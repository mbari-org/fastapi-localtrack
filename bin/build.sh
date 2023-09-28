#!/usr/bin/env bash
# Build the docker images
# Run with ./build.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"

# Get the short version of the hash of the commit
git_hash=$(git log -1 --format=%h)

#cd $BASE_DIR && docker build \
--build-arg IMAGE_URI=mbari/fastapi-localtrack:"${git_hash}"  \
--network host \
-t mbari/fastapi-localtrack:"${git_hash}" \
-f containers/api/Dockerfile .

cd $BASE_DIR && docker build \
--build-arg IMAGE_URI=mbari/fastapi-localtrack-daemon:"${git_hash}"  \
--network host \
-t mbari/fastapi-localtrack-daemon:"${git_hash}" \
-f containers/daemon/Dockerfile .

docker network inspect minio-net >/dev/null 2>&1 || \
docker network create minio-net
docker-compose up