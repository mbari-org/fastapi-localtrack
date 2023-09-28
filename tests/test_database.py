# fastapi-localtrack, Apache-2.0 license
# Filename: tests/test_database.py
# Description: Test the sqlite database with pydantic

import time
from datetime import datetime
from pathlib import Path
import os
import signal

import pytest
from sqlalchemy.orm import Session
from deepsea_ai.database.job.database_helper import get_num_failed, get_num_completed, json_b64_decode, json_b64_encode, \
    get_status
from deepsea_ai.database.job.misc import JobType, Status, job_hash
from app.job import JobLocal, MediaLocal, PydanticJobWithMedia2, init_db, update_media

from app import logger

logger = logger.create_logger_file(Path(__file__).parent, __file__)

global session_maker

fake_metadata = {
    "image_uri_ecr": "fake_image_uri_ecr",
    "instance_type": "fake_instance_type",
}


@pytest.fixture
def startup():
    global session_maker
    # Reset the database
    session_maker = init_db(Path.cwd() / 'db', reset=True)
    name = "Dive 1377 with yolov5x-mbay-benthic"
    job = JobLocal(id=1,
                   engine="test docker runner id 1",
                   metadata_b64=json_b64_encode(fake_metadata),
                   name=name,
                   model='yolov5x-mbay-benthic',
                   args='--conf-thres=0.1 --iou-thres=0.4 --max-det=100 --agnostic-nms --imgsz 640',
                   job_type=JobType.DOCKER)
    vid1 = MediaLocal(name="vid1.mp4", status=Status.QUEUED)
    vid2 = MediaLocal(name="vid2.mp4", status=Status.SUCCESS)
    job.media = [vid1, vid2]
    with session_maker.begin() as db:
        db.add(job)
    yield


@pytest.fixture
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)


def test_pydantic_sqlalchemy(startup):
    """
    Test that the sqlalchemy models can be converted to pydantic models and back
    """
    with session_maker.begin() as db:
        job = db.query(JobLocal).first()
        pydantic_job_with_medias = PydanticJobWithMedia2.from_orm(job)
        data = pydantic_job_with_medias.dict()
        # Remove the timestamps as they are not in the sqlalchemy model
        del data['createdAt']
        for media in data['media']:
            del media['createdAt']

        assert data == {
            "engine": "test docker runner id 1",
            "id": 1,
            "args": '--conf-thres=0.1 --iou-thres=0.4 --max-det=100 --agnostic-nms --imgsz 640',
            "model": 'yolov5x-mbay-benthic',
            "name": "Dive 1377 with yolov5x-mbay-benthic",
            'metadata_b64': json_b64_encode(fake_metadata),
            "job_type": JobType.DOCKER,
            "media": [
                {"name": "vid1.mp4",
                 "id": 1,
                 'metadata_b64': None,
                 "job_id": 1,
                 "status": Status.QUEUED,
                 "updatedAt": None
                 },
                {"name": "vid2.mp4",
                 "id": 2,
                 "job_id": 1,
                 'metadata_b64': None,
                 "status": Status.SUCCESS,
                 "updatedAt": None
                 }
            ],
        }

        data_job = {
            "engine": "test docker runner id 2",
            "id": 2,
            "args": "",
            "name": "Dive 1377 with yolov5x-mbay-benthic",
            "model": 'yolov5x-mbay-benthic',
            "job_type": JobType.DOCKER,
            "metadata_b64": json_b64_encode(fake_metadata),
        }

        data_media = [
            {"name": "vid1.mp4", "id": 3, "job_id": 2, "status": Status.QUEUED, "updatedAt": None},
            {"name": "vid2.mp4", "id": 4, "job_id": 2, "status": Status.SUCCESS, "updatedAt": None},
        ]

        # Convert the pydantic model back to a sqlalchemy model
        sqlalchemy_job = JobLocal(**data_job)
        db.add(sqlalchemy_job)
        sqlalchemy_media = [MediaLocal(**media) for media in data_media]
        db.add(sqlalchemy_media[0])
        db.add(sqlalchemy_media[1])


def test_running_status(startup):
    """
    Test that a job status is running if one or more of the media is running
    and the rest are queued
    """
    global session_maker
    with session_maker.begin() as db:
        job = db.query(JobLocal).first()

        # Set the first media as RUNNING
        failed_media = job.media[0]
        failed_media.status = Status.RUNNING
        db.add(job)
        db.commit()

    with session_maker.begin() as db:
        job_query = db.query(JobLocal).first()
        status = get_status(job_query)

        # Status should be RUNNING
        assert status == Status.RUNNING


def test_failed_status(startup):
    """
    Test that a job status is failed if one of the media2 is failed
    """
    global session_maker
    with session_maker.begin() as db:
        job = db.query(JobLocal).first()

        # set the first media as FAILED
        failed_media = job.media[0]
        failed_media.status = Status.FAILED

        # Set the status of all the other media2 to success
        for m in job.media[1:]:
            m.status = Status.SUCCESS

        db.add(job)

        job_query = db.query(JobLocal).first()
        status = get_status(job_query)

        # Status should be FAILED
        assert status == Status.FAILED


def test_queued_status(startup):
    """
    Test that a job status is queued if all the media2 are queued
    """
    with session_maker.begin() as db:
        job = db.query(JobLocal).first()

        status = get_status(job)

    # Status should be QUEUED
    assert status == Status.QUEUED


def test_num_failed(startup):
    """
    Test that the number of failed media2 is correct
    """
    with session_maker.begin() as db:
        job = db.query(JobLocal).first()
        num_failed = get_num_failed(job)

        # There should be no failed media2
        assert num_failed == 0


def test_num_completed(startup):
    """
    Test that the number of completed media2 is correct
    """
    with session_maker.begin() as db:
        job = db.query(JobLocal).first()
        num_completed = get_num_completed(job)

        # There should be 1 completed media2
        assert num_completed == 1


def add_vid3(db: Session = None):
    """
    Helper function to add a new media to the database
    """
    job = db.query(JobLocal).first()  # Get the first job
    vid1 = MediaLocal(id=3, name="vid3.mp4", status=Status.QUEUED, updatedAt=datetime.now(), job=job)
    db.add(vid1)


def test_add_one_media(startup):
    """
    Test adding a new media object adds 1 to the number of media2 in the job
    """
    with session_maker.begin() as db:
        job = db.query(JobLocal).first()
        job_p = PydanticJobWithMedia2.from_orm(job)
        num_media2 = len(job_p.media)

        job = db.query(JobLocal).first()  # Get the first job
        vid1 = MediaLocal(id=3, name="vid3.mp4", status=Status.QUEUED, updatedAt=datetime.now(), job=job)
        db.add(vid1)

        # Verify that the number of media2 has increased by 1
        job_updated = db.query(JobLocal).first()
        job_p_updated = PydanticJobWithMedia2.from_orm(job_updated)
        assert len(job_p_updated.media) == num_media2 + 1


def test_update_one_media(startup):
    """
    Test updating a media with a new media object updates the media timestamp.
    """
    with session_maker.begin() as db:

        job = db.query(JobLocal).first()  # Get the first job
        vid1 = MediaLocal(id=3, name="vid3.mp4", status=Status.QUEUED, updatedAt=datetime.now(), job=job)
        db.add(vid1)

        time.sleep(1)  # sleep for 1 second to ensure the timestamp is different

        job = db.query(JobLocal).first()
        num_medias = len(job.media)

        # Get the media with the name vid3.mp4 and update the timestamp and status to SUCCESS
        update_media(db, job, 'vid3.mp4', Status.SUCCESS)

        media = db.query(MediaLocal).filter(MediaLocal.name == 'vid3.mp4').first()

        # Verify that the number of medias is the same, except a newer timestamp
        job_updated = db.query(JobLocal).first()
        media_updated = [m for m in job_updated.media if m.name == 'vid3.mp4'][0]
        assert len(job_updated.media) == num_medias
        assert media_updated.updatedAt > media.createdAt


if __name__ == '__main__':
    test_pydantic_sqlalchemy()
