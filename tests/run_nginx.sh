#!/usr/bin/env bash

# Build and run the docker container for the nginx server
IMAGE_NAME=mbari/nginx

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Build the docker image
pushd $DIR/nginx && docker build -t $IMAGE_NAME --platform linux/arm64/v8 . && popd

# If the container is already running, stop it
if [ "$(docker ps -q -f name=microtrack-nginx)" ]; then
    docker stop microtrack-nginx
fi

# Run the container in the background with port 8090 exposed and the volume mounted to the current directory and remove the container when it exits
docker run --rm -d -p 8090:80 -v $DIR/data:/data:ro --name microtrack-nginx $IMAGE_NAME

echo "Nginx server running at http://localhost:8090"