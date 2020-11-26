import sys
import boto3
from botocore.exceptions import ClientError
import botocore
import paramiko
import os

def get_mastermode_ip(ec2_client,tagname):
    master_tagname = tagname + '-master'
    masternodes = []
    
    response = ec2_client.describe_instances(
        Filters=[
            {
                'Name':'tag:Name',
                'Values': [
                    master_tagname
                ]
            }
        ]
    )
    for instance in response['Reservations']:
        for i in instance['Instances']:
            if i['State']['Name'] == 'running':
                masternodes.append(i)

    if len(masternodes) == 1:
        public_ip = masternodes[0]['PublicIpAddress']
        key_name = masternodes[0]['KeyName']
        print('\033[1m'+'\033[95m'+'Public ip for masternode: ',public_ip)
        print('Key required: {}.pem'.format(key_name)+'\033[0m')

        return public_ip,key_name
    else:
        print("WARN! The number of master node shoudld be 1")

def exe_cmd(cmds):
    stdin , stdout, stderr = p_client.exec_command(cmds)
    lines = stdout.readlines()
    for line in lines:
        print(line)
    if len(stderr.readlines()) != 0:
        print(stderr.readlines())    


cluster_name = sys.argv[1]
print('cluster name: ',cluster_name)

# connect
ec2_client = boto3.client('ec2')

# key set up
masternode_ip,key_name= get_mastermode_ip(ec2_client,cluster_name)

key = paramiko.RSAKey.from_private_key_file(key_name+".pem")
p_client = paramiko.SSHClient()
p_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# download sql client and mongodb client


# set up analytic applications on masternode
print("\n--------------Seting up correlation and tf-idf applications -------------------")
try:
    print("Setting up masternode on: "+str(masternode_ip))
    p_client.connect(hostname=masternode_ip, username= "ubuntu", pkey= key)

    # loading data and running analytic scripts: to be done!
    print("downloading the analytic script...")
    exe_cmd("wget https://raw.githubusercontent.com/LengSicong/DatabaseAnalytics/main/analytics.sh") 
    print("running analytic scripts...")
    exe_cmd('chmod +x analytics.sh')
    exe_cmd('yes | ./analytics.sh')

    # disconnect and save the analysis result to local machine
    p_client.close()
    copy_command_1 = 'scp -i {}.pem -o StrictHostKeyChecking=no ubuntu@'.format(key_name)+masternode_ip+':~/Pearson_correlation_output.txt .'
    copy_command_2 = 'scp -i {}.pem -o StrictHostKeyChecking=no ubuntu@'.format(key_name)+masternode_ip+':~/tfidf_output.csv .'
    os.system(copy_command_1)
    os.system(copy_command_2)

except Exception as e:
    print(e)





