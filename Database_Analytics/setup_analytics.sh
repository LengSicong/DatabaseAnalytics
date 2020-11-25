#!/bin/bash

# --------- Linux ----------
if [[ "$OSTYPE" == "linux-gnu" ]]; then
    echo "Detected Linux system"
    echo ""
    
    if ! [ -x "$(command -v python3)" ]; then
        echo -e "Installing python"
        sudo apt-get install python3-pip
    fi
    echo "Installing wget"
    if ! [ -x "$(command -v wget)" ]; then
        sudo apt-get install wget
    fi
# ------- Mac OS --------------
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected MACOSX system"
    echo ""
    echo "Installing curl on your machine "
    if ! [ -x "$(command -v curl)" ]; then
        brew install curl
    fi
else
    echo "This script need Linux or MacOS system"
fi

mkdir -p ~/.aws
FILE1=~/.aws/credientials
if [ -f "$FILE1" ]; then
    touch "$FILE1"
fi
FILE2=~/.aws/config
if [ -f "$FILE2" ]; then
    touch "$FILE2"
fi

# downloading the set up script
echo -e "Downloading scripts for analytic system"
# to be done: curl http://***/analytic_backend_setup.py --output analytic_backend_setup.py

read -p "Create new python virtual environment 'VeryGoodReads' to run scripts, (y/n)?" create
if [ "$create" == "y" ]; then
    python3 -m venv VeryGoodReads
    source VeryGoodReads/bin/activate
else 
    echo "A new virtual environment is needed for running our scripts, please type 'y'. "
    echo "Terminating process..."
    exit 
fi

echo -e "Installing libraries: boto3, paramiko, and flintrock"
python3 -m pip install boto3 paramiko flintrock

echo -e "All local dependencied are installed"

echo "-------------- Set up Analytic System backend ---------------"
# Alter the number of datanodes
read -p "Please Enter number of slaves: " NUM

echo -e "building aws neccesary components..."
python3 analytic_backend_setup.py

echo -e "creating cluster..."
flintrock launch very_good_reads_$NUM \
    --num-slaves $NUM \
    --spark-version 2.4.4 \
    --hdfs-version 2.7.7 \
    --ec2-key-name databaseproject-ec2-key \
    --ec2-identity-file databaseproject-ec2-key.pem \
    --ec2-ami ami-068663a3c619dd892 \
    --ec2-user ubuntu \
    --ec2-instance-type t2.medium \
    --ec2-region us-east-1 \
    --hdfs-download-source https://apachemirror.sg.wuchna.com/hadoop/common/hadoop-3.3.0/hadoop-3.3.0.tar.gz \
    --install-hdfs \
    --spark-download-source https://apachemirror.sg.wuchna.com/spark/spark-3.0.1/spark-3.0.1-bin-hadoop3.2.tgz \
    --install-spark

echo -e "setting up masternode..."
python3 setup_nodes.py very_good_reads_$NUM

