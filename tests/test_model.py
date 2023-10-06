# fastapi-localtrack, Apache-2.0 license
# Filename: tests/test_model.py
# Description: Tests for the models endpoint

from pathlib import Path
from urllib.parse import urlparse
from urllib import request
import time

import boto3
import yaml
from fastapi.testclient import TestClient
import pytest
import os
import signal

from app import logger

logger = logger.create_logger_file(Path(__file__).parent, __file__)

global client


@pytest.fixture
def startup():
    global client
    os.environ['MINIO_ENDPOINT_URL'] = 'http://localhost:7000'
    os.environ['MINIO_ACCESS_KEY'] = 'localtrack'
    os.environ['MINIO_SECRET_KEY'] = 'ReplaceMePassword'
    os.environ['MODEL_DIR'] = (Path.home() / 'fastapi_localtrack_dev' / 'models').as_posix()
    os.environ['DATABASE_DIR'] = (Path.home() / 'fastapi_localtrack_dev' / 'sqlite_data').as_posix()
    os.environ['YAML_PATH'] = (Path(__file__).parent.parent / 'config.yml').as_posix()
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
    model_path = Path(os.environ['MODEL_DIR'])

    # Grab a new model from the config.yaml file and copy it to the models directory
    with open(Path(__file__).parent.parent / 'config.yml', 'r') as f:
        config = yaml.safe_load(f)
        s3_new_model = config['aws_public']['model']
        new_model = f'new{Path(s3_new_model).name}'
        local_file_path = model_path / new_model

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

    # Delay to allow the model to be discovered which happens every 30 seconds
    time.sleep(35)

    # Check if the new model is in the models endpoint
    response = client.get('/models')
    assert response.status_code == 200
    models = response.json()['model']
    assert len(models) == 2
    assert 'new' in models[1] # The new model should be the second model in the list

    # Clean-up

    # Remove the new model
    local_file_path.unlink()

    # Remove the new model from the bucket
    s3 = boto3.client('s3',
                        endpoint_url=os.environ['MINIO_ENDPOINT_URL'],
                        aws_secret_access_key=os.environ['MINIO_SECRET_KEY'],
                        aws_access_key_id=os.environ['MINIO_ACCESS_KEY'])
    s3.delete_object(Bucket=config['minio']['root_bucket'], Key=f"{config['minio']['model_prefix']}/{new_model}")
