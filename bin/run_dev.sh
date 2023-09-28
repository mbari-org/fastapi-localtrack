#!/usr/bin/env bash

# Get the directory of this script and the base directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"

echo "Build the docker images and start the compose stack"
$BASE_DIR/bin/build_docker.sh
$BASE_DIR/bin/run_docker.sh $BASE_DIR/.env.dev

echo "Nginx server running at http://localhost:8090"

echo "Fetch a few videos to serve in the default nginx/video directory"
mkdir -p $HOME/fastapi_localtrack/nginx/video
pushd $HOME/fastapi_localtrack/nginx/video
curl -O https://902005-public.s3.us-west-2.amazonaws.com/video/10frame/V4361_20211006T162656Z_h265_10frame.mp4
curl -O https://902005-public.s3.us-west-2.amazonaws.com/video/1sec/V4361_20211006T162656Z_h265_1sec.mp4
curl -O https://902005-public.s3.us-west-2.amazonaws.com/video/1min/V4361_20211006T162656Z_h265_1min.mp4
popd

## Export the environment variables in the .env.dev file
export $(grep -v '^#' $BASE_DIR/.env.dev | xargs)

## Run the daemon and the api server
conda activate fastapi-microtrack
export PYTHONPATH=$BASE_DIR/src:$BASE_DIR/tests
cd $BASE_DIR/src/app
python -m daemon &
uvicorn main:app --reload