# fastapi-accutrack, Apache-2.0 license
# Filename: runner/local.py
# Description: Docker runner to process videos locally

import pathlib
import time

import docker
import os
import shutil

from urllib.parse import urlparse
from deepsea_ai.config.config import Config
from pathlib import Path
from app.conf import temp_path, local_config_ini_path
from app.logger import info, err, debug, exception
from app import logger, conf
from app.utils.misc import upload_files_to_s3, download_video

default_name = 'strongsort'

class DockerRunner:

    def __init__(self,
                 job_id: int,
                 video_url: str,
                 model_s3: str,
                 output_s3: str,
                 args: str | None = None,
                 track_s3: str | None = None):
        """
        Run docker container with the given model and video
        :param job_id: id for the job in the database
        :param video_url: url of the video to process
        :param model_s3:  location of the model in s3
        :param output_s3: location to upload the results
        :param track_s3:: location of the track configuration in s3
        :param args: optional arguments to pass to the track command
        """
        cfg = Config(conf.local_config_ini_path.as_posix())

        self.container = None
        self.args = args
        self.video_url = video_url
        self.model_s3 = model_s3
        self.output_s3 = output_s3
        if track_s3:
            self.track_s3 = track_s3
        else:
            self.track_s3 = cfg('minio', 's3_strongsort_track_config')

        if not self.track_s3.endswith('.yaml'):
            exception(f'Invalid track config {self.track_s3}')
            return

        self.processjobconfig_json_path = Path(__file__).parent / 'processingjobconfig.json'

        if not self.processjobconfig_json_path.exists():
            err(f'Processing job config file {self.processjobconfig_json_path} missing')

        # if running this on an arm64 machine, use the arm64 docker image
        if os.uname().machine == 'arm64':
            self.container_name = cfg('minio',
                                      'strongsort_container_arm64')
        else:
            self.container_name = cfg('minio',
                                      'strongsort_container')

        self.in_path = temp_path / str(job_id) / 'input'
        self.out_path = temp_path / str(job_id) / 'output'
        self.in_path.mkdir(parents=True, exist_ok=True)
        self.out_path.mkdir(parents=True, exist_ok=True)

    def __del__(self):
        """
        Delete the docker container and clean up the input directory
        :return:
        """
        debug(f'Deleting {self.__class__.__name__} instance')

        if self.container:
            debug(f'Stopping and removing {self.container.id} container')
            if self.container:
                self.container.stop()
                self.container.remove()

            # Clean up the input directory
            debug(f'Removing {self.in_path.as_posix()}')
            if self.in_path.exists():
                shutil.rmtree(self.in_path.as_posix())

    def run(self):
        """
        Proces the video with a local docker runner. Results are uploaded to the output_s3 location
        :return:
        """
        info(f'Processing {self.video_url} with {self.model_s3} and {self.track_s3} to {self.output_s3}<----')

        # Download the video at the self.video_url to the self.in_path
        if download_video(self.video_url, self.in_path):
            info(f'Video {self.video_url} downloaded to {self.in_path.as_posix()}')
        else:
            err(f'Failed to download {self.video_url} to {self.in_path.as_posix()}. Are you sure your nginx server is running?')
            return

        home = Path.home()
        profile = os.environ.get('AWS_DEFAULT_PROFILE', 'default')
        info(f'Using credentials file in {home}/.aws and profile {profile}')

        # Set volume bindings to run to be AWS SageMaker compliant
        volumes = {
            f'{home}/.aws': {'bind': '/root/.aws', 'mode': 'ro'},
            self.in_path.as_posix(): {'bind': '/opt/ml/processing/input'},
            self.out_path.as_posix(): {'bind': '/opt/ml/processing/output'},
        }

        client = docker.from_env()

        # Setup the command to run to be AWS SageMaker compliant, /opt/ml/input, etc. These are the default,
        # but included here for clarity
        command = (f"dettrack --model-s3 {self.model_s3} "
                   f"--config-s3 {self.track_s3} "
                   f"-i /opt/ml/processing/input "
                   f"-o /opt/ml/processing/output")

        # Add the optional arguments if they exist. If these are missing, defaults are included in the Docker container
        if self.args:
            command += f" --args \"{self.args}\""

        info(f'Using command {command}')
        info(f'Running {self.container_name} ...')

        # Run the docker container in detached mode with network mode host to allow access to the local minio server
        self.container = client.containers.run(
            image=self.container_name,
            name=default_name,
            command=command,
            volumes=volumes,
            detach=True,
            environment={'AWS_DEFAULT_PROFILE': 'minio-accutrack'},
            network_mode='host'
        )

        info(f'Running docker container {self.container.id} {self.container_name} with command {command}')

        for line in self.container.logs(stream=True):
            output_line = line.decode('utf-8')
            debug(output_line)
            if 'Error' in output_line:
                err(output_line)

        # Wait for the container to finish up to 1 hour
        info(f'Waiting for container {self.container.id} to finish')
        self.container.wait(timeout=3600)

        # Check if the container is still running
        if self.container.status == 'running':
            err(f'Container {self.container.id} failed to complete')
            # Stop the container
            self.container.stop()
            return

        # Copy the processing job config file to the output directory
        debug(f'Copying {self.processjobconfig_json_path} to {self.out_path.as_posix()}')
        shutil.copy(self.processjobconfig_json_path.as_posix(), self.out_path.as_posix())

        # Upload the results to s3
        p = urlparse(self.output_s3)  # remove trailing slash
        upload_files_to_s3(bucket=p.netloc,
                           s3_path=p.path.lstrip('/'),
                           local_path=self.out_path.as_posix(),
                           suffixes=['.tar.gz', '.json'])

        info(f'Finished processing {self.video_url} with {self.model_s3} and {self.track_s3} to {self.output_s3}')

    def get_id(self):
        """
        Get the container id
        :return: The container id if it exists, None otherwise
        """
        if self.container:
            return self.container.id
        else:
            return None

    def is_successful(self):
        """
        Check if the container has successfully completed
        :return: True if a .tar.gz was created, False otherwise
        """

        # Complete if the output directory has a tar.gz file in it
        if len(list(self.out_path.glob('*.tar.gz'))) > 0:
            return True
        else:
            return False


def main():
    cfg = Config(local_config_ini_path.as_posix())
    track_prefix = cfg('minio', 's3_track_prefix')
    job_id = 1
    output_s3 = f's3://m3-video-processing/{track_prefix}/test/{job_id}'

    # Create a docker runner and run it
    p = DockerRunner(job_id=job_id,
                     output_s3=output_s3,
                     video_url='http://localhost:8090/video/V4361_20211006T163856Z_h265_1sec.mp4',
                     model_s3='s3://m3-video-processing/models/yolov5x_mbay_benthic_model.tar.gz',
                     args='--iou-thres 0.5 --conf-thres 0.01 --agnostic-nms --max-det 100')
    p.run()

    # Wait for the container to finish
    num_tries = 0
    while not p.is_successful() and num_tries < 3:
        time.sleep(30)
        num_tries += 1

    if p.is_successful():
        info(f'Processing complete: {p.is_successful()}')
    else:
        err(f'Processing complete: {p.is_successful()}')


if __name__ == '__main__':
    os.environ['AWS_DEFAULT_PROFILE'] = 'minio-accutrack'
    temp_path = pathlib.Path(__file__).parent / 'tmp'
    logger.create_logger_file(temp_path / 'logs', 'local')
    main()
