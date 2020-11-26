#!/bin/bash

# Install MySQL client
echo "Mysql client installing..."
# sudo apt update -qq && apt install -qq -y mysql-client-8.0 unzip
sudo yum install https://dev.mysql.com/get/mysql80-community-release-el7-3.noarch.rpm
sudo yum install mysql-community-client

# Connect to MySQL server
export MYSQL_PWD="yD5dMepw7XpwEWn8"
# Download reviews from Mysql server 
echo "Downloading review.tsv"
mysql -u root -h 13.250.30.159 -e "select * from DBProject.review" | tail -n +2 > review.csv

# Install Mongodb tools
echo "Mongo-tools installing..."
# sudo apt-get install gnupg
# wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
# echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
# sudo apt-get update
# sudo apt-get install -y mongodb-database-tools
# sudo echo -e "
# [mongodb-org-4.4] \n
# name=MongoDB Repository \n
# baseurl=https://repo.mongodb.org/yum/redhat/$releasever/mongodb-org/4.4/x86_64/ \n
# gpgcheck=1 \n
# enabled=1 \n
# gpgkey=https://www.mongodb.org/static/pgp/server-4.4.asc \n
# " > /etc/yum.repos.d/mongodb-org-4.4.repo
sudo yum install https://repo.mongodb.org/yum/amazon/2/mongodb-org/4.4/x86_64/RPMS/mongodb-database-tools-100.0.0.x86_64.rpm

# Download books from Mongodb server
echo "Downloading book.json"
mongoexport --collection=books --out=books.json "mongodb://DBProjectUser:NcMcZDU9Sqw49nJT@54.255.154.236:27017/DBProject?authSource=DBProject"

# HDFS upload
echo "Uploading review.tsv & books.json to hdfs"
hdfs dfs -mkdir -p /DBProject
hdfs dfs -put review.tsv /DBProject/review.tsv
hdfs dfs -put books.json /DBProject/books.json

# Download Pyspark analytic scripts 
wget https://raw.githubusercontent.com/LengSicong/DatabaseAnalytics/main/correlation.py
wget https://raw.githubusercontent.com/LengSicong/DatabaseAnalytics/main/tfidf.py

# Download pyspark
echo "Pyspark downloading..."
sudo yum update
sudo yum install python-pip
sudo pip install numpy
python -m pip --no-cache-dir install pyspark --user

# Run analytic script
python correlation.py
python tfidf.py

# HDFS download
hdfs dfs -get ./DBProject/tfidf_output.csv ./
hdfs dfs -get ./DBProject/correlation_output.txt ./




