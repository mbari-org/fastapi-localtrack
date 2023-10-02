#!/usr/bin/env bash
# Run production stack: nginx, minio, fastapi, daemon
# Run with ./run_prod.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"

# Build the docker images
./bin/build_docker.sh

# Export the environment variables in the .env.dev file
export $(grep -v '^#' $BASE_DIR/.env |  xargs)

# Get the short version of the hash of the commit
git_hash=$(git log -1 --format=%h)

# Run the production compose stack
docker network inspect minio-net >/dev/null 2>&1 || \
docker network create minio-net
GIT_VERSION="${git_hash}" docker-compose -f compose.yml up -d