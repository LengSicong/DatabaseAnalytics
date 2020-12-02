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
    vpc_id = response.get('Vpcs', [{}])[0].get(
        'VpcId', '')  # Get VPC id of this aws account

    try:
        response = ec2_client.create_security_group(GroupName=security_group_name,
                                                    Description="Group7:This is for SUTD 50.0043 Big Data and Database project",
                                                    VpcId=vpc_id)
        security_group_id = response['GroupId']
        pp.pprint('Security Group Created %s in vpc %s.' %
                  (security_group_id, vpc_id))

        data = ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                 'FromPort': 80,
                 'ToPort': 80,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp',
                 'FromPort': 22,  # SSH
                 'ToPort': 22,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp',
                 'FromPort': 27017,  # MongoDB
                 'ToPort': 27017,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp',
                 'FromPort': 3306,  # mySQL
                 'ToPort': 3306,
                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}

            ])
        pp.pprint('Ingress Successfully Set %s' % data)

    except ClientError as e:
        pp.pprint(e)

# function for creating a key-pair for EC2 instance


def generate_key_pairs(key_name):  # Key_name needs to be unique *
    outfile = open('{}.pem'.format(key_name), 'w')
    key_pair = ec2.create_key_pair(KeyName=key_name)
    KeyPairOut = str(key_pair.key_material)
    outfile.write(KeyPairOut)
    # print(KeyPairOut)
    print("Finish creating EC2 key paris")
    os.system("chmod 400 {}.pem".format(key_name))


# set up aws credentials and config
key_id = "ASIAWETJUJFKAUYQ56GJ"
access_key = "1tXld6FPCSCsIr27576zlT0H0Fp5U2xeWjDiGR3k"
session_token = "FwoGZXIvYXdzEBUaDIIYlplReTOC+fC7mSLKAXpRlH08tPvuYWaWzETVUar4v3didHk/QDsNONstzLKpdjZg6QqC8HV/yauA6u7kn03Iz0zTWBGOZjizHMBnRFR0qnbzfsRWACXLQ54jZDCC9KksLze6xYqB/+E3ZjUbGptMZbrYQ0J5vKUHrXN17TPd/9ZC4ftxqV15IbYd89EruuiAhxC/PR651eDJsZsil2Sekmg0HkAQw31s7WBERAGQ4LQCFEZ5TuR4uDJJRWiMwPVtH9azXJEtJ9AkoKJKffc129S5YDNEEGUous2Y/gUyLYgcaiGG1hnlOHE3d0Dw558nkW2jKVA+lPV5gQ1Kk2i55khmKUCekDTT+ecBGw=="

region = "us-east-1"

os.system("echo '[default]\naws_access_key_id = %s\naws_secret_access_key = %s\naws_session_token = %s' > ~/.aws/credentials" %
          (str(key_id), str(access_key), str(session_token)))
os.system("echo '[default]\nregion = %s' > ~/.aws/config" % (str(region)))

# Connection automaticaly use saved aws credentials and config
ec2 = boto3.resource('ec2')
ec2_client = boto3.client('ec2')

# 1. Set up the security group
print("\nStep 1 Set up Security Group:")
security_group_name = 'DatabaseProject'
try:
    response = ec2_client.describe_security_groups(
        GroupNames=[security_group_name])
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
if key_not_exist:
    print("Generating a unique key for EC2 instances")
    generate_key_pairs(key_name)
