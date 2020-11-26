#!/bin/bash

# Install MySQL client
echo "Mysql client installing..."
sudo apt update -qq && apt install -qq -y mysql-client-8.0 unzip

# Connect to MySQL server
export MYSQL_PWD="yD5dMepw7XpwEWn8"
# Download reviews from Mysql server 
echo "Downloading review.tsv"
mysql -u root -h 13.250.30.159 -p -e "select * from DBProject.review" | tail -n +2 > review.tsv

# Install Mongodb tools
echo "Mongo-tools installing..."
sudo apt-get install gnupg
wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
sudo apt-get update
sudo apt-get install -y mongodb-database-tools

# Download books from Mongodb server
echo "Downloading book.json"
mongoexport --collection=books --out=books.json "mongodb://DBProjectUser:NcMcZDU9Sqw49nJT@54.255.154.236:27017/DBProject?authSource=DBProject"

# HDFS upload
echo "Uploading review.tsv & books.json to hdfs"
hdfs dfs -mkdir -p /DBProject
hdfs dfs -put review.tsv /DBProject/review.tsv
hdfs dfs -put books.json /DBProject/books.json

# Download Pyspark analytic scripts 
wget 
wget 

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
hdfs dfs -get tfidf_output.csv ./
hdfs dfs -get ßcorrelation_output.txt ./




