from datetime import datetime
from pydantic import BaseModel


# Enum for the status of a job
class JobStatus:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    UNKNOWN = "UNKNOWN"


# Indexes into the micro database for Media and Job
class JobIndex:
    NAME = 0
    CLUSTER = 1
    MODEL = 2
    MEDIA = 3
    CREATED_TIME = 4
    UPDATE_TIME = 4
    STATUS = 5
    EMAIL = 6
    RUNNER_ID = 7


class MediaIndex:
    NAME = 0
    UUID = 1
    UPDATE_TIME = 2
    STATUS = 3


class JobEntry(BaseModel):
    name: str
    cluster: str
    model: str
    media: list[str]
    created_time: datetime | None = datetime.utcnow()
    update_time: datetime | None = datetime.utcnow()
    status: str | None = JobStatus.UNKNOWN
    email: str | None
    runner_id: str | None


class Job(BaseModel):
    model: str
    video: str | None = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec.mp4'
    email: str | None = None
    metadata: str | None = None
