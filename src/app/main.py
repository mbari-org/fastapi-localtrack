# fastapi-accutrack, Apache-2.0 license
# Filename: app/main.py
# Description: Runs a FastAPI server to run video detection and tracking models locally

import datetime
import signal
import threading
import time

import docker
from pathlib import Path
from urllib.parse import urlparse

from deepsea_ai.database.job.database_helper import get_status, json_b64_encode, json_b64_decode
from deepsea_ai.database.job.misc import JobType, Status
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from app.conf import cfg
from app import __version__
from app.job import Job2, Media2, init_db
from app.logger import info, debug
from app.qmanager import Monitor
from app.utils.exceptions import NotFoundException, InvalidException
from app.utils.mailer import validate_email
from app.utils.misc import check_video_availability, list_by_suffix

s3_root_bucket = cfg('minio', 's3_root_bucket')
s3_model_prefix = cfg('minio', 's3_model_prefix')

info(f'Fetching models from s3://{s3_root_bucket}/{s3_model_prefix}')
model_s3 = list_by_suffix(s3_root_bucket, s3_model_prefix, ['.gz', '.pt'])

debug(f'Creating dictionary of model names to model paths')
model_paths = {Path(urlparse(model_s3[0]).path).stem: model for model in model_s3}

app = FastAPI()

running = True

# Reset the database
info(f'Initializing the database')
session_maker = init_db(Path.cwd() / 'db', reset=True)

def background_thread():
    while running:
        monitor = Monitor(session_maker)
        monitor.run()
        debug('Sleeping for 5 seconds')
        time.sleep(5)

# Start the background thread
background_thread = threading.Thread(target=background_thread)
background_thread.start()

# Get an example model to use for the API documentation
if model_paths and len(model_paths) > 0:
    example_model = list(model_paths.keys())[0]
else:
    example_model = None


# Define a function to handle the SIGINT signal (Ctrl+C)
def handle_sigint(signum, frame):
    global running
    info("Received Ctrl+C signal. Stopping the application...")
    print("Received Ctrl+C signal. Stopping the application...")
    running = False


# Set up the signal handler for SIGINT
signal.signal(signal.SIGINT, handle_sigint)


class PredictModel(BaseModel):
    model: str | None = example_model
    video: str | None = 'http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec.mp4'
    metadata: str | None = ''
    email: str | None = 'dcline@mbari.org'


# Exception handler for 404 errors
@app.exception_handler(NotFoundException)
async def nof_found_exception(request: Request, exc: NotFoundException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": f"{exc.name} not found"},
    )


def get_job_status(**kwargs):
    """
    Get the status of a job
    :param kwargs: The job name or job id
    :return: The status of the job or a 404 error
    """
    # if job_name in the kwargs
    with session_maker.begin() as db:
        job = None
        if 'job_name' in kwargs:
            job_name = kwargs['job_name']
            job = db.query(Job2).filter(Job2.name == job_name).first()
        if 'job_id' in kwargs:
            job_id = kwargs['job_id']
            job = db.query(Job2).filter(Job2.id == job_id).first()
        if job:
            job_status = get_status(job)
            media = job.media[0]
            return {"status": job_status, "video": media.name, "metadata": json_b64_decode(media.metadata_b64)}
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {kwargs} not found")


@app.get("/")
async def root():
    return {"message": f'fastapi-accutrack {__version__}'}


@app.get("/health", status_code=status.HTTP_200_OK)
async def root():
    # Check if docker is available on the host and models are available
    # if not, return a 503 error
    client = docker.from_env()
    try:
        client.ping()
    except Exception as e:
        return {"message": "docker not available"}, 503

    if len(model_paths) == 0:
        return {"message": "no models available"}, 503

    return {"message": "OK"}


@app.get("/models", status_code=status.HTTP_200_OK)
async def read_models():
    return {"model": list(model_paths.keys())}


@app.post("/predict", status_code=status.HTTP_200_OK)
async def process_task(item: PredictModel):
    data = jsonable_encoder(item)
    video = data['video']
    model = data['model']
    email = data['email']
    metadata = data['metadata']

    # If the video cannot be reached return a 400 error
    if not check_video_availability(video):
        raise NotFoundException(name=video)

    # If the email is not valid, return a 400 error
    if email and not validate_email(email):
        raise InvalidException(name=email)

    # If the model does not exist, return a 404 error
    if model not in model_paths.keys():
        raise NotFoundException(name=model)

    # Create a name for the job based on the video prefix, the model name and the timestamp
    video_name = video.split('=')[-1]
    job_name = f"{model} {Path(video_name).stem} {datetime.datetime.utcnow()}"

    # Add the job to the cache
    with session_maker.begin() as db:
        model_s3 = model_paths[model]
        if email:
            job = Job2(email=email, name=job_name, engine="", model=model_s3, job_type=JobType.DOCKER)
        else:
            job = Job2(name=job_name, engine="", model=model_s3, job_type=JobType.DOCKER)
        media = Media2(name=video, status=Status.QUEUED, metadata_b64=json_b64_encode(metadata), updatedAt=datetime.datetime.utcnow())
        job.media.append(media)
        db.add(job)

    with session_maker.begin() as db:
        job = db.query(Job2).filter(Job2.name == job_name).first()
        job_id = job.id

        return {"message": f"Video {video} queued for processing",
                "job_id": job_id,
                "job_name": job_name}


@app.get("/status_by_id/{job_id}")
async def get_status_by_id(job_id: int):
    return get_job_status(job_id=job_id)


@app.get("/status_by_name/{job_name}")
async def get_status_by_name(job_name: str):
    return get_job_status(job_name=job_name)


@app.get("/status")
async def get_status_all():
    # Get status for all DOCKER jobs
    with session_maker.begin() as db:
        jobs = db.query(Job2).filter(Job2.job_type == JobType.DOCKER).all()
        return {"jobs": [{"id": job.id, "name": job.name, "status": get_status(job)} for job in jobs]}