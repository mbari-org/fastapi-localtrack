#!/usr/bin/env bash
# Stop all docker images and remove the networks
# Run with ./stop_docker.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"

cd $BASE_DIR
docker-compose --env-file .env.dev -f compose.dev.yml down
docker-compose --env-file .env -f compose.yml down

# Remove the networks
docker network rm dev-minio-net
docker network rm minio-net