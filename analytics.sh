#!/bin/bash

# Install MySQL client
echo "Mysql client installing..."
apt update && apt install mysql-client-8.0 unzip

# Connect to MySQL server
echo "Connecting to the Mysql Server..."
export MYSQL_PWD="yD5dMepw7XpwEWn8"
# Download reviews from Mysql server 
mysql -u root -h 13.250.30.159 -p MYSQL_PWD -e "select * from DBProject.review" | tail -n +2 > review.tsv

# Install Mongodb tools
echo "Mongo-tools installing..."
apt install mongo-tools
# Download books from Mongodb server
mongoexport --collection=books --out=books.json "mongodb://DBProjectUser:NcMcZDU9Sqw49nJT@54.255.154.236:27017/DBProject?authSource=DBProject"

