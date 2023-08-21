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
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from deepsea_ai.logger.job_cache import job_hash
from fastapi import FastAPI, WebSocket, BackgroundTasks, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.conf import job_cache, model_paths, temp_path, s3_root_bucket, s3_track_prefix
from app.job.cache import JobIndex, JobStatus
from app.logger import info
from app.runner.local import DockerRunner
from app.utils.mailer import send_email
from app.utils.misc import check_video_availability


class Job(BaseModel):
    model: str | None = list(model_paths.keys())[0]
    video_url: str | None = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec.mp4'
    metadata: str | None = None


example_vid_url = 'http://localhost:8090/V4361_20211006T162656Z_h265_1sec.mp4'
example_model = list(model_paths.keys())[0]

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


async def perform_io_task(task_name: str, video_url: str, model_s3: str, email: str = None):
    # Simulate an I/O-bound task
    # await asyncio.sleep(5)

    # Set the job status to running
    info(f"Running I/O Task '{task_name}'")
    job_cache.set_job(task_name, 'LOCAL', [video_url], JobStatus.RUNNING)

    # Create a docker runner instance and run it asynchronously
    job_uuid = job_hash(task_name)
    instance = DockerRunner(job_uuid, video_url, model_s3, track_s3=None, args=None, metadata=None)

    # Make a prefix for the output based on the video path (sans http) and the current time
    video_s3 = Path(urlparse(video_url).path)
    key = f"{video_s3.parent}{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"

    if email:
        output_s3 = f"s3://{s3_root_bucket}/{s3_track_prefix}/{email.split('@')[0]}{key}/output"
    else:
        # output_s3 = f"s3://{s3_root_bucket}/{s3_track_prefix}{key}/output"
        output_s3 = f"s3://{s3_root_bucket}/{s3_track_prefix}"

    await instance.run(output_s3)

    # The job is complete if it produces a compressed file
    out_tar = (temp_path / task_name / 'output' / f"{video_url.split('.')[0]}.tar.gz")

    if out_tar.exists():
        job_cache.set_job(task_name, 'LOCAL', [video_url], JobStatus.SUCCESS)
    else:
        job_cache.set_job(task_name, 'LOCAL', [video_url], JobStatus.FAILED)
    info(f"I/O Task '{task_name}' completed")


@app.get("/")
async def root():
    return {"message": "Hello"}


@app.get("/health", status_code=status.HTTP_200_OK)
async def root():
    # TODO: check if the models are available
    # Check if docker is available
    return {"message": "OK"}


@app.get("/models", status_code=status.HTTP_200_OK)
async def read_models():
    return {"model": list(model_paths.keys())}


@app.post("/process")
async def process_task(background_tasks: BackgroundTasks, model: str = example_model, video_url: str = example_vid_url):
    # data = jsonable_encoder(item)

    # If the video cannot be reached return a 400 error
    if not check_video_availability(video_url):
        raise NotFoundException(name=video_url)

    # If the model not exist, return a 404 error
    if model not in model_paths.keys():
        raise NotFoundException(name=model)

    # Create a name for the job based on the video prefix and model name
    video_name = video_url.split('=')[-1]
    job_name = f"{model}-{video_name}"

    # Add the job to the cache and run it in the background
    job_cache.set_job(job_name, 'LOCAL', [video_url], JobStatus.QUEUED)
    background_tasks.add_task(perform_io_task, "Task 1", video_url, model)
    job_uuid = job_hash(job_name)
    return {"message": f"Video {video_url} queued for processing", "job_uuid": job_uuid}


@app.get("/status/{job_uuid}")
async def get_status(job_uuid: str):
    job = job_cache.get_job_by_uuid(job_uuid)

    if job:
        # Get the cluster this job is running on and check the status
        cluster = job[JobIndex.CLUSTER]

        # # Get the cluster by name
        # for model_cluster in model_clusters:
        #     if model_cluster.model_name == cluster:
        #         # Get the status of the job

        return {"status": job[JobIndex.STATUS]}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
