#!/bin/bash

# Install MySQL client
echo "Mysql client installing..."
# sudo apt update -qq && apt install -qq -y mysql-client-8.0 unzip
sudo yum install https://dev.mysql.com/get/mysql80-community-release-el7-3.noarch.rpm
sudo yum install -y mysql-community-client

# Connect to MySQL server
echo "Downloading review.csv"

# Get MySQL and Mongodb credentials
wget http://***/database_credentials.py
# password of mysql and mongodb databae should be export in this python file ----- to be confirmed
python database_credentials.py --keyfile ***.pem

# Download reviews from Mysql server 
mysql -u root -h $MYSQL_IP -e "select * from DBProject.review" | tail -n +2 > review.csv

# Install Mongodb tools
echo "Mongo-tools installing..."
sudo yum install https://repo.mongodb.org/yum/amazon/2/mongodb-org/4.4/x86_64/RPMS/mongodb-database-tools-100.0.0.x86_64.rpm

# Download books from Mongodb server
echo "Downloading book.json"
mongoexport --collection=books --out=books.json $MONGO_URL

# HDFS upload
echo "Uploading review.csv & books.json to hdfs"
hdfs dfs -mkdir -p /DBProject
hdfs dfs -put review.csv /DBProject/review.csv
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
hdfs dfs -rm -r /DBProject/correlation_output
hdfs dfs -rm -r /DBProject/tfidf_output.txt
sudo pip install findspark
python correlation.py
python tfidf.py

# HDFS download
hdfs dfs -get /DBProject/tfidf_output ./
hdfs dfs -get /DBProject/correlation_output ./




