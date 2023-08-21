from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.conf import job_cache

# Get the path of this file
path = Path(__file__)

# Create a test client
client = TestClient(app)


def test_status():
    print('Test that the models endpoint returns a 200 status code')
    response = client.get('/models')
    print(response)
    assert response.status_code == 200


def test_num_models():
    print('Test that the models endpoint returns a 200 status code and a single model')
    response = client.get('/models')
    assert response.status_code == 200
    assert len(response.json()['model']) == 1
