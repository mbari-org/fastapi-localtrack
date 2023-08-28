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
import json
import pathlib

import docker
import os
import shutil

from urllib.parse import urlparse
from deepsea_ai.logger.job_cache import job_hash
from deepsea_ai.config.config import Config
from pathlib import Path
from app.conf import temp_path, local_config_ini_path
from app.logger import info, err, debug, exception
from app import logger, conf
from app.utils.misc import upload_files_to_s3, download_video


class DockerRunner:

    def __init__(self,
                 job_uuid: str,
                 video_url: str,
                 model_s3: str,
                 args: str | None = None,
                 track_s3: str | None = None,
                 metadata: dict | None = None):
        """
        Run docker container with the given model and video
        :param job_uuid: unique id for the job
        :param video_url: url of the video to process
        :param model_s3:  location of the model in s3
        :param track_s3:: location of the track configuration in s3
        :param args: optional arguments to pass to the track command
        :param metadata: optional metadata to pass through to the job cache - not used during processing
        """
        cfg = Config(conf.local_config_ini_path.as_posix())

        self.container = None
        self.args = args
        self.metadata = metadata
        self.video_url = video_url
        self.model_s3 = model_s3
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

        self.container_name = cfg('minio',
                                  'strongsort_container')  # docker image for running the strongsort track pipeline

        self.in_path = (temp_path / job_uuid / 'input')
        self.out_path = (temp_path / job_uuid / 'output')
        self.in_path.mkdir(parents=True, exist_ok=True)
        self.out_path.mkdir(parents=True, exist_ok=True)

    def __del__(self):
        debug(f'Deleting {self.__class__.__name__} instance')

        debug(f'Stopping and removing {self.container_name} container')
        if self.container:
            self.container.stop()
            self.container.remove()

        # Clean up the input and output directories
        debug(f'Removing {self.in_path.as_posix()} and {self.out_path.as_posix()}')
        if self.in_path.exists():
            shutil.rmtree(self.in_path.as_posix())
        if self.out_path.exists():
            shutil.rmtree(self.out_path.as_posix())

    async def run(self, output_s3: str):
        """
        Proces the video with a local docker runner. Results are uploaded to the output_s3 location
        :param output_s3: s3 location to upload the results
        :return:
        """
        info(f'Processing {self.video_url} with {self.model_s3} and {self.track_s3} to {output_s3}<----')

        # Download the video at the self.video_url to the self.in_path
        if download_video(self.video_url, self.in_path):
            info(f'Video {self.video_url} downloaded to {self.in_path.as_posix()}')
        else:
            err(f'Failed to download {self.video_url} to {self.in_path.as_posix()}. Are you sure your nginx server is running?')
            return

        if 'AWS_SHARED_CREDENTIALS_FILE' in os.environ:
            cred_path = Path(os.environ['AWS_SHARED_CREDENTIALS_FILE'])
        else:
            # Attempt to set to the HOME directory
            cred_path = Path.home() / '.aws' / 'credentials'

        info(f'Using credentials file {cred_path.as_posix()}')

        # Set volume bindings
        volumes = {
            cred_path.as_posix(): {'bind': '/root/.aws/credentials', 'mode': 'ro'},
            self.in_path.as_posix(): {'bind': '/opt/ml/processing/input'},
            self.out_path.as_posix(): {'bind': '/opt/ml/processing/output'},
        }

        # Setup the environment variables to pass to the docker self.container AWS_SHARED_CREDENTIALS_FILE is not
        # required as the default user is root and this is the default location; included for clarity
        env = {'AWS_SHARED_CREDENTIALS_FILE': '/root/.aws/credentials'}
        # Add in the PROFILE if it exists
        if 'AWS_DEFAULT_PROFILE' in os.environ:
            env['AWS_DEFAULT_PROFILE'] = os.environ['AWS_DEFAULT_PROFILE']

        client = docker.from_env(environment=env)

        # Setup the command to run per the AWS SageMaker standard
        command = (f"dettrack --model-s3 {self.model_s3} "
                   f"--config-s3 {self.track_s3} "
                   f"-i /opt/ml/processing/input "
                   f"-o /opt/ml/processing/output")

        # Add the optional arguments if they exist; if these are missing, defaults are included in the Docker container
        if self.args:
            command += f" --args \"{self.args}\""

        info(f'Running {command}...')

        # Run the docker container
        self.container = client.containers.run(
            image=self.container_name,
            command=command,
            volumes=volumes,
            detach=True,
            # remove=True,
            environment=env,
            network_mode='host'
        )

        for line in self.container.logs(stream=True):
            output_line = line.decode('utf-8')
            debug(output_line)
            if 'Error' in output_line:
                err(output_line)

        # Wait for the container to finish
        self.container.wait()

        # insert the metadata into the processing job config file
        if self.metadata:
            processing_job_config = self.out_path / 'processingjobconfig.json'
            if processing_job_config.exists():
                with open(processing_job_config.as_posix(), "r", encoding="utf-8") as f:
                    json_dict = json.load(f)

                json_dict['metadata'] = self.metadata
                debug(json_dict)

                with open(processing_job_config.as_posix(), "w", encoding="utf-8") as j:
                    json.dump(json_dict, j, indent=4)

        # Copy the processing job config file to the output directory
        debug(f'Copying {self.processjobconfig_json_path} to {self.out_path.as_posix()}')
        shutil.copy(self.processjobconfig_json_path.as_posix(), self.out_path.as_posix())

        # Upload the results to s3
        p = urlparse(output_s3)  # remove trailing slash
        upload_files_to_s3(bucket=p.netloc,
                           s3_path=p.path.lstrip('/'),
                           local_path=self.out_path.as_posix(),
                           suffixes=['.tar.gz', '.json'])

        info(f'Finished processing {self.video_url} with {self.model_s3} and {self.track_s3} to {output_s3}')

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
        Check if the container is successfully complete
        :return: True if the container is complete, False otherwise
        """

        # Complete if the output directory has a tar.gz file in it
        if len(list(self.out_path.glob('*.tar.gz'))) > 0:
            return True
        else:
            return False


async def main():
    cfg = Config(local_config_ini_path.as_posix())
    track_prefix = cfg('minio', 's3_track_prefix')
    job_uuid = job_hash("test")

    # Create a docker runner and run it
    p = DockerRunner(job_uuid=job_uuid,
                     video_url='http://localhost:8090/video/V4361_20211006T163856Z_h265_1min.mp4',
                     model_s3='s3://m3-video-processing/models/yolov5x_mbay_benthic_model.tar.gz',
                     args='--iou-thres 0.5 --conf-thres 0.01 --agnostic-nms --max-det 100')
    output_s3 = f's3://m3-video-processing/{track_prefix}/test/{job_uuid}'
    await p.run(output_s3)
    # Wait for the container to finish
    num_tries = 0
    while not p.is_successful() and num_tries < 3:
        await asyncio.sleep(30)
        num_tries += 1

    if p.is_successful():
        info(f'Processing complete: {p.is_successful()}')
    else:
        err(f'Processing complete: {p.is_successful()}')


if __name__ == '__main__':
    os.environ['AWS_DEFAULT_PROFILE'] = 'minio-accutrack'
    temp_path = pathlib.Path(__file__).parent / 'tmp'
    logger.create_logger_file(temp_path / 'logs', 'local')
    asyncio.run(main())
