from pathlib import Path
from fastapi.testclient import TestClient
from app.job.cache import JobCache
from app.job import JobStatus, JobIndex
from app.main import app
from app.conf import job_cache

client = TestClient(app)

def test_job_insert():
    jc = JobCache(Path.cwd())
    name = "strongsort-yolov5-mbari315k-DocRicketts dive 1373 with mbari315k model"
    jc.set_job(name, JobStatus.UNKNOWN, ["vid1.mp4"], JobStatus.RUNNING)
    f = jc.get_job_by_name(name)
    assert f[JobIndex.NAME] == name


def test_job_remove():
    jc = JobCache(Path.cwd())
    name = "strongsort-yolov5-mbari315k-DocRicketts dive 1373 with mbari315k model"
    jc.set_job(name, JobStatus.UNKNOWN, ["vid1.mp4"], JobStatus.RUNNING)
    jc.remove_job(name)
    f = jc.get_job_by_name(name)
    # Should be false if the job was removed
    assert f == False


def test_job_status_running():
    jc = JobCache(Path.cwd())
    name = "strongsort-yolov5-mbari315k-DocRicketts dive 1373 with mbari315k model"
    jc.set_job(name, JobStatus.UNKNOWN, ["vid1.mp4"], JobStatus.RUNNING)
    f = jc.get_job_by_name(name)
    assert f[JobIndex.STATUS] == JobStatus.RUNNING