from __future__ import annotations
import argparse
import io
import logging
import os
import threading
import queue
import hashlib
import subprocess
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional
import boto3
import boto3.session
import paramiko


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d  %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


# =================== EC2 Management ====================
class EC2Config():
    def __init__(self, image_id: str, instance_type: str) -> None:
        self.instance_type = instance_type
        self.block_device_mappings = []
        self.image_id = image_id
        self.ip_permissions = []
        self.setup_script = None

    @staticmethod
    def get_latest_ubuntu_ami() -> str:
        session = boto3.session.Session()
        images = session.client('ec2').describe_images(Filters=[{
            'Name': 'name',
            'Values': ['ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server*']
        }])
        return sorted(images['Images'], key=lambda i: i['CreationDate'])[-1]['ImageId']

    def with_storage(
            self, volume_size: int = 8,
            volume_type: str = 'gp2',
            device_name: str = '/dev/sda1',
            delete_on_termination: bool = True) -> EC2Config:
        self.block_device_mappings.append({
            'DeviceName': device_name,
            'Ebs': {
                'DeleteOnTermination': delete_on_termination,
                'VolumeSize': volume_size,
                'VolumeType': volume_type
            },
        })
        return self

    def with_inbound_rule(self, protocol: str, port: int, ip_range: str = '0.0.0.0/0') -> EC2Config:
        self.ip_permissions.append({
            'IpProtocol': protocol,
            'FromPort': port,
            'ToPort': port,
            'IpRanges': [{'CidrIp': ip_range}]
        })
        return self


class EC2RuntimeException(Exception):
    pass


class EC2KeyPair():
    DEFAULT_USER = 'ubuntu'
    DEFAULT_PORT = 22

    def __init__(self, key_name: str, priv_key: paramiko.PKey) -> None:
        self.key_name = key_name
        self.priv_key = priv_key

    @staticmethod
    def from_file(filename: str) -> EC2KeyPair:
        f = argparse.FileType('r')(filename)
        name = os.path.basename(f.name).replace('.pem', '')
        key = paramiko.RSAKey.from_private_key(f)
        return EC2KeyPair(key_name=name, priv_key=key)

    @staticmethod
    def from_str(keystr: str) -> EC2KeyPair:
        name, key_str = keystr.split(':')
        key = paramiko.RSAKey.from_private_key(io.StringIO(key_str))
        return EC2KeyPair(key_name=name, priv_key=key)

    @staticmethod
    def new(filename: str) -> EC2KeyPair:
        f = argparse.FileType('x')(filename)
        name = os.path.basename(f.name).replace('.pem', '')
        logger.info(f'Creating a new EC2 key pair {name}...')
        keypair = boto3.client('ec2').create_key_pair(KeyName=name)
        f.writelines(keypair['KeyMaterial'])
        f.close()
        logger.info(f'Saved EC2 key pair to {filename}')
        key = paramiko.RSAKey.from_private_key_file(filename)
        return EC2KeyPair(key_name=name, priv_key=key)


class EC2SSHConfig():
    def __init__(self, keypair: EC2KeyPair, username: str = 'ubuntu', port: int = 22) -> None:
        self.keypair = keypair
        self.username = username
        self.port = port


class EC2Instance():
    NotExistsException = EC2RuntimeException('Instance does not exist')
    AlreadyExistsException = EC2RuntimeException('Instance already exists')

    def __init__(self, app_name: str, ssh_config: EC2SSHConfig,
                 logger: logging.Logger = None) -> None:
        self.app_name = app_name
        self.ssh_config = ssh_config

        self._boto3_session = boto3.session.Session()
        self._ec2_client = self._boto3_session.client('ec2')
        self._session_id = str(int(time.time()))
        self._logger = logger or logging.getLogger(self.__class__.__name__)

        self._ssh = None

    @property
    def instance(self) -> Optional[Dict[str, Any]]:
        response = self._ec2_client.describe_instances(Filters=[{
            'Name': 'tag:app_name',
            'Values': [self.app_name]
        }])
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] == 'running':
                    instances.append(instance)
        if len(instances) > 1:
            raise EC2RuntimeException(
                f'Found multiple instance with tag app_name:{self.app_name}! '
                'Please manually check them in AWS console.')
        if len(instances) == 1:
            return instances[0]

    @property
    def exists(self) -> bool:
        return self.instance is not None

    @property
    def public_ip(self) -> str:
        if not self.exists:
            raise self.NotExistsException
        return self.instance['PublicIpAddress']

    @property
    def private_ip(self) -> str:
        if not self.exists:
            raise self.NotExistsException
        return self.instance['PrivateIpAddress']

    @property
    def instace_id(self) -> str:
        if not self.exists:
            raise self.NotExistsException
        return self.instance['InstanceId']

    @property
    def ssh(self) -> paramiko.SSHClient:
        if self._ssh:
            return self._ssh

        if not self.exists:
            raise self.NotExistsException

        retries = 3
        interval = 5

        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ip_address = self.public_ip
        for _ in range(retries):
            try:
                self._logger.info(f'SSH into the instance {self.app_name}({ip_address})')
                self._ssh.connect(
                    ip_address,
                    port=self.ssh_config.port,
                    username=self.ssh_config.username,
                    pkey=self.ssh_config.keypair.priv_key)
                return self._ssh
            except Exception as e:
                self._logger.warning(e)
                self._logger.info(f'Retrying in {interval} seconds...')
                time.sleep(interval)
        raise EC2RuntimeException(f'Failed to ssh into the {self.app_name}({ip_address})')

    def _create_security_group(self, ip_permissions):
        rule_id = hashlib.md5(str(ip_permissions).encode('utf-8')).hexdigest()[:8]
        group_name = self.app_name + '-' + rule_id

        # return existing group if exists
        response = self._ec2_client.describe_security_groups(Filters=[{
            'Name': 'group-name',
            'Values': [group_name]}
        ])
        if len(response['SecurityGroups']) > 0:
            return response['SecurityGroups'][0]['GroupId']

        # Create new security group
        response = self._ec2_client.create_security_group(
            GroupName=group_name, Description=group_name)
        security_group_id = response['GroupId']
        self._ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=ip_permissions
        )
        return security_group_id

    def launch(self, config: EC2Config = None) -> None:
        if self.exists:
            raise self.AlreadyExistsException

        self._ec2_client.run_instances(
            ImageId=config.image_id,
            InstanceType=config.instance_type,
            MinCount=1,
            MaxCount=1,
            BlockDeviceMappings=config.block_device_mappings,
            SecurityGroupIds=[
                self._create_security_group(config.ip_permissions)
            ],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'app_name',
                        'Value': self.app_name
                    },
                    {
                        'Key': 'Name',
                        'Value': self.app_name
                    }
                ]
            }],
            KeyName=self.ssh_config.keypair.key_name
        )

        while self.instance is None:
            self._logger.info('Waitting for the instance to be running...')
            time.sleep(30)

        self._logger.info('Waitting for AWS cloud-init(about 30s) ...')
        time.sleep(25)
        self.run_command('; '.join([
            "while [ ! -f /var/lib/cloud/instance/boot-finished ]",
            "do echo 'Waiting for cloud-init...'",
            "sleep 3",
            "done"
        ]))

    def terminate(self) -> None:
        if not self.exists:
            raise self.NotExistsException
        ec2 = self._boto3_session.resource('ec2')
        ec2.instances.filter(InstanceIds=[self.instace_id]).terminate()

    def run_command(self, command: str) -> List[str]:
        def channel_logger(logger_func, channel):
            while True:
                line = channel.readline()
                if not line:
                    break
                logger_func(line.rstrip())

        self._logger.info('$ ' + command)
        session_file = '/tmp/ssh_seesion_' + self._session_id
        _, stdout, stderr = self.ssh.exec_command(' ; '.join([
            'touch ' + session_file,
            'source ' + session_file,
            'cd $PWD',
            command + ' && export -p > ' + session_file
        ]))

        stdout_lines = []

        t_err = threading.Thread(target=channel_logger, args=(self._logger.warning, stderr))
        t_err.start()
        try:
            channel_logger(lambda line: (
                self._logger.info(line),
                stdout_lines.append(line)
            ), stdout)
            t_err.join()
            if stdout.channel.recv_exit_status() != 0:
                raise EC2RuntimeException(
                    f'Command `{command}` failed with non-zero exit code')
        except (KeyboardInterrupt, Exception):
            stderr.channel.close()
            self._logger.info('Channel closed')
            raise

        return stdout_lines

    def run_local_script(
            self, script_path: Path,
            sudo: bool = False, cwd: Optional[PurePosixPath] = None) -> None:
        remote_path = '/tmp/automation_script'
        self.upload_file(script_path, PurePosixPath(remote_path))
        # this line converts CRLF to LF in case Windows in used to deploy
        self.run_command('ex -bsc \'%!awk "{sub(/\\r/,\\"\\")}1"\' -cx ' + remote_path)
        self.run_command('chmod +x ' + remote_path)
        commands = []
        if cwd:
            commands.append('cd ' + str(cwd))
        commands.append(('sudo -E ' if sudo else '') + '/tmp/automation_script')
        self.run_command(' && '.join(commands))

    def upload_file(self, local_path: Path, remote_path: PurePosixPath) -> None:
        with self.ssh.open_sftp() as sftp:
            self._logger.info(f'Uploading {str(local_path.absolute())} -> {str(remote_path)}')
            sftp.put(localpath=str(local_path.absolute()), remotepath=str(remote_path))

    def download_file(self, remote_path: PurePosixPath, local_path: Path) -> None:
        with self.ssh.open_sftp() as sftp:
            sftp.get(remotepath=str(remote_path), localpath=str(local_path.absolute()))

    def import_variable(self, **kvs: str):
        for name, value in kvs.items():
            self.run_command(f'export {name}={value}')

    def export_variable(self, name: str) -> str:
        value = self.run_command('echo $' + name)[-1]
        return value


# =================== Helpers ====================
def archive_git_dir(dir: Path, save_as: Path) -> Path:
    p = subprocess.Popen(['git', 'archive', '-o', str(save_as), 'HEAD'], cwd=dir)
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f'Failed to create project archive: {p.stderr}')
    return save_as


class FutureValue():
    def __init__(self) -> None:
        self._queue = queue.Queue(maxsize=1)
        self._done = False
        self._result = None
        self._result_saved = False
        self._w_lock = threading.Lock()
        self._r_lock = threading.Lock()

    def set(self, value) -> None:
        with self._w_lock:
            if self._done:
                raise ValueError('Future can only be set once')
            self._queue.put_nowait(value)
            self._done = True

    def get(self) -> Any:
        with self._r_lock:
            if self._result_saved:
                return self._result
            self._result = self._queue.get()
            self._result_saved = True
            return self._result


class CatchableThread(threading.Thread):
    def __init__(self, target: Callable[[], Any]) -> None:
        super().__init__()
        self._target = target
        self._exception = None
        self._lock = threading.Lock()

    def run(self):
        try:
            self._target()
        except BaseException as e:
            self._lock.acquire()
            self._exception = e
            self._lock.release()
            raise

    def exception(self):
        self._lock.acquire()
        e = self._exception
        self._lock.release()
        return e


def run_in_parallel(*tasks: Callable[[], Any]) -> None:
    threads = [CatchableThread(target=task) for task in tasks]
    for thread in threads:
        thread.daemon = True
        thread.start()
    pending = threads[:]
    while pending:
        for i in range(len(pending)):
            # join thread with timeout 0.5s
            pending[i].join(timeout=0.5)
            # if the thread is still alive, means we reached timeout
            if pending[i].is_alive():
                # just continue
                continue
            # otherwise the thread did finished
            # if due to exception, abort all tasks
            e = pending[i].exception()
            if e:
                logger.error('Abort all tasks because of exception: ' + str(e))
                exit(-1)
            # remove the finished task from pending
            pending.pop(i)
            break


# ================= Main Function =================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--override', action='store_true',
        help='terminate existing instances before deploy')
    keypair_group = parser.add_mutually_exclusive_group(required=True)
    keypair_group.add_argument('--keyfile', type=EC2KeyPair.from_file)
    keypair_group.add_argument('--key', type=EC2KeyPair.from_str)
    keypair_group.add_argument('--newkey', type=EC2KeyPair.new, dest='new_key_path')
    args = parser.parse_args()

    keypair = args.keyfile or args.key or args.new_key_path
    ssh_config = EC2SSHConfig(keypair, username='ubuntu', port=22)

    project_base = Path(__file__).absolute().parent.parent
    project_archive = archive_git_dir(project_base, save_as=project_base/'archive.tar.gz')

    mongo_public_url = FutureValue()
    mongo_private_url = FutureValue()

    def deploy_mongodb():
        logger = logging.getLogger('@mongodb')
        instance = EC2Instance('mongodb', ssh_config, logger)

        if args.override or not instance.exists:
            if instance.exists:
                logger.info('Terminating existing MongoDB instance')
                instance.terminate()

            logger.info('Launching new MongoDB instance')
            instance.launch(
                EC2Config(
                    image_id=EC2Config.get_latest_ubuntu_ami(),
                    instance_type='t2.micro')
                .with_storage(volume_size=20)
                .with_inbound_rule('tcp', 22)
                .with_inbound_rule('tcp', 27017))
            instance.run_local_script(project_base/'scripts'/'setup'/'setup_mongo.bash', sudo=True)

        # export credentials from saved credentials
        instance.run_command('source ~/.credentials')
        db_name = instance.export_variable('MONGO_DB')
        db_user = instance.export_variable('MONGO_USR')
        db_pass = instance.export_variable('MONGO_PWD')

        # create url
        mongo_url_template = 'mongodb://{}:{}@{}:27017/{}?authSource={}'
        mongo_public_url.set(mongo_url_template.format(
            db_user, db_pass, instance.public_ip, db_name, db_name))
        mongo_private_url.set(mongo_url_template.format(
            db_user, db_pass, instance.private_ip, db_name, db_name))

    mysql_private_ip = FutureValue()
    mysql_public_ip = FutureValue()
    mysql_database = FutureValue()
    mysql_username = FutureValue()
    mysql_password = FutureValue()
    auth_secret = FutureValue()

    def deploy_mysql():
        logger = logging.getLogger('@mysql')
        instance = EC2Instance('mysql', ssh_config, logger)

        if args.override or not instance.exists:
            if instance.exists:
                logger.info('Terminating existing MySQL instance')
                instance.terminate()

            logger.info('Launching new MySQL instance')
            instance.launch(
                EC2Config(
                    image_id=EC2Config.get_latest_ubuntu_ami(),
                    instance_type='t2.micro')
                .with_storage(volume_size=20)
                .with_inbound_rule('tcp', 22)
                .with_inbound_rule('tcp', 80)
                .with_inbound_rule('tcp', 3306))
            instance.run_local_script(project_base/'scripts'/'setup'/'setup_mysql.bash', sudo=True)

        # export credentials from saved credentials
        instance.run_command('source ~/.credentials')
        mysql_database.set(instance.export_variable('MYSQL_DB'))
        mysql_username.set(instance.export_variable('MYSQL_USR'))
        mysql_password.set(instance.export_variable('MYSQL_PWD'))
        auth_secret.set(instance.export_variable('AUTH_SECRET'))
        mysql_private_ip.set(instance.private_ip)
        mysql_public_ip.set(instance.public_ip)

    react_build = FutureValue()

    def build_react():
        logger = logging.getLogger('@builder')
        instance = EC2Instance('react-builder', ssh_config, logger)
        if instance.exists:
            instance.terminate()
        instance.launch(
            EC2Config(
                image_id=EC2Config.get_latest_ubuntu_ami(),
                instance_type='t2.xlarge')
            .with_storage(volume_size=8)
            .with_inbound_rule('tcp', 22))
        try:
            logger.info('Installing node.js')
            version, distro = 'v14.15.1', 'linux-x64'
            instance.run_command(' && '.join([
                f'wget -q -c https://nodejs.org/dist/{version}/node-{version}-{distro}.tar.xz',
                f'sudo mkdir -p /usr/local/lib/nodejs',
                f'sudo tar -xJf node-{version}-{distro}.tar.xz -C /usr/local/lib/nodejs',
                f'export PATH=/usr/local/lib/nodejs/node-{version}-{distro}/bin:$PATH'
            ]))
            logger.info('Uploading project archive')
            instance.upload_file(project_archive, PurePosixPath('app.tar.gz'))
            logger.info('Building project')
            instance.import_variable(
                NODE_OPTIONS='--max-old-space-size=14336',
                GENERATE_SOURCEMAP='false')
            instance.run_command(' && '.join([
                'mkdir -p app',
                'tar -zxf app.tar.gz -C app',
                'cd app',
                'npm install --loglevel warn',
                'npm run build',
                'tar -zcf build.tar.gz build/',
                'cd ~'
            ]))
            save_as = project_base/'build.tar.gz'
            instance.download_file(PurePosixPath('app/build.tar.gz'), save_as)
            react_build.set(save_as)
        finally:
            instance.terminate()

    web_app_ip = FutureValue()

    def deploy_web_app():
        logger = logging.getLogger('@web-app')
        instance = EC2Instance('web-app', ssh_config, logger)

        if args.override or not instance.exists:
            if instance.exists:
                logger.info('Terminating existing WebApp instance')
                instance.terminate()

            logger.info('Launching new WebApp instance')
            instance.launch(
                EC2Config(
                    image_id=EC2Config.get_latest_ubuntu_ami(),
                    instance_type='t2.micro')
                .with_storage(volume_size=8)
                .with_inbound_rule('tcp', 22)
                .with_inbound_rule('tcp', 80))
            instance.run_local_script(project_base/'scripts'/'setup'/'setup_web.bash', sudo=True)

        web_app_ip.set(instance.public_ip)

        logger.info('Uploading project archive')
        instance.upload_file(project_archive, PurePosixPath('app.tar.gz'))

        logger.info('Releasing files')
        instance.run_command(' && '.join([
            'mkdir -p app',
            'tar -zxf app.tar.gz -C app'
        ]))
        logger.info('Installing dependencies')
        instance.run_command(' && '.join([
            'cd app',
            'sudo npm install --loglevel warn',
            'cd ~'
        ]))
        logger.info('Uploading front-end build')
        instance.upload_file(react_build.get(), PurePosixPath('build.tar.gz'))
        instance.run_command(' && '.join([
            'sudo rm -rf build',
            'tar -zxf build.tar.gz',
            'sudo rm -rf /var/www/html',
            'sudo cp -r build /var/www/html'
        ]))

        logger.info('Launching back-end service')
        instance.run_command(' && '.join([
            'cd app',
            'rm -f .env',
            f'echo MONGODB_URL={mongo_private_url.get()} >> .env',
            'echo MYSQL_URL='
            + f'mysql://{mysql_username.get()}:{mysql_password.get()}'
            + f'@{mysql_private_ip.get()}/{mysql_database.get()} >> .env',
            f'echo AUTHENTICATION_SECRET={auth_secret.get()} >> .env',
            '( sudo pm2 delete all || true )',
            'sudo pm2 start ./src/api/index.js'
            + ' -i max -e /var/log/nodejs/err.log -o /var/log/nodejs/out.log',
        ]))

    # Start tasks
    run_in_parallel(deploy_mongodb, deploy_mysql, build_react, deploy_web_app)

    # Print result
    print()
    print('\x1b[6;30;42m' + 'Success!' + '\x1b[0m')

    print('\x1b[1;32;40m●\x1b[0m MongoDB')
    print('URL:', mongo_public_url.get())
    print()

    print('\x1b[1;32;40m●\x1b[0m MySQL')
    print('IP:        ', mysql_public_ip.get())
    print('Database:  ', mysql_database.get())
    print('Username:  ', mysql_username.get())
    print('Password:  ', mysql_password.get())
    print('phpMyAdmin:', f'http://{mysql_public_ip.get()}/phpmyadmin')
    print()

    print('\x1b[1;32;40m●\x1b[0m WebApp')
    print('IP: ', web_app_ip.get())
    print('URL:', f'http://{web_app_ip.get()}/')
    print()

    print('# Please add the following to your local .env file:')
    print(f'MONGODB_URL={mongo_public_url.get()}')
    print(
        f'MYSQL_URL=mysql://{mysql_username.get()}:{mysql_password.get()}'
        f'@{mysql_public_ip.get()}/{mysql_database.get()}')
    print(f'AUTHENTICATION_SECRET={auth_secret.get()}')
    print()

    # Clean up
    os.remove(project_archive)
    os.remove(react_build.get())


if __name__ == "__main__":
    main()