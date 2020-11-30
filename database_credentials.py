import argparse
import logging
import os
from deploy_production import EC2SSHConfig, EC2KeyPair, EC2Instance


logger = logging.getLogger(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keyfile', type=EC2KeyPair.from_file, required=True)
    args = parser.parse_args()

    ssh_config = EC2SSHConfig(args.keyfile, username='ubuntu', port=22)

    mongo_instance = EC2Instance('mongodb', ssh_config, logger)
    if not mongo_instance.exists:
        logger.error('Can not find MongoDB instance')
        exit(1)

    mysql_instance = EC2Instance('mysql', ssh_config, logger)
    if not mysql_instance.exists:
        logger.error('Can not find MySQL instance')
        exit(1)

    mongo_instance.run_command('source ~/.credentials')
    db_name = mongo_instance.export_variable('MONGO_DB')
    db_user = mongo_instance.export_variable('MONGO_USR')
    db_pass = mongo_instance.export_variable('MONGO_PWD')
    mongo_url = f'mongodb://{db_user}:{db_pass}@{mongo_instance.private_ip}:27017/{db_name}?authSource={db_name}'

    mysql_instance.run_command('source ~/.credentials')
    mysql_ip = mysql_instance.private_ip
    mysql_database = mysql_instance.export_variable('MYSQL_DB')
    mysql_username = mysql_instance.export_variable('MYSQL_USR')
    mysql_password = mysql_instance.export_variable('MYSQL_PWD')

    print('\x1b[1;32;40m●\x1b[0m MongoDB')
    print('URL:', mongo_url)
    print()

    print('\x1b[1;32;40m●\x1b[0m MySQL')
    print('IP:        ', mysql_ip)
    print('Database:  ', mysql_database)
    print('Username:  ', mysql_username)
    print('Password:  ', mysql_password)
    print()

    cmd_1 = f'export MYSQL_PWD={mysql_password}' 
    os.system(cmd_1)
    cmd_2 = f'export MYSQL_IP={mysql_ip}' 
    os.system(cmd_2)
    cmd_3 = f'export MONGO_URL={mongo_url}'
    os.system(cmd_3)

if name == "main":
    main()