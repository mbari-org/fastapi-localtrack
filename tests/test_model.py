# fastapi-localtrack, Apache-2.0 license
# Filename: tests/test_model.py
# Description: Tests for the models endpoint

from pathlib import Path
from fastapi.testclient import TestClient
from app.job import init_db
from tests.conf.setup import init_credentials, run_minio
import pytest
import os
import signal
import time


@pytest.fixture
def startup():
    global client
    global session_maker

    # Reset the database
    session_maker = init_db(Path.cwd() / 'db', reset=True)

    # Initialize the credentials - this is needed before starting the app to set the environment variables
    init_credentials()

    # Start minio
    run_minio()

    from app.main import app
    client = TestClient(app)


@pytest.fixture
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)


def test_status(startup, shutdown):
    print('Test that the models endpoint returns a 200 status code')
    response = client.get('/models')
    print(response)
    assert response.status_code == 200


def test_num_models(startup, shutdown):
    print('Test that the models endpoint returns a 200 status code and a single model')
    response = client.get('/models')
    assert response.status_code == 200
    assert len(response.json()['model']) == 1
