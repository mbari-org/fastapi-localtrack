from pathlib import Path
import time
from fastapi.testclient import TestClient
from app.main import app
from app.conf import job_cache

# Get the path of this file
path = Path(__file__)

# Get the path of a test model
image_path = path.parent / 'data' / 'model.pt'

# Test video url hosted on localhost; Requires running the test/runserver.sh script first
test_video_url = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec.mp4'
test_video_url_missing = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec_missing.mp4'

# Clear the test cache and create a test client
job_cache.clear()
client = TestClient(app)


def test_predict_queued():
    print('Test that the prediction reports A QUEUED status')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url,
        'metadata': 'test'
    })
    print(f'Received response {response.json()}')
    assert response.status_code == 200

    job_uuid = response.json()['job_uuid']
    print(f'Job is {job_uuid}')

    response = client.get(f"/status/{job_uuid}")
    print(f'Received status {response.json()}')

    assert response.status_code == 200
    assert response.json()['status'] == 'QUEUED'
    job_cache.clear()


def test_predict_running():
    print('Test that the prediction reports A RUNNING status')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url,
        'metadata': 'test'
    })
    print(f'Received response {response.json()}')
    assert response.status_code == 200

    job_uuid = response.json()['job_uuid']
    print(f'Job is {job_uuid}')

    # Wait for 5 seconds to allow the job to start
    time.sleep(5)

    response = client.get(f"/status/{job_uuid}")
    print(f'Received status {response.json()}')

    assert response.status_code == 200
    assert response.json()['status'] == 'RUNNING'


def test_predict_conflict():
    print('Test that the prediction for yolov5 returns a 409 status code if the video is already being processed')
    # Run the prediction twice
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url,
        'metadata': 'test'
    })
    print(f'Received metadata {response.json()}')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url,
        'metadata': 'test'
    })
    # Remove the job from the cache
    job_cache.remove_job(f'yolov5s-{test_video_url}')
    assert response.status_code == 409