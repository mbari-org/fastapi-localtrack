#!/usr/bin/env bash
# Run tests
# Run with ./run_test.sh
set -x
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"
cd $BASE_DIR
export PYTHONPATH=$BASE_DIR/src:$BASE_DIR

# Run the development stack
./bin/run_dev.sh

# Kill the api server if it is running as the tests will run the api server
pkill -f "uvicorn main:app"

# Export the environment variables in the .env.dev file
export $(grep -v '^#' $BASE_DIR/.env.dev |  xargs)

# Run all tests
pytest

# Run the predict tests individually
# pytest -s -v tests/test_predict.py::test_predict_invalid_model
# pytest -s -v tests/test_predict.py::test_predict_sans_metadata
# pytest -s -v tests/test_predict.py::test_predict_invalid_url
# pytest -s -v tests/test_predict.py::test_predict_queued
# pytest -s -v tests/test_predict.py::test_predict_running
# pytest -s -v tests/test_predict.py::test_predict_sans_metadata