# fastapi-localtrack, Apache-2.0 license
# Filename: job/database.py
# Description: Job database
from datetime import datetime
from typing import List

from app.logger import info
from deepsea_ai.database.job import MediaBase, Status, Media, Job
from pydantic_sqlalchemy import sqlalchemy_to_pydantic
from sqlalchemy import Column, String, create_engine, Integer, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base, Session
from pathlib import Path

Base = declarative_base()


class JobLocal(Job):
    __table_args__ = {'extend_existing': True}
    __tablename__ = "job"

    args = Column(String, nullable=True)

    metadata_b64 = Column(String, nullable=True)

    model = Column(String, nullable=False)

    media = relationship('MediaLocal', backref="job", passive_deletes=True)


class MediaLocal(MediaBase):
    __table_args__ = {'extend_existing': True}
    __tablename__ = "media"

    job_id = Column(Integer, ForeignKey('job.id', ondelete='CASCADE'))


PydanticJob2 = sqlalchemy_to_pydantic(JobLocal)
PydanticMedia2 = sqlalchemy_to_pydantic(MediaLocal)


class PydanticJobWithMedia2(PydanticJob2):
    media: List[PydanticMedia2] = []


def init_db(db_path: Path, reset: bool = False) -> sessionmaker:
    """
    Initialize the job cache database
    :param db_path: The path to the database
    :param reset: Whether to reset the database
    :return: A sessionmaker
    """

    # Create the output path to store the database if it doesn't exist
    db_path.mkdir(parents=True, exist_ok=True)

    db = db_path / f'sqlite_job_cache_docker.db'
    info(f"Initializing job cache database in {db_path} as {db}")
    engine = create_engine(f"sqlite:///{db.as_posix()}", connect_args={"check_same_thread": False}, echo=False)

    Base.metadata.create_all(engine, tables=[JobLocal.__table__, MediaLocal.__table__])

    # If the database is missing, create it
    if not db.exists():
        reset = True

    if reset:
        # Clear the database
        with sessionmaker(bind=engine).begin() as db:
            db.query(JobLocal).delete()
            db.query(MediaLocal).delete()

    return sessionmaker(bind=engine)


def update_media(db: Session, job: Job, video_name: str, status: str, metadata_b64: str = None):
    """
    Update a video in a job. If the video does not exist, add it to the job.
    :param db: The database session
    :param job: The job
    :param video_name: The name of the video to update
    :param status: The status of the video
    :param metadata_b64: The metadata to pass to the job
    """
    info(f'Updating media {video_name} in job {job.id} {job.name} to {status}')

    media = [m for m in job.media if m.name == video_name]

    if media:
        if len(media) > 0:
            media = media[0]

        info(f'Found media {video_name} in job {job.name}')

        # Update the media status, timestamp and any additional kwargs
        media.status = status
        media.updatedAt = datetime.utcnow()
        if metadata_b64:
            media.metadata_b64 = metadata_b64

    else:
        info(f'A new media {video_name} was added to job {job.id} {job.name}')
        new_media = Media(name=video_name,
                          status=status,
                          job=job,
                          metadata_b64=metadata_b64,
                          updatedAt=datetime.utcnow())
        db.add(new_media)
        job.media.append(new_media)
