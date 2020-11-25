import sys
import boto3
import pprint as pp
import os
from botocore.exceptions import ClientError

import botocore
import paramiko

# functions for creating security group
def create_security_group(security_group_name):
    response = ec2_client.describe_vpcs()
    vpc_id = response.get('Vpcs', [{}])[0].get('VpcId', '') #Get VPC id of this aws account

    try:
        response = ec2_client.create_security_group(GroupName=security_group_name,
                                             Description="Group7:This is for SUTD 50.0043 Big Data and Database project",
                                             VpcId=vpc_id)
        security_group_id = response['GroupId']
        pp.pprint('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

        data = ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                 'FromPort': 80,
                 'ToPort': 80,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp',
                 'FromPort': 22,      ## SSH
                 'ToPort': 22,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp',
                 'FromPort': 27017,   ## MongoDB
                 'ToPort': 27017,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp',
                 'FromPort': 3306,    ## mySQL
                 'ToPort': 3306,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}

            ])
        pp.pprint('Ingress Successfully Set %s' % data)

    except ClientError as e:
        pp.pprint(e)

# function for creating a key-pair for EC2 instance
def generate_key_pairs(key_name):  # Key_name needs to be unique *
    outfile = open('{}.pem'.format(key_name),'w')
    key_pair = ec2.create_key_pair(KeyName=key_name)
    KeyPairOut = str(key_pair.key_material)
    outfile.write(KeyPairOut)
    # print(KeyPairOut)
    print("Finish creating EC2 key paris")
    os.system("chmod 400 {}.pem".format(key_name))



# set up aws credentials and config
key_id = "ASIA2AAJXSNIHHA6FLWI"
access_key = "byk9nc2LVzbNxg3Qhb0eO5MY4/WmaVwruHCdGNu7"
session_token = "FwoGZXIvYXdzEIP//////////wEaDETAv0dDBz0iydZ0gyLNAeVeKlDPvLCK8gaxQjlJFUsG7yBqoTPEgrTXkXmUNKFglAU1NikY1GJHxz7uJTk+eraTjhYKa6I8wLPOWyLLooJBM4IqIXkyAMFfQk8YmnFrRIP8oUZezG1IcaKR5+IVlFOEaxNFtHPN7ASeYtoLJR7vqyBJAg8CMF+/J7rW9bxi7DzTa9UJyaoJjPQdj9KWbVZwn4bbb3Lf7SOFYpE7QSemLrgpvpEbuKbxQMTdujJrBv/IIHjdtMXW3oqEAaS9h0Ytut5gktUjrICoUNUowMn4/QUyLQ1pCOZyrH8JeW9TnCQvvWs5eLK4Rmnghe316+JrTJRcXrWEV0qVmdUrxZsr6w=="

region = "us-east-1"

os.system("echo '[default]\naws_access_key_id = %s\naws_secret_access_key = %s\naws_session_token = %s' > ~/.aws/credentials"%(str(key_id),str(access_key),str(session_token)))
os.system("echo '[default]\nregion = %s' > ~/.aws/config"%(str(region)))

# Connection automaticaly use saved aws credentials and config
ec2 = boto3.resource('ec2')
ec2_client = boto3.client('ec2')

# 1. Set up the security group
print("\nStep 1 Set up Security Group:")
security_group_name='DatabaseProject'
try:
    response = ec2_client.describe_security_groups(GroupNames=[security_group_name])
    print("Security group: {} already exits".format(security_group_name))
except ClientError as e:
    print("Creating a new security group named {}\n".format(security_group_name))
    create_security_group(security_group_name)


# 2. Set up the key
print("\nStep 2 Set up Key-pair:")
key_name = "databaseproject-ec2-key"
key_not_exist = True

keyPairs = ec2_client.describe_key_pairs()
for key in keyPairs.get('KeyPairs'):
    if key.get('KeyName') == key_name:
        key_not_exist = False
        print("key-pair: {} already exists.".format(key_name))
        break
if key_not_exist :
    print("Generating a unique key for EC2 instances")
    generate_key_pairs(key_name)

