from pathlib import Path
from fastapi.testclient import TestClient
from app.job.cache import JobCache
from app.job import JobStatus, JobIndex
from app.main import app
from app.conf import job_cache

client = TestClient(app)

def test_health():
    # The health endpoint should return a 200 status code
    response = client.get('/health')
    assert response.status_code == 200



