#!/usr/bin/env bash
# Run development stack: nginx, minio, fastapi, daemon
# This fetches a few videos to serve in the default nginx/video directory and starts the minio server
# fastapi server, and daemon are run locally outside the containers
# Get the directory of this script and the base directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"
cd $BASE_DIR

# Get the short version of the hash of the commit
git_hash=$(git log -1 --format=%h)

# Setup the dev network and run the development compose stack
docker network inspect dev-minio-net >/dev/null 2>&1 || \
docker network create dev-minio-net
GIT_VERSION="${git_hash}" docker-compose --env-file .env.dev -f compose.dev.yml up -d

# Wait for the nginx server to start
echo "Wait for the nginx server to start"
until $(curl --output /dev/null --silent --head --fail http://localhost:8090); do
    printf '.'
    sleep 5
done

# Export the environment variables in the .env.dev file
export $(grep -v '^#' $BASE_DIR/.env.dev |  xargs)

# Replace ${HOME} with the actual home directory and export needed variables
DATA_DIR=${DATA_DIR/\$\{HOME\}/$HOME}
export DATABASE_DIR=${DATA_DIR}/sqlite_data # Path to local database
export MODEL_DIR=${DATA_DIR}/models # Path to models

# Build nginx
docker build -t mbari/nginx -f containers/nginx/Dockerfile .

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

# Fetch a model
mkdir -p ${MODEL_DIR}
if [ ! -f ${MODEL_DIR}/MegadetectorTest ]; then
  curl -o ${MODEL_DIR}/MegadetectorTest https://902005-public.s3.us-west-2.amazonaws.com/models/Megadetector/best.pt
fi

username=$(grep MINIO_ACCESS_KEY .env.dev | cut -d '=' -f2)
password=$(grep MINIO_SECRET_KEY .env.dev | cut -d '=' -f2)

echo "Nginx server running at http://localhost:8090"
echo "Minio server running at http://localhost:7000" username: $username password: $password
echo "FastAPI server running at http://localhost:8001"
echo "FastAPI docs running at http://localhost:8001/docs"

# Run the daemon and the api server
export PYTHONPATH=$BASE_DIR/src
pkill -f "python -m daemon"
pkill -f "uvicorn main:app"
cd $BASE_DIR/src && python -m daemon > daemon.log 2>&1 &
cd $BASE_DIR/src/app && uvicorn main:app --port 8001 --reload > app.log 2>&1 &
