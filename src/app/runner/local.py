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
from pathlib import Path
from deepsea_ai.config.config import Config
from app.conf import temp_path, s3_track_prefix
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

        self.args = args
        self.metadata = metadata
        self.video_url = video_url
        self.model_s3 = model_s3
        if track_s3:
            self.track_s3 = track_s3
        else:
            self.track_s3 = cfg('minio', 'strongsort_track_config_s3')

        if not self.track_s3.endswith('.yaml'):
            exception(f'Invalid track config {self.track_s3}')
            return

        self.processjobconfig_json_path = Path(__file__).parent / 'processingjobconfig.json'

        if not self.processjobconfig_json_path.exists():
            err(f'Processing job config file {self.processjobconfig_json_path} missing')

        self.container_image = cfg('minio', 'strongsort_container')  # docker image for running the strongsort track pipeline

        self.in_path = (temp_path / job_uuid / 'input')
        self.out_path = (temp_path / job_uuid / 'output')
        self.in_path.mkdir(parents=True, exist_ok=True)
        self.out_path.mkdir(parents=True, exist_ok=True)

    async def run(self, output_s3: str):
        """
        Proces the video with a local docker runner. Results are uploaded to the output_s3 location
        :param output_s3: s3 location to upload the results
        :return:
        """
        info(f'Processing {self.video_url} with {self.model_s3} and {self.track_s3} to {output_s3}<----')

        # Download the video at the self.video_url to the self.in_path
        # if download_video(self.video_url, self.in_path):
        #     info(f'Video {self.video_url} downloaded to {self.in_path.as_posix()}')
        # else:
        #     err(f'Failed to download {self.video_url} to {self.in_path.as_posix()}')
        #     return

        # if 'AWS_SHARED_CREDENTIALS_FILE' in os.environ:
        #     cred_path = Path(os.environ['AWS_SHARED_CREDENTIALS_FILE'])
        # else:
        # Attempt to set to the HOME directory
        cred_path = Path.home() / '.aws' / 'credentials'

        pipeline_path = Path(__file__).parent / 'pipeline'

        # Set volume bindings
        volumes = {
            cred_path.as_posix(): {'bind': '/root/.aws/credentials', 'mode': 'ro'},
            # TODO: remove this as this file is automatically created by docker image
            # self.processjobconfig_json_path: {'bind': '/opt/ml/config/processingjobconfig.json', 'mode': 'ro'},
            pipeline_path.as_posix(): {'bind': '/app/pipeline', 'mode': 'ro'},
            self.in_path.as_posix(): {'bind': '/opt/ml/processing/input'},
            self.out_path.as_posix(): {'bind': '/opt/ml/processing/output'},
        }
        # os.environ['AWS_SHARED_CREDENTIALS_FILE'] = ""
        os.environ['SERVICE_ENDPOINT_URL'] = 'http://192.168.224.2:9000'
        client = docker.from_env()
        # os.environ['AWS_SHARED_CREDENTIALS_FILE'] = cred_path.as_posix()

        # Setup the command to run
        command = (f"dettrack --model-s3 {self.model_s3} "
                   f"--config-s3 {self.track_s3} "
                   f"-i /opt/ml/processing/input "
                   f"-o /opt/ml/processing/output")

        # Add the optional arguments if they exist
        if self.args:
            command += f" --args \"{self.args}\""

        info(f'Running {command}...')

        # Run the docker container
        container = client.containers.run(
            image=self.container_image,
            command=command,
            volumes=volumes,
            detach=True,
            network_mode='host',
            # networks=['minio-net'],
        )

        for line in container.logs(stream=True):
            output_line = line.decode('utf-8')
            debug(f'Docker container: {output_line}')
            if 'Error' in output_line:
                err(output_line)
                container.stop()
                container.remove()
                return
            # debug(line.decode('utf-8'))
            # print(line.decode('utf-8'))

        container.stop()
        container.remove()
        os.environ['SERVICE_ENDPOINT_URL'] = conf.minio_endpoint_url

        # while container.status == 'running':
        #     debug(container.logs())
        #     await asyncio.sleep(5)

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

        # upload the results to s3
        p = urlparse(output_s3)  # remove trailing slash
        upload_files_to_s3(bucket=p.netloc,
                           s3_path=p.path.lstrip('/'),
                           local_path=self.out_path.as_posix(),
                           suffixes=['.tar.gz', '.json'])

        # remove the input and output directories
        info(f'Removing {self.in_path.as_posix()} and {self.out_path.as_posix()}')
        # self.in_path.unlink()
        # self.out_path.unlink()

        info(f'Finished processing {self.video_url} with {self.model_s3} and {self.track_s3} to {output_s3}')
        await asyncio.sleep(5)

    def teardown(self):
        info(f'Tear down not current implemented.')
        pass


async def main():
    job_uuid = job_hash("test")
    # Create a docker runner and run it
    p = DockerRunner(job_uuid=job_uuid,
                     video_url='http://localhost:8090/V4361_20211006T162656Z_h265_1sec.mp4',
                     model_s3='s3://m3-video-processing/models/yolov5x_mbay_benthic_model.tar.gz',#Megadetector.pt',
                     track_s3='s3://m3-video-processing/track_config/strong_sort_benthic.yaml',
                     args='--iou-thres 0.5 --conf-thres 0.01')
    output_s3 = f's3://m3-video-processing/{s3_track_prefix}/test/{job_uuid}'
    await p.run(output_s3)
    p.teardown()


if __name__ == '__main__':
    temp_path = pathlib.Path(__file__).parent / 'tmp'
    logger.create_logger_file(temp_path / 'logs', 'local')

    # env_path = temp_path / 'aws' / 'credentials.txt'
    # os.environ['AWS_SHARED_CREDENTIALS_FILE'] = env_path.as_posix()
    # env_path.parent.mkdir(parents=True, exist_ok=True)
    # # Add the credentials file to the environment
    # with env_path.open('w+') as f:
    #     f.write('[minio-microtrack]\n')
    #     f.write('aws_access_key_id = microtrack\n')
    #     f.write('aws_secret_access_key = ReplaceMePassword\n')
    #     f.write('endpoint_url = http://127.0.0.1:9000\n')
    #     f.write('region = us-east-1\n')
    asyncio.run(main())
