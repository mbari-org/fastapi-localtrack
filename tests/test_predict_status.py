from pathlib import Path
import time
from fastapi.testclient import TestClient
from app.main import app
from tests.conf import test_video_url_1sec

# Get the path of a test model
image_path = Path(__file__).parent / 'data' / 'model.pt'

# Clear the test cache and create a test client
job_cache.clear()
client = TestClient(app)


def test_predict_queued():
    print('Test that the prediction reports A QUEUED status')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url_1sec,
        'metadata': 'test'
    })
    print(f'Received response {response.json()}')
    assert response.status_code == 200

    job_id = response.json()['job_id']
    print(f'Job is {job_id}')

    response = client.get(f"/status/{job_id}")
    print(f'Received status {response.json()}')

    assert response.status_code == 200
    assert response.json()['status'] == 'QUEUED'
    job_cache.clear()


def test_predict_running():
    print('Test that the prediction reports A RUNNING status')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url_1sec,
        'metadata': 'test'
    })
    print(f'Received response {response.json()}')
    assert response.status_code == 200

    job_id = response.json()['job_id']
    print(f'Job is {job_id}')

    # Wait for 5 seconds to allow the job to start
    time.sleep(5)

    response = client.get(f"/status/{job_id}")
    print(f'Received status {response.json()}')

    assert response.status_code == 200
    assert response.json()['status'] == 'RUNNING'


def test_predict_conflict():
    print('Test that the prediction for yolov5 returns a 409 status code if the video is already being processed')
    # Run the prediction twice
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url_1sec,
        'metadata': 'test'
    })
    print(f'Received metadata {response.json()}')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url_1sec,
        'metadata': 'test'
    })
    # Remove the job from the cache
    job_cache.remove_job(f'yolov5s-{test_video_url_1sec}')
    assert response.status_code == 409