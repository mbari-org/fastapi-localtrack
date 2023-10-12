# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/docker_client.py
# Description: Docker client that manages docker containers

import os
from datetime import datetime
from pathlib import Path

import docker
import requests
import json
import tempfile
from aiohttp import ClientResponse
from deepsea_ai.database.job import Status, JobType
from deepsea_ai.database.job.database_helper import json_b64_decode, json_b64_encode, get_status

from app.job import MediaLocal, JobLocal, update_media, PydanticJobWithMedia2, init_db
from daemon.logger import info, err, warn, exception
from daemon.docker_runner import DockerRunner, DEFAULT_CONTAINER_NAME

DEFAULT_ARGS = '--iou-thres 0.5 --conf-thres 0.01 --agnostic-nms --max-det 100'


class DockerClient:

    def __init__(self) -> None:
        info('Initializing DockerClient')
        self._runners = {}

    async def check(self, database_path: Path) -> None:
        """
        Check the status of any running jobs and close them out
        :param database_path: The path to the database
        :return:
        """

        session_maker = init_db(database_path, reset=False)

        jobs_to_remove = []
        for job_id, runner in self._runners.items():

            if runner.is_running():
                info(f'Job {job_id} docker container {runner.container_name} is still running')
                continue

            if runner.is_successful():
                info(f'Job {job_id} docker container {runner.container_name} processing complete')
                jobs_to_remove.append(job_id)

                # Update the job status and notify
                with session_maker.begin() as db:
                    job = db.query(JobLocal).filter(JobLocal.id == job_id).first()
                    if job.media[0].metadata_b64:
                        metadata = json_b64_decode(job.media[0].metadata_b64)
                    else:
                        metadata = {}
                    job.results, local_path, num_tracks, processing_time_secs = runner.get_results()
                    metadata['s3_path'] = job.results
                    metadata['num_tracks'] = num_tracks
                    metadata['processing_time_secs'] = processing_time_secs
                    update_media(db, job,
                                 job.media[0].name,
                                 Status.SUCCESS,
                                 metadata_b64=json_b64_encode(metadata))
                    await notify(job, local_path)
                    await runner.fini()

            if runner.failed():
                warn(f'Job {job_id} docker container {runner.container_name} failed')
                jobs_to_remove.append(job_id)
                # Update the job status and notify
                with session_maker.begin() as db:
                    job = db.query(JobLocal).filter(JobLocal.id == job_id).first()
                    if job.media[0].metadata_b64:
                        metadata = json_b64_decode(job.media[0].metadata_b64)
                    else:
                        metadata = {}
                    update_media(db, job,
                                 job.media[0].name,
                                 Status.FAILED,
                                 metadata_b64=json_b64_encode(metadata))
                    # Create a track tar file that is empty
                    temp_path = Path(tempfile.gettempdir())
                    local_path = temp_path / 'empty.tar.gz'
                    local_path.touch()
                    await notify(job, local_path)
                    await runner.fini()
                    local_path.unlink()

        # Remove the instances
        for job_id in jobs_to_remove:
            if job_id in self._runners:
                info(f'Removing runner for job {job_id} from the list of runners')
                del self._runners[job_id]

    async def process(self,
                      has_gpu: bool,
                      num_procs: int,
                      database_path: Path,
                      root_bucket: str,
                      track_prefix: str,
                      s3_track_config: str) -> ClientResponse:
        """
        Process any jobs that are queued. This function is called by the daemon module
        :param has_gpu: True if the machine has a GPU(s)
        :param num_procs: The number of processes to run in parallel
        :param database_path: The path to the database
        :param root_bucket: The root bucket for the track tar files
        :param track_prefix: The prefix for the track tar files
        :param s3_track_config: The s3 track config
        """
        session_maker = init_db(database_path, reset=False)

        # Get any media that are queued for processing
        with session_maker.begin() as db:
            media = db.query(MediaLocal).filter(MediaLocal.status == Status.QUEUED).first()
            if not media:
                info(f'No video queued to process')
                return

            job_id = media.job_id

        client = docker.from_env()

        # Get all active docker containers
        all_containers = client.containers.list(all=True)
        all_containers = [container for container in all_containers if
                          container.name.startswith(DEFAULT_CONTAINER_NAME)]

        info(f'Found {len(all_containers)} active {DEFAULT_CONTAINER_NAME} docker containers')

        if len(all_containers) <= num_procs:
            with session_maker.begin() as db:
                # Get the first job in the queue
                job = db.query(JobLocal).filter(JobLocal.id == job_id).first()
                if not job:
                    err(f'No job found with id {job_id}')
                    return
                job_data = PydanticJobWithMedia2.from_orm(job)
                update_media(db, job, job.media[0].name, Status.RUNNING)

            if job_data:
                # Make a prefix for the output based on the video path (sans http) and the current time
                key = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
                output_s3 = f"s3://{root_bucket}/{track_prefix}/{key}"

                # Add default args if none are provided
                args = job_data.args or DEFAULT_ARGS

                info(f'Running job {job_data.id} with output {output_s3}')
                runner = DockerRunner(image_name=job_data.engine,
                                      job_id=job_data.id,
                                      job_name=job_data.name,
                                      output_s3=output_s3,
                                      video_url=job_data.media[0].name,
                                      model_s3=job_data.model,
                                      track_s3=s3_track_config,
                                      args=args)

                with session_maker.begin() as db:
                    job = db.query(JobLocal).filter(JobLocal.id == job_data.id).first()
                    update_media(db, job, job.media[0].name, Status.RUNNING)

                self._runners[job_data.id] = runner

                await runner.run(has_gpu)
            else:
                err(f'No job found with id {job_id}')
        else:
            info(f'Already running maximum allowed {len(all_containers)} jobs. Waiting for one to finish')

    @staticmethod
    def startup(database_path: Path) -> None:
        """
        Startup logic to kill any dangling jobs and check for docker
        Check the database for any jobs that were running when the service was restarted and mark them as failed
        Kill any containers that are running
        :param database_path: The path to the database
        :return:
        """
        session_maker = init_db(database_path, reset=False)

        info(f'Checking for valid docker connection')
        client = docker.from_env()

        try:
            client.ping()
        except Exception as e:
            err(f"docker not available {e}")
            return

        with session_maker.begin() as db:
            docker_jobs = db.query(JobLocal).filter(JobLocal.job_type == JobType.DOCKER).all()
            # Get all the job ids with status QUEUED and RUNNING
            jobs_ids_queued = [job.id for job in docker_jobs if get_status(job) == Status.QUEUED]
            jobs_ids_running = [job.id for job in docker_jobs if get_status(job) == Status.RUNNING]
            info(f'Found {len(docker_jobs)} docker jobs in the database. '
                 f'Number of queued jobs: {len(jobs_ids_queued)}. Number of running jobs: {len(jobs_ids_running)}')
        if len(jobs_ids_running) > 0:
            for job_id in jobs_ids_running:
                # Should never get here unless something went wrong and the
                # service was restarted while a job was running, so kill
                # the container and mark the job as failed
                err(f'Job {job_id} was running but the service was restarted')
                with session_maker.begin() as db:
                    job = db.query(JobLocal).filter(JobLocal.id == job_id).first()
                    job.media[0].status = Status.FAILED

        # Get all active docker containers
        all_containers = client.containers.list(all=True)
        all_containers = [container for container in all_containers if
                          container.name.startswith(DEFAULT_CONTAINER_NAME)]

        # Should never get here unless something went wrong
        for container in all_containers:
            err(
                f'Container {container.id} was running but the service was restarted. Stopping and removing it')
            # Stop the container
            try:
                container = client.containers.get(container.id)
                if container.status == 'running':
                    container.stop()
                    info(f"Container {container.id} stopped successfully.")
                info(f"Container {container.id} removed successfully.")
            except Exception as e:
                exception(e)


async def notify(job: JobLocal, local_path: Path = None) -> None:
    """
    Notify a receiver through a multipart POST request
    :param job: The job to notify about
    :param local_path: The local path to the track tar file
    :return:
    """
    notify_url = os.getenv('NOTIFY_URL')
    if not notify_url:
        warn("NOTIFY_URL environment variable not set. Skipping notification")
        return

    metadata = json_b64_decode(job.metadata_b64)

    if local_path and local_path.exists():
        with local_path.open("rb") as file:
            results = file.read()
            form_data = {
                "metadata": (None, json.dumps(metadata), 'application/json'),
                "file": results
            }
    else:
        err(f'No track tar file found for job {job.id}')
        form_data = {
            "metadata": (None, json.dumps(metadata), 'application/json'),
            "file": None
        }

    info(f'Sending notification for job {job.id} to {notify_url}')

    # Send the multipart POST request
    response = requests.post(notify_url, files=form_data)

    # Check the response
    if response.status_code == 200:
        info(f'Notification {metadata} sent successfully')
    else:
        err(f"Failed to send notification {metadata}. Status code: {response.status_code}")
        err(response.text)
