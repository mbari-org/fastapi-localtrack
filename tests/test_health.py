# fastapi-accutrack, Apache-2.0 license
# Filename: tests/test_health.py
# Description: Test health endpoint

import time
from pathlib import Path
from conf import init_credentials, run_minio

# Initialize the credentials - this is needed before starting the app to set the environment variables
init_credentials()

from app.job import init_db
from fastapi.testclient import TestClient

import pytest
import os
import signal

@pytest.fixture
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)

global session_maker

fake_metadata = {
    "image_uri_ecr": "fake_image_uri_ecr",
    "instance_type": "fake_instance_type",
}

@pytest.fixture
def startup():
    global client
    global session_maker

    # Initialize the credentials - this is needed before starting the app to set the environment variables
    init_credentials()

    # Start minio
    run_minio()

    session_maker = init_db(Path.cwd() / 'db', reset=True)

    from app.main import app
    client = TestClient(app)

@pytest.fixture
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)

def test_health(startup, shutdown):
    # The health endpoint should return a 200 status code
    response = client.get('/health')
    assert response.status_code == 200
