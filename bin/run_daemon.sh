#!/usr/bin/env bash
# Run development stack: nginx, minio, fastapi, daemon
# This fetches a few videos to serve in the default nginx/video directory and starts the minio server
# fastapi server, and daemon are run locally outside the containers
# Get the directory of this script and the base directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"
cd $BASE_DIR

if [ "$1" == "build" ]; then
  echo "Build the docker images"
  ./bin/build_docker.sh
fi

# Get the short version of the hash of the commit
git_hash=$(git log -1 --format=%h)

# Setup the dev network and run the development compose stack
docker network inspect dev-minio-net >/dev/null 2>&1 || \
docker network create dev-minio-net
GIT_VERSION="${git_hash}" docker-compose -f compose.dev.yml up -d

# Wait for the nginx server to start
echo "Wait for the nginx server to start"
until $(curl --output /dev/null --silent --head --fail http://localhost:8090); do
    printf '.'
    sleep 5
done

# Export the environment variables in the .env.dev file
export $(grep -v '^#' $BASE_DIR/.env.dev |  xargs)

# Replace ${HOME} with the actual home directory
DATA_DIR=${DATA_DIR/\$\{HOME\}/$HOME}
export DATABASE_DIR=${DATA_DIR}/db

echo "Fetch a few videos to serve in the default nginx/video directory"
mkdir -p ${DATA_DIR}/nginx/video
# Fetch each video if it doesn't already exist
declare -a video_urls=(
  "https://902005-public.s3.us-west-2.amazonaws.com/video/10frame/V4361_20211006T162656Z_h265_10frame.mp4"
  "https://902005-public.s3.us-west-2.amazonaws.com/video/1sec/V4361_20211006T162656Z_h265_1sec.mp4"
  "https://902005-public.s3.us-west-2.amazonaws.com/video/1min/V4361_20211006T162656Z_h265_1min.mp4"
)
for url in "${video_urls[@]}"
do
  file_name=$(basename $url)
  if [ ! -f ${DATA_DIR}/nginx/video/$file_name ]; then
    curl -o ${DATA_DIR}/nginx/video/$file_name  $url
  fi
done

echo "Nginx server running at http://localhost:8090"
echo "Minio server running at http://localhost:7000"

### Run the daemon and the api server
export PYTHONPATH=$BASE_DIR/src:$BASE_DIR/tests
pkill -f "python -m daemon"
cd $BASE_DIR/src && python -m daemon