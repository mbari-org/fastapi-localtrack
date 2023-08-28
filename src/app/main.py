# !/usr/bin/env python
__author__ = "Danelle Cline"
__copyright__ = "Copyright 2023, MBARI"
__credits__ = ["MBARI"]
__license__ = "GPL"
__maintainer__ = "Danelle Cline"
__email__ = "dcline at mbari.org"
__doc__ = '''

Runs a FastAPI server to serve video detection and tracking models

@author: __author__
@status: __status__
@license: __license__
'''

import asyncio
from pathlib import Path
from urllib.parse import urlparse

from deepsea_ai.logger.job_cache import job_hash
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.conf import job_cache, cfg
from app.job.cache import JobIndex, JobStatus
from app.job.model import Job
from app.logger import info, debug
from app.utils.exceptions import NotFoundException
from app.utils.mailer import send_email
from app.utils.misc import check_video_availability, list_by_suffix

s3_root_bucket = cfg('minio', 's3_root_bucket')
s3_model_prefix = cfg('minio', 's3_model_prefix')

info(f'Fetching models from s3://{s3_root_bucket}/{s3_model_prefix}')
model_s3 = list_by_suffix(s3_root_bucket, s3_model_prefix, ['.gz', '.pt'])

debug(f'Creating dictionary of model names to model paths')
model_paths = {Path(urlparse(model_s3[0]).path).stem: model for model in model_s3}

app = FastAPI()

# Exception handler for 404 errors
@app.exception_handler(NotFoundException)
async def nof_found_exception(request: Request, exc: NotFoundException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": f"{exc.name} not found"},
    )


async def send_notification_email(email_address):
    # Simulate an I/O-bound task
    await asyncio.sleep(2)
    # Send an email notification
    send_email(subject="Video Processing Complete",
               message_body="Your video processing has completed",
               to_email=email_address)
    info(f"Email notification sent to {email_address}")


@app.get("/")
async def root():
    return {"message": "Hello"}


@app.get("/health", status_code=status.HTTP_200_OK)
async def root():
    # TODO: check if at least one model is available
    # TODO: check if docker is available
    return {"message": "OK"}


@app.get("/models", status_code=status.HTTP_200_OK)
async def read_models():
    return {"model": list(model_paths.keys())}


@app.post("/predict", status_code=status.HTTP_200_OK)
async def process_task(background_tasks: BackgroundTasks, item: Job):
    data = jsonable_encoder(item)
    video = data['video']
    model = data['model']

    # If the video cannot be reached return a 400 error
    if not check_video_availability(video):
        raise NotFoundException(name=video)

    # If the model not exist, return a 404 error
    if model not in model_paths.keys():
        raise NotFoundException(name=model)

    # Create a name for the job based on the video prefix and model name
    video_name = video.split('=')[-1]
    job_name = f"{model}-{video_name}"

    # Add the job to the cache
    job_cache.set_job(job_name, 'LOCAL', [video], JobStatus.QUEUED, data)
    job_uuid = job_hash(job_name)
    return {"message": f"Video {video} queued for processing",
            "job_uuid": job_uuid,
            "job_name": job_name}


@app.get("/status_by_uuid/{job_uuid}")
async def get_status_by_uuid(job_uuid: str):
    job = job_cache.get_job_by_uuid(job_uuid)

    if job:
        return {"status": job[JobIndex.STATUS]}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


@app.get("/status_by_name/{job_name}")
async def get_status_by_name(job_name: str):
    job = job_cache.get_job_by_uuid(job_name)

    if job:
        return {"status": job[JobIndex.STATUS]}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
