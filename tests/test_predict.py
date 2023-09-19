import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.job import init_db, Job2
from app.logger import CustomLogger
from app.main import app, session_maker
from deepsea_ai.database.job.database_helper import get_num_failed, get_num_completed,  json_b64_encode, get_status

# Get the path of this file
path = Path(__file__)

# Get the path of a test model
image_path = path.parent / 'data' / 'model.pt'

# Test video url hosted on localhost; Requires running the test/runserver.sh script first
test_video_url = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec.mp4'
test_video_url_missing = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec_missing.mp4'

CustomLogger(output_path=Path.cwd() / 'logs', output_prefix=__name__)

client = TestClient(app)

global session_maker


@pytest.fixture
def setup_database():
    global session_maker
    # Reset the database
    session_maker = init_db(Path.cwd() / 'db', reset=True)


def test_predict_invalid_url():
    print('Test that the prediction for a bad or missing video url returns a 404 status code')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url_missing,
    })
    assert response.status_code == 404


def test_predict_invalid_model():
    print('Test that the prediction for an invalid model returns a 404 status code')
    response = client.post('/predict', json={
        'model': 'yolov5sfoobar',
        'video': test_video_url,
    })
    assert response.status_code == 404


def test_predict(setup_database):
    print('Test that the prediction for yolov5 returns a 200 status code')
    data = {"model": "yolov5s"}
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url
    })
    assert response.status_code == 200
    job_id = response.json()['job_id']
    print(f'Job is {job_id}')

    # Sleep for 3 seconds to allow the job to start
    time.sleep(3)

    # Check every 5 seconds to see if the job is complete and timeout after 10 tries
    num_tries = 0
    while num_tries < 10:
        print('Waiting for job to complete')
        with session_maker.begin() as db:
            # Get the job from the database by the job_id
            job = db.query(Job2).filter(Job2.id == job_id).first()
            status = get_status(job)
            print(f'Job status: {status}')
            if status == 'SUCCESS':
                break
        time.sleep(5)

        num_tries += 1
        assert num_tries < 3
        assert status == 'SUCCESS'