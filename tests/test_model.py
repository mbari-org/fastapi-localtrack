# fastapi-localtrack, Apache-2.0 license
# Filename: tests/test_model.py
# Description: Tests for the models endpoint

from pathlib import Path
from urllib.parse import urlparse
from urllib import request
import time
import yaml
from fastapi.testclient import TestClient
import pytest
import os
import signal

from app import logger

logger = logger.create_logger_file(Path(__file__).parent, __file__)


@pytest.fixture
def startup():
    global client

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


def test_model_discovery(startup, shutdown):
    print('Test that a new model shows up in the models endpoint')

    # Grab a new model from the config.yaml file and copy it to the models directory
    with open(Path(__file__).parent.parent / 'config.yml', 'r') as f:
        config = yaml.safe_load(f)
        s3_new_model = config['aws_public']['model']
        local_file_path = Path(config['monitors']['models']['path']) / f'new{Path(s3_new_model).name}'

        if not local_file_path.parent.exists():
            local_file_path.parent.mkdir(parents=True)

        if not local_file_path.exists():
            # Download the new model using url retrieve
            parsed_uri = urlparse(s3_new_model)
            s3_url = f'https://{parsed_uri.netloc}.s3.amazonaws.com/{parsed_uri.path[1:]}'

            # Download the object from S3 to the local file path
            request.urlretrieve(s3_url, local_file_path.as_posix())
            print(f'{s3_url} has been downloaded to {local_file_path}')
        else:
            print(f'{local_file_path} already exists. Skipping download.')

    # Delay to allow the model to be discovered which happens every 15 seconds in test
    time.sleep(20)

    # Check if the new model is in the models endpoint
    response = client.get('/models')
    assert response.status_code == 200
    models = response.json()['model']
    assert len(models) == 2
    assert 'new' in models[1]