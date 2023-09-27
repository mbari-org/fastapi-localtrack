#!/usr/bin/env bash

# Get the directory of this script and its parent
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PARENT_DIR="$(dirname "$DIR")"

conda activate fastapi-localtrack

# Run the python daemon module
cd $PARENT_DIR/src && export AWS_DEFAULT_PROFILE=minio-localtrack && python3 -m daemon
