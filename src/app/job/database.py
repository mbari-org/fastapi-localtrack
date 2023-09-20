# fastapi-accutrack, Apache-2.0 license
# Filename: job/database.py
# Description: Job database
from datetime import datetime
from typing import List

from deepsea_ai.logger import info
from deepsea_ai.database.job import MediaBase, Status, Media, Job
from deepsea_ai.database.job.database_helper import json_b64_encode, json_b64_decode
from pydantic_sqlalchemy import sqlalchemy_to_pydantic
from sqlalchemy import Column, String, create_engine, Integer, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base, Session
from pathlib import Path

Base = declarative_base()


class Job2(Job):
    __table_args__ = {'extend_existing': True}
    __tablename__ = "job"

    args = Column(String, nullable=False)

    email = Column(String, nullable=False)

    model = Column(String, nullable=False)

    media = relationship('Media2', backref="job", passive_deletes=True)


class Media2(MediaBase):
    __table_args__ = {'extend_existing': True}
    __tablename__ = "media"

    job_id = Column(Integer, ForeignKey('job.id', ondelete='CASCADE'))


PydanticJob2 = sqlalchemy_to_pydantic(Job2)
PydanticMedia2 = sqlalchemy_to_pydantic(Media2)


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

    # Name the database based on the account number to avoid collisions
    db = db_path / f'sqlite_job_cache_docker.db'
    info(f"Initializing job cache database in {db_path} as {db}")
    engine = create_engine(f"sqlite:///{db.as_posix()}", connect_args={"check_same_thread": True}, echo=False)

    Base.metadata.create_all(engine, tables=[Job2.__table__, Media2.__table__])

    if reset:
        # Clear the database
        with sessionmaker(bind=engine).begin() as db:
            db.query(Job2).delete()
            db.query(Media2).delete()

    return sessionmaker(bind=engine)


def update_media(db: Session, job: Job, video_name: str, status: str, **kwargs):
    """
    Update a video in a job. If the video does not exist, add it to the job.
    :param db: The database session
    :param job: The job
    :param video_name: The name of the video to update
    :param status: The status of the video
    """
    info(f'Updating media {video_name} to {status}')

    # Set kwargs to empty dict if None
    kwargs = kwargs or {}

    # If there are additional kwargs, search by them and the name
    media = None
    if kwargs:
        if 'metadata_b64' in kwargs:
            # Find the media with the matching metadata
            media = [m for m in job.media if m.metadata_b64 == kwargs['metadata_b64'] and m.name == video_name]
        else:
            for key, value in kwargs.items():
                for m in job.media:
                    if m.metadata_b64 and json_b64_decode(m.metadata_b64)[key] == value and m.name == video_name:
                        info(f'Found media matching {video_name} and {key} {value} in job {job.name}')
                        media = m
                        break
    if not media:  # can't find by metadata, try by name
        media = [m for m in job.media if m.name == video_name]

    if media:
        if len(media) > 0:
            media = media[0]

        info(f'Found media {video_name} in job {job.name}')

        if status == Status.QUEUED and media.status == Status.RUNNING or media.status == Status.SUCCESS or media.status == Status.FAILED:
            info(f'Media {video_name} in job {job.name} is already {media.status}. Not updating to {status}')
            return

        # Update the media status, timestamp and any additional kwargs
        media.status = status
        media.updatedAt = datetime.utcnow()

        # add metadata if there was one in the kwargs
        if 'metadata_b64' in kwargs:
            media.metadata_b64 = kwargs['metadata_b64']
        else:
            media.metadata_b64 = json_b64_encode(kwargs)

        # Update the metadata
        metadata_json = json_b64_decode(media.metadata_b64)
        for key, value in kwargs.items():
            if key in metadata_json:
                metadata_json[key] = value
        media.metadata_b64 = json_b64_encode(metadata_json)

        db.merge(media)

    else:
        info(f'A new media {video_name} was added to job {job.name} kwargs {kwargs}')
        new_media = Media(name=video_name,
                          status=status,
                          job=job,
                          metadata_b64=json_b64_encode(kwargs),
                          updatedAt=datetime.utcnow())
        db.add(new_media)
        job.media.append(new_media)
