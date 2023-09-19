# Test the sqlite database with pydantic
import time
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session
from deepsea_ai.database.job.database_helper import get_num_failed, get_num_completed, json_b64_encode, get_status
from deepsea_ai.database.job.misc import JobType, Status, job_hash
from app.job import Job2, Media2, PydanticJobWithMedia2, init_db, update_media
from app.logger import CustomLogger

# Set up the logger
CustomLogger(output_path=Path.cwd() / 'logs', output_prefix=__name__)

global session_maker


@pytest.fixture
def setup_database():
    global session_maker
    # Reset the database
    session_maker = init_db(Path.cwd() / 'db', reset=True)
    name = "Dive 1377 with yolov5x-mbay-benthic"
    job = Job2(id=1,
               engine="test docker runner id 1",
               email="dcline@mbari.org",
               name=name,
               job_type=JobType.DOCKER)
    vid1 = Media2(name="vid1.mp4", status=Status.QUEUED, metadata_b64=json_b64_encode({"job_uuid": job_hash(name)}))
    vid2 = Media2(name="vid2.mp4", status=Status.SUCCESS, metadata_b64=json_b64_encode({"job_uuid": job_hash(name)}))
    job.media = [vid1, vid2]
    with session_maker.begin() as db:
        db.add(job)


def test_pydantic_sqlalchemy(setup_database):
    """
    Test that the sqlalchemy models can be converted to pydantic models and back
    """
    with session_maker.begin() as db:
        job = db.query(Job2).first()
        pydantic_job_with_medias = PydanticJobWithMedia2.from_orm(job)
        data = pydantic_job_with_medias.dict()
        # Remove the timestamps as they are not in the sqlalchemy model
        del data['createdAt']
        for media in data['media']:
            del media['createdAt']

        assert data == {
            "engine": "test docker runner id 1",
            'email': 'dcline@mbari.org',
            "id": 1,
            "name": "Dive 1377 with yolov5x-mbay-benthic",
            "job_type": JobType.DOCKER,
            "media": [
                {"name": "vid1.mp4",
                 "id": 1,
                 "job_id": 1,
                 "status": Status.QUEUED,
                 "updatedAt": None,
                 "metadata_b64": json_b64_encode({"job_uuid": job_hash(job.name)})
                 },
                {"name": "vid2.mp4",
                 "id": 2,
                 "job_id": 1,
                 "status": Status.SUCCESS,
                 "updatedAt": None,
                 "metadata_b64": json_b64_encode({"job_uuid": job_hash(job.name)})
                 }
            ],
        }

        data_job = {
            "engine": "test docker runner id 2",
            "id": 2,
            "email": "dcline@mbari.org",
            "name": "Dive 1377 with yolov5x-mbay-benthic",
            "job_type": JobType.DOCKER,
        }

        data_media = [
            {"name": "vid1.mp4", "id": 3, "job_id": 2, "status": Status.QUEUED, "updatedAt": None,
             "metadata_b64": json_b64_encode({"job_uuid": job_hash(job.name)})},
            {"name": "vid2.mp4", "id": 4, "job_id": 2, "status": Status.SUCCESS, "updatedAt": None,
             "metadata_b64": json_b64_encode({"job_uuid": job_hash(job.name)})},
        ]

        # Convert the pydantic model back to a sqlalchemy model
        sqlalchemy_job = Job2(**data_job)
        db.add(sqlalchemy_job)
        sqlalchemy_media = [Media2(**media) for media in data_media]
        db.add(sqlalchemy_media[0])
        db.add(sqlalchemy_media[1])


def test_running_status(setup_database):
    """
    Test that a job status is running if one or more of the media is running
    and the rest are queued
    """
    global session_maker
    with session_maker.begin() as db:
        job = db.query(Job2).first()

        # Set the first media as RUNNING
        failed_media = job.media[0]
        failed_media.status = Status.RUNNING
        db.add(job)
        db.commit()

    with session_maker.begin() as db:
        job_query = db.query(Job2).first()
        status = get_status(job_query)

        # Status should be RUNNING
        assert status == Status.RUNNING


def test_failed_status(setup_database):
    """
    Test that a job status is failed if one of the media2 is failed
    """
    global session_maker
    with session_maker.begin() as db:
        job = db.query(Job2).first()

        # set the first media as FAILED
        failed_media = job.media[0]
        failed_media.status = Status.FAILED

        # Set the status of all the other media2 to success
        for m in job.media[1:]:
            m.status = Status.SUCCESS

        db.add(job)

        job_query = db.query(Job2).first()
        status = get_status(job_query)

        # Status should be FAILED
        assert status == Status.FAILED


def test_queued_status(setup_database):
    """
    Test that a job status is queued if all the media2 are queued
    """
    with session_maker.begin() as db:
        job = db.query(Job2).first()

        status = get_status(job)

    # Status should be QUEUED
    assert status == Status.QUEUED


def test_num_failed(setup_database):
    """
    Test that the number of failed media2 is correct
    """
    with session_maker.begin() as db:
        job = db.query(Job2).first()
        num_failed = get_num_failed(job)

        # There should be no failed media2
        assert num_failed == 0


def test_num_completed(setup_database):
    """
    Test that the number of completed media2 is correct
    """
    with session_maker.begin() as db:
        job = db.query(Job2).first()
        num_completed = get_num_completed(job)

        # There should be 1 completed media2
        assert num_completed == 1


def add_vid3(db: Session = None):
    """
    Helper function to add a new media to the database
    """
    job = db.query(Job2).first()  # Get the first job
    vid1 = Media2(id=3, name="vid3.mp4", status=Status.QUEUED, updatedAt=datetime.now(), job=job)
    db.add(vid1)


def test_add_one_media(setup_database):
    """
    Test adding a new media object adds 1 to the number of media2 in the job
    """
    with session_maker.begin() as db:
        job = db.query(Job2).first()
        job_p = PydanticJobWithMedia2.from_orm(job)
        num_media2 = len(job_p.media)

        add_vid3(db)

        # Verify that the number of media2 has increased by 1
        job_updated = db.query(Job2).first()
        job_p_updated = PydanticJobWithMedia2.from_orm(job_updated)
        assert len(job_p_updated.media) == num_media2 + 1


def test_update_one_media(setup_database):
    """
    Test updating a media with a new media object updates the media timestamp.
    """
    with session_maker.begin() as db:
        add_vid3(db)
        time.sleep(1)  # sleep for 1 second to ensure the timestamp is different

        job = db.query(Job2).first()
        num_medias = len(job.media)

        # Get the media with the name vid3.mp4 and update the timestamp and status to SUCCESS
        update_media(db, job, 'vid3.mp4', Status.SUCCESS)

        media = db.query(Media2).filter(Media2.name == 'vid3.mp4').first()

        # Verify that the number of medias is the same, except a newer timestamp
        job_updated = db.query(Job2).first()
        media_updated = [m for m in job_updated.media if m.name == 'vid3.mp4'][0]
        assert len(job_updated.media) == num_medias
        assert media_updated.updatedAt > media.createdAt


if __name__ == '__main__':
    test_pydantic_sqlalchemy()
