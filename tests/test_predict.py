from pathlib import Path
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


def test_predict():
    print('Test that the prediction for yolov5 returns a 200 status code')
    response = client.post('/predict', json={
        'model': 'yolov5s',
        'video': test_video_url,
        'metadata': 'test'
    })
    print(f'Received metadata {response.json()}')
    # Remove the job from the cache
    job_cache.remove_job(f'yolov5s-{test_video_url}')
    assert response.status_code == 200

