#!/usr/bin/env bash

# Get the directory of this script and its parent
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PARENT_DIR="$(dirname "$DIR")"

conda activate fastapi-accutrack

# Run the python daemon module in the background and redirect output to a log file
cd $PARENT_DIR/src && export AWS_DEFAULT_PROFILE=minio-accutrack && python3 -m daemon
