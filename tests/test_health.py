# fastapi-localtrack, Apache-2.0 license
# Filename: tests/test_health.py
# Description: Test health endpoint

from pathlib import Path

import yaml

from app.job import init_db
from fastapi.testclient import TestClient

import pytest
import os
import signal
from app import logger

logger = logger.create_logger_file(Path(__file__).parent, __file__)


@pytest.fixture
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)


global client
global session_maker

fake_metadata = {
    "image_uri_ecr": "fake_image_uri_ecr",
    "instance_type": "fake_instance_type",
}


@pytest.fixture
def startup():
    global client
    global session_maker
    # As defined in .env.dev
    db_path = Path.home() / 'fastapi_localtrack_dev' / 'sqlite_data'
    os.environ['MINIO_ENDPOINT_URL'] = 'http://localhost:7000'
    os.environ['MINIO_ACCESS_KEY'] = 'localtrack'
    os.environ['MINIO_SECRET_KEY'] = 'ReplaceMePassword'
    os.environ['DATABASE_DIR'] = db_path.as_posix()
    session_maker = init_db(db_path, reset=True) # Reset the database
    from app.main import app
    client = TestClient(app)


@pytest.fixture
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)


def test_health(startup, shutdown):
    # The health endpoint should return a 200 status code
    response = client.get('/health')
    assert response.status_code == 200
