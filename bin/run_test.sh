#!/usr/bin/env bash
# Run tests
# Run with ./run_test.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(cd "$(dirname "${SCRIPT_DIR}/../.." )" && pwd )"
cd $BASE_DIR
export PYTHONPATH=$BASE_DIR/src:$BASE_DIR/tests

# Run the development stack
./bin/run_dev.sh

# Export the environment variables in the .env.dev file
export $(grep -v '^#' $BASE_DIR/.env.dev |  xargs)

# Run all tests
#pytest

# Run the tests individually

# Model tests
pytest -s -v tests/test_model.py::test_model_discovery
pytest -s -v tests/test_model.py::test_num_models
pytest -s -v tests/test_model.py::test_stats

# Health tests
pytest -s -v tests/test_health.py::test_health

# Database tests
pytest -s -v tests/test_database.py::test_add_one_media
pytest -s -v tests/test_database.py::test_failed_status
pytest -s -v tests/test_database.py::test_num_completed
pytest -s -v tests/test_database.py::test_num_failed
pytest -s -v tests/test_database.py::test_pydantic_sqlalchemy
pytest -s -v tests/test_database.py::test_queued_status
pytest -s -v tests/test_database.py::test_running_status
pytest -s -v tests/test_database.py::test_update_one_media

# Predict tests - these take a while to run
# pytest -s -v tests/test_predict.py::test_predict_invalid_model
# pytest -s -v tests/test_predict.py::test_predict_sans_metadata
# pytest -s -v tests/test_predict.py::test_predict_invalid_url
# pytest -s -v tests/test_predict.py::test_predict_queued
# pytest -s -v tests/test_predict.py::test_predict_running
# pytest -s -v tests/test_predict.py::test_predict_sans_metadata