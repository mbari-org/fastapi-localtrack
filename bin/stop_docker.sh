#!/usr/bin/env bash
# Stop all docker images and remove the networks
# Run with ./stop_docker.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"

cd $BASE_DIR

# Get the short version of the hash of the commit
git_hash=$(git log -1 --format=%h)

# Stop both prod/dev stacks
GIT_VERSION="${git_hash}" COMPOSE_PROJECT_NAME=fastapi-localtrack-dev docker-compose --env-file .env.dev -f compose.dev.yml down --remove-orphans
GIT_VERSION="${git_hash}" COMPOSE_PROJECT_NAME=fastapi-localtrack docker-compose --env-file .env -f compose.yml down --remove-orphans

# Remove the networks
docker network rm dev-minio-net
docker network rm minio-net
