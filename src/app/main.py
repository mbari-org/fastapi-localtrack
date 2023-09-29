# fastapi-localtrack, Apache-2.0 license
# Filename: app/main.py
# Description: Runs a FastAPI server to run video detection and tracking models locally

import datetime
import signal
import random
import os

from pathlib import Path
from urllib.parse import urlparse

from deepsea_ai.database.job.database_helper import get_status, json_b64_encode, json_b64_decode
from deepsea_ai.database.job.misc import JobType, Status
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from app.conf import temp_path, default_args, default_video_url, root_bucket, model_prefix, engine, database_path, \
    lagoon_names, lagoon_states
from app import __version__
from app.job import JobLocal, MediaLocal, init_db
from app.logger import info, debug
from app import logger
from app.utils.exceptions import NotFoundException
from app.utils.misc import check_video_availability, list_by_suffix

if not os.getenv('MINIO_ENDPOINT_URL') or not os.getenv('MINIO_ACCESS_KEY') or not os.getenv('MINIO_SECRET_KEY'):
    info(f"MINIO_ENDPOINT_URL, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY environment variables must be set")

app = FastAPI()

shutdown_flag = False

# Create a logger if one doesn't exist in the temp directory
if not logger.custom_logger():
    logger = logger.create_logger_file(temp_path / 'logs')

# Reset the database
info(f'Initializing the database')
session_maker = init_db(database_path, reset=False)


# Define a function to handle the SIGINT signal (Ctrl+C)
def handle_sigint(signum, frame):
    global shutdown_flag
    info("Received Ctrl+C signal. Stopping the application...")
    print("Received Ctrl+C signal. Stopping the application...")
    shutdown_flag = False


# Set up the signal handler for SIGINT
signal.signal(signal.SIGINT, handle_sigint)

global model_paths, default_model, example_video, default_args, default_video_url


def fetch_models():
    """
    Fetch the models from the minio bucket
    :return:
    """
    global model_paths, default_model, example_video, default_video_url, default_args
    info(f'Fetching models from s3://{root_bucket}/{model_prefix}')
    model_s3 = list_by_suffix(root_bucket, model_prefix, ['.gz', '.pt'])
    debug(f'Creating dictionary of model names to model paths')
    model_paths = {Path(urlparse(m).path).name: m for m in model_s3}
    debug(f'Found {len(model_paths)} models')
    # Get an example model to use for the API documentation
    if model_paths and len(model_paths) > 0:
        default_model = list(model_paths.keys())[0]
    else:
        default_model = None

    if not check_video_availability(default_video_url):
        default_video_url = None

fetch_models()


class PredictModel(BaseModel):
    model: str | None = default_model
    video: str | None = default_video_url
    metadata: dict | None = {}
    args: str | None = default_args


# Exception handler for 404 errors
@app.exception_handler(NotFoundException)
async def nof_found_exception(request: Request, exc: NotFoundException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": f"{exc._name} not found"},
    )


def get_job_detail(**kwargs):
    """
    Get more detailed status of a job
    :param kwargs: The job name or job id
    :return: The status of the job or a 404 error
    """
    job = None
    job_status = Status.UNKNOWN
    media_name = ''
    metadata = {}
    with session_maker.begin() as db:
        if 'job_name' in kwargs:
            job_name = kwargs['job_name']
            job = db.query(JobLocal).filter(JobLocal.name == job_name).first()
        if 'job_id' in kwargs:
            job_id = kwargs['job_id']
            job = db.query(JobLocal).filter(JobLocal.id == job_id).first()
        if job:
            job_status = get_status(job)
            media_name = job.media[0].name
            if job.metadata_b64:
                metadata = json_b64_decode(job.metadata_b64)
            else:
                metadata = {}

            # fetch other metadata, e.g. processing_time_secs from the media metadata
            media_metadata = json_b64_decode(job.media[0].metadata_b64)
            processing_time_secs = media_metadata.get('processing_time_secs', None)
            num_tracks = media_metadata.get('num_tracks', None)
            s3_path = media_metadata.get('s3_path', None)
        if job:
            json_response = {"status": job_status,
                             "last_updated": f"{job.media[0].updatedAt}",
                             "created_at": f"{job.createdAt}",
                             "name": job.name,
                             "job_id": job.id,
                             "video": media_name,
                             "args": job.args,
                             "model": job.model,
                             "metadata": metadata,
                             "processing_time_secs": processing_time_secs,
                             "num_tracks": num_tracks,
                             "s3_path": s3_path}
            return json_response
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {kwargs} not found")


@app.get("/")
async def root():
    return {"message": f'fastapi-localtrack {__version__}'}


@app.get("/health", status_code=status.HTTP_200_OK)
async def root():
    # Check if models are available and return a 503 error if not
    fetch_models()
    database_online = is_database_online()

    if len(model_paths) == 0:
        return {"message": "no models available"}, 503

    if not database_online:
        return {"message": "database offline"}, 503

    return {"message": "OK"}


@app.get("/models", status_code=status.HTTP_200_OK)
async def read_models():
    fetch_models()
    return {"model": list(model_paths.keys())}


@app.post("/predict", status_code=status.HTTP_200_OK)
async def process_video(item: PredictModel):
    data = jsonable_encoder(item)
    video = data['video']
    model_name = data['model']
    metadata = data['metadata']
    args = data['args']
    fetch_models()

    # If the video cannot be reached return a 400 error
    if not check_video_availability(video):
        raise NotFoundException(name=video)

    # If the model does not exist, return a 404 error
    if model_name not in model_paths.keys():
        raise NotFoundException(name=model_name)

    # Create a name for the job based on the video prefix, model name and lagoon fun to honor Duane and his lagoons
    video_name = video.split('=')[-1]
    # random number in the range of the lagoons
    index_name = random.randint(0, len(lagoon_names) - 1)
    index_state = random.randint(0, len(lagoon_states) - 1)

    job_name = f"{model_name} {Path(video_name).stem} {lagoon_names[index_name]} {lagoon_states[index_state]}"

    # Add the job to the cache
    with session_maker.begin() as db:
        job = JobLocal(name=job_name,
                       metadata_b64=json_b64_encode(metadata),
                       args=args,
                       engine=engine,  # this is the name of the docker container
                       model=model_paths[model_name],
                       job_type=JobType.DOCKER)

        media = MediaLocal(name=video,
                           status=Status.QUEUED,
                           metadata_b64=json_b64_encode({}),
                           updatedAt=datetime.datetime.utcnow())
        job.media.append(media)
        db.add(job)

    with session_maker.begin() as db:
        job = db.query(JobLocal).filter(JobLocal.name == job_name).first()
        job_id = job.id
        job_name = job.name

        return {"message": f"{video} queued for processing",
                "job_id": job_id,
                "job_name": job_name}


@app.get("/status_by_id/{job_id}")
async def get_status_by_id(job_id: int):
    return get_job_detail(job_id=job_id)


@app.get("/status_by_name/{job_name}")
async def get_status_by_name(job_name: str):
    return get_job_detail(job_name=job_name)


@app.get("/status")
async def get_status_all():
    # Get status for all DOCKER jobs
    with session_maker.begin() as db:
        jobs = db.query(JobLocal).filter(JobLocal.job_type == JobType.DOCKER).all()
        return {"jobs": [{"id": job.id, "name": job.name, "status": get_status(job)} for job in jobs]}


def is_database_online():
    """
    True if we can get a session to the database
    :return:
    """
    with session_maker.begin() as db:
        return True
    return False