#!/usr/bin/env bash
# Build the docker images and start the compose stack
# Run with ./build.sh <optional .env file>
# If no .env file is provided, then .env is used
if [ -z "$1" ]
then
  ENV_FILE=.env
else
  ENV_FILE=$1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"

# Get the short version of the hash of the commit
git_hash=$(git log -1 --format=%h)

docker network inspect minio-net >/dev/null 2>&1 || \
docker network create minio-net
GIT_VERSION="${git_hash}" docker-compose up --remove-orphans --build -d --env-file $ENV_FILE