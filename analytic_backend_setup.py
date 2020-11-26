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
key_id = "ASIAWETJUJFKO6AYWYZF"
access_key = "cI5eyjEbpLTvLUNMv1wtjfBU6D2QHbzHnwVXO7FU"
session_token = "FwoGZXIvYXdzEJ7//////////wEaDI2+RkZucmQlkBFvRCLKASwpIDqkwmdhEEkIZ1YIfDh23DK/5iCHF1x/jnnzTGVXW7SdjPW/0qTvuP+Uvlds3HGWeyGv83j3viLY5LdeqM6HtdaijxlxVb/Ef4TyLcsfL5eQj0AV3PhoKh0Of1kmnGVI33b+eWozR29eJuRZ8ojUK/vQzi/3YA9jkxBuO5pEfWB2wGqE4hZhSTG/v8Vvi8hVQq0RWLZIizJULhO31V/lM1a7roYC9H86gBVUbcMpalYrQatmmg8IqyqdBdbmawG+9i5gNk+IaKYo/rT+/QUyLaVJ1uCkh0xqAwEZWp82EOkmpnOVukck77jQvOBmT3AF+E3HsmXAZmvPNPfAog=="

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

