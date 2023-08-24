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
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from deepsea_ai.logger.job_cache import job_hash
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.conf import job_cache, model_paths, temp_path, s3_root_bucket, s3_track_prefix
from app.job.cache import JobIndex, JobStatus
from app.logger import info
from app.runner.local import DockerRunner
from app.utils.mailer import send_email
from app.utils.misc import check_video_availability

if model_paths and len(model_paths) > 0:
    example_model = list(model_paths.keys())[0]
else:
    example_model = None


class Job(BaseModel):
    model: str | None = example_model
    video: str | None = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec.mp4'
    metadata: str | None = None


app = FastAPI()


# Exception handler for 404 errors
class NotFoundException(Exception):
    def __init__(self, name: str):
        self.name = name


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


def run_job(job_name: str, video_url: str, model_s3: str, email=None):
    info(f"Running '{job_name}'")

    # Create a docker runner instance and run it asynchronously
    job_uuid = job_hash(job_name)
    instance = DockerRunner(job_uuid, video_url, model_s3, track_s3=None, args=None, metadata=None)

    # Make a prefix for the output based on the video path (sans http) and the current time
    video_s3 = Path(urlparse(video_url).path)
    key = f"{video_s3.parent}{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"

    if email:
        output_s3 = f"s3://{s3_root_bucket}/{s3_track_prefix}/{email.split('@')[0]}{key}/output"
    else:
        # output_s3 = f"s3://{s3_root_bucket}/{s3_track_prefix}{key}/output"
        output_s3 = f"s3://{s3_root_bucket}/{s3_track_prefix}"

    instance.run(output_s3)
    job_cache.set_job(job_name, 'LOCAL', [video_url], JobStatus.RUNNING)

    # Check if the job is complete every 5 seconds and timeout after 5 minutes
    while not instance.is_complete():
        time.sleep(5)
        if instance.is_complete():
            break

    # The job is successful if it produces a non-zero compressed file
    out_tar = (temp_path / job_uuid / 'output' / f"{video_s3.stem}.tracks.tar.gz")

    if out_tar.exists() and out_tar.stat().st_size > 0:
        job_cache.set_job(job_name, 'LOCAL', [video_url], JobStatus.SUCCESS)
    else:
        job_cache.set_job(job_name, 'LOCAL', [video_url], JobStatus.FAILED)
    info(f"Job '{job_name}' ended with status {job_cache.get_job_by_uuid(job_uuid)[JobIndex.STATUS]}")


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
    model_s3 = model_paths[model]

    # Add the job to the cache and run it in the background
    job_cache.set_job(job_name, 'LOCAL', [video], JobStatus.QUEUED)
    background_tasks.add_task(run_job, job_name, video, model_s3)
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
