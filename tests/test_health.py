from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    # The health endpoint should return a 200 status code
    response = client.get('/health')
    assert response.status_code == 200
