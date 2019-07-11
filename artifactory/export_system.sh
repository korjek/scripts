#!/bin/bash
env='dummy'
site=

if [[ "$#" -ne 5 ]]; then
    echo "Usage: run_aql.sh ENV SITE JSON_FILE USERNAME PASS"
    echo "Example: run_aql.sh test kiev find_by_name.json admin password"
    exit
fi

if [[ $1 == "test" ]]; then
    env='-test'
elif [[ $1 == "uat" ]]; then
    env='-uat'
elif [[ $1 == "prod" ]]; then
    env=''
else 
    echo "Uknowm environment"
    exit
fi
site=$2
json=$3
username=$4
pass=$5

curl -X POST "https://dsl${env}.${site}.elex.be/artifactory/api/export/system" -T ${json} -u ${4}:${5}
