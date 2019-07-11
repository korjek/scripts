#!/bin/bash
if [[ "$#" -ne 3 ]]; then
    echo "Usage: build_and_upload_dummy_docker.sh ART_ENV ENV SITE"
    echo "Example: build_and_upload_dummy_docker.sh test test kiev"
    exit
fi

env=$2
art_env=$1
site=$3
env_port=
art_env_suffix="dummy"
if [ "$env" == "test" ]; then
    env_port=5000
elif [ "$env" == "uat" ]; then
    env_port=5001
elif [ "$env" == "prod" ]; then
    env_port=5002
else
    echo "Couldn't determine ENV. Exiting..."
    exit 1
fi

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

DATE=`date '+%Y%m%d_%H%M%S'`
cat >./$DATE <<EOL
$DATE
EOL

cat >./Dockerfile <<EOL
FROM scratch
COPY $DATE /
EOL

docker build -t dsl$art_env_suffix.$site.elex.be:$env_port/dummy/dummy:$DATE .
echo -e "Logging to dsl$art_env_suffix.$site.elex.be.\n Type your trigramm"
read username
echo -e "Type your pass"
read -s password


docker login --username=$username --password=$password  dsl$art_env_suffix.$site.elex.be:$env_port > /dev/null 2>&1

docker push dsl$art_env_suffix.$site.elex.be:$env_port/dummy/dummy:$DATE

echo -e "Image is pushed to dsl$art_env_suffix.$site.elex.be:$env_port/dummy/dummy:$DATE"

docker logout dsl$art_env_suffix.$site.elex.be:$env_port > /dev/null 2>&1
