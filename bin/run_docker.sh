#!/usr/bin/env bash
# Build the docker images and start the compose stack
# Run with ./run_docker.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"

# Get the short version of the hash of the commit
git_hash=$(git log -1 --format=%h)

docker network inspect minio-net >/dev/null 2>&1 || \
docker network create minio-net
GIT_VERSION="${git_hash}" docker-compose -f compose.yml up -d