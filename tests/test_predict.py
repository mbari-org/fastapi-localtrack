# fastapi-localtrack, Apache-2.0 license
# Filename: tests/test_predict.py
# Description: Tests for the predict endpoint

import time
from pathlib import Path
import pytest
import os
import signal
from fastapi.testclient import TestClient

from app.logger import info
from app import logger

test_video_url = 'http://localhost:8090/video/V4361_20211006T162656Z_h265_10frame.mp4'
test_video_url_missing = 'http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec_missing.mp4'

global client

DAEMON_AVAILABLE = True
logger = logger.create_logger_file(Path(__file__).parent / 'logs', __file__)

fake_metadata = {
    "image_uri_ecr": "fake_image_uri_ecr",
    "instance_type": "fake_instance_type",
}


@pytest.fixture
def startup():
    global client
    # As defined in .env.dev
    db_path = Path.home() / 'fastapi_localtrack_dev' / 'sqlite_data'
    os.environ['MINIO_ENDPOINT_URL'] = 'http://localhost:7000'
    os.environ['MINIO_ACCESS_KEY'] = 'localtrack'
    os.environ['MINIO_SECRET_KEY'] = 'ReplaceMePassword'
    os.environ['DATABASE_DIR'] = db_path.as_posix()
    from app.main import app
    client = TestClient(app)
    yield


@pytest.fixture
def shutdown():
    print('Shutting down the app')
    os.kill(os.getpid(), signal.SIGINT)


def get_example_model():
    """
    Get the first model from the models endpoint
    :return: model name
    """
    # Get the first model from the models endpoint - there should only be one in test
    response = client.get('/models')
    assert response.status_code == 200
    models = response.json()['model']
    assert len(models) == 1
    return models[0]


def test_predict_invalid_url(startup, shutdown):
    info('Test that the prediction for a bad or missing video url returns a 404 status code')
    example_model = get_example_model()
    response = client.post('/predict', json={
        'model': example_model,
        'video': test_video_url_missing,
    })
    assert response.status_code == 404


def test_predict_invalid_model(startup, shutdown):
    info('Test that the prediction for an invalid model returns a 404 status code')
    response = client.post('/predict', json={
        'model': 'yolov5sfoobar',
        'video': test_video_url,
    })
    assert response.status_code == 404


@pytest.mark.skipif(not DAEMON_AVAILABLE, reason="This test is excluded because it requires a daemon process")
def test_predict_sans_metadata(startup, shutdown):
    info('Test that the prediction for yolov5 returns a 200 status code')
    # Get the first model from the models endpoint
    response = client.get('/models')
    assert response.status_code == 200
    models = response.json()['model']
    example_model = models[0]

    response = client.post('/predict', json={
        'model': example_model,
        'video': test_video_url
    })
    assert response.status_code == 200
    job_id = response.json()['job_id']
    info(f'Job is {job_id}')

    # Wait for 60 seconds to allow the job to finish
    time.sleep(60)

    response = client.get(f"/status_by_id/{job_id}")
    info(f'Received status {response.json()} for job {job_id}')

    assert response.status_code == 200
    response_json = response.json()
    assert response_json['status'] == 'SUCCESS'

    # Verify that we can get the results which are available via s3 in the metadata field s3_path
    assert response_json['s3_path'] is not None


@pytest.mark.skipif(not DAEMON_AVAILABLE, reason="This test is excluded because it requires a daemon process")
def test_predict_metadata(startup, shutdown):
    info('Test that the prediction for yolov5 returns a 200 status code')
    # Get the first model from the models endpoint
    response = client.get('/models')
    assert response.status_code == 200
    models = response.json()['model']
    example_model = models[0]

    response = client.post('/predict', json={
        'model': example_model,
        'video': test_video_url,
        'metadata': fake_metadata
    })
    assert response.status_code == 200
    job_id = response.json()['job_id']
    info(f'Job is {job_id}')

    # Wait for 60 seconds to allow the job to finish
    time.sleep(60)

    response = client.get(f"/status_by_id/{job_id}")
    info(f'Received status {response.json()} for job {job_id}')

    assert response.status_code == 200
    assert response.json()['status'] == 'SUCCESS'

    # Verify that the metadata was passed through correctly
    final_metadata = response.json()['metadata']
    assert response.json()['metadata'] == final_metadata


@pytest.mark.skipif(not DAEMON_AVAILABLE, reason="This test is excluded because it requires a daemon process")
def test_predict_queued(startup, shutdown):
    info('Test that the prediction reports A QUEUED status')
    example_model = get_example_model()
    response = client.post('/predict', json={
        'model': example_model,
        'video': test_video_url
    })
    info(f'Received response {response.json()}')
    assert response.status_code == 200

    job_id = response.json()['job_id']
    info(f'Job is {job_id}')

    response = client.get(f"/status_by_id/{job_id}")
    info(f'Received status {response.json()} for job {job_id}')

    assert response.status_code == 200
    assert response.json()['status'] == 'QUEUED'

    # Wait for 50 seconds to allow the job to finish before running the next test
    time.sleep(50)


@pytest.mark.skipif(not DAEMON_AVAILABLE, reason="This test is excluded because it requires a daemon process")
def test_predict_running(startup, shutdown):
    info('Test that the prediction reports A RUNNING status and metadata following submission')
    example_model = get_example_model()

    response = client.post('/predict', json={
        'model': example_model,
        'video': test_video_url,
        'metadata': fake_metadata
    })
    info(f'Received response {response.json()}')
    assert response.status_code == 200

    job_id = response.json()['job_id']
    info(f'Job is {job_id}')

    # Wait for 10 seconds to allow the job to start
    time.sleep(10)

    response = client.get(f"/status_by_id/{job_id}")
    info(f'Received status {response.json()} for job {job_id}')

    assert response.status_code == 200
    assert response.json()['status'] == 'RUNNING'

    # Wait for 50 seconds to allow the job to finish
    time.sleep(50)
