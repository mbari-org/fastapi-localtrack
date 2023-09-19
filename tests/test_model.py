from fastapi.testclient import TestClient
from tests.conf.setup import init_credentials
init_credentials()
from app.main import app

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
