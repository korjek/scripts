#!/bin/bash
if [[ "$#" -ne 2 ]]; then
    echo "Usage: get_job_status.sh ART_ENV SITE"
    echo "Example: get_job_status.sh test kiev"
    exit
fi

art_env=$1
site=$2
art_env_suffix="dummy"

if [ "$art_env" == "test" ]; then
    art_env_suffix="-test"
elif [ "$art_env" == "-uat" ]; then
    art_env_suffix="uat"
elif [ "$art_env" == "prod" ]; then
    art_env_suffix=""
else
    echo "Couldn't determine ENV. Exiting..."
    exit 1
fi

echo -e "Logging to dsl$art_env_suffix.$site.elex.be.\n Type your trigramm"
read username
echo -e "Type your pass"
read -s password


curl -X GET -u$username:$password  https://dsl$art_env_suffix.$site.elex.be/artifactory/api/tasks > tasks.lst
