# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/docker_runner.py
# Description: Docker runner to process videos locally

from datetime import datetime

from aiodocker import Docker, DockerError
import asyncio
import docker

import yaml
import os
import tarfile
import shutil
import json
from urllib.parse import urlparse
from pathlib import Path

from daemon.misc import download_video, upload_files_to_s3
from daemon.logger import info, debug, err

DEFAULT_CONTAINER_NAME = 'strongsort'


class DockerRunner:

    def __init__(self,
                 image_name: str,
                 track_s3: str,
                 job_id: int,
                 job_name: str,
                 video_url: str,
                 model_s3: str,
                 output_s3: str,
                 args: str | None = None):
        """
        Run docker container with the given model and video
        :param job_id: id for the job in the database
        :param video_url: url of the video to process
        :param model_s3:  location of the model in s3
        :param output_s3: location to upload the results
        :param track_s3:: location of the track configuration in s3
        :param args: optional arguments to pass to the track command
        """
        self._start_utc = None
        self._container_name = f'{DEFAULT_CONTAINER_NAME}-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
        self._container = None
        self._image_name = image_name
        self._track_s3 = track_s3
        self._args = args
        self._job_name = job_name
        self._is_complete = False
        self._video_url = video_url
        self._model_s3 = model_s3
        self._output_s3 = output_s3
        self._temp_path = Path(os.environ.get('TEMP_DIR', Path.cwd() / 'temp'))
        self._in_path = self._temp_path / str(job_id) / 'input'
        self._out_path = self._temp_path / str(job_id) / 'output'
        # Create the input/output directories if they don't exist, and clean them if they do
        self._temp_path.mkdir(parents=True, exist_ok=True)
        if self._in_path.exists():
            shutil.rmtree(self._in_path.as_posix())
        if self._out_path.exists():
            shutil.rmtree(self._out_path.as_posix())
        self._in_path.mkdir(parents=True, exist_ok=True)
        self._out_path.mkdir(parents=True, exist_ok=True)

    async def fini(self):
        """
        Final processing after the container has finished; upload results, and clean up temp dir
        :return:
        """
        p = urlparse(self._output_s3)
        await upload_files_to_s3(bucket=p.netloc,
                                 s3_path=p.path.lstrip('/'),
                                 local_path=self._out_path.as_posix(),
                                 suffixes=['.gz', '.json', ".mp4", ".txt"])
        self.clean()

    @property
    def container_name(self) -> str:
        return self._container_name

    def clean(self):
        """
        Clean up the input/output directories and the container
        :return:
        """
        # Clean up the container
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={'name': self._container_name})
        if len(containers) == 1:
            container = client.containers.get(containers[0].id)
            if container.status == 'running':
                container.stop()
                info(f"Container {container.id} stopped successfully.")
            container.remove()
            info(f"Container {container.id} removed successfully.")

        # Clean up the input directory
        debug(f'Removing {self._in_path.as_posix()}')
        if self._in_path.exists():
            shutil.rmtree(self._in_path.as_posix())

        # Clean up the output directory
        debug(f'Removing {self._out_path.as_posix()}')
        if self._out_path.exists():
            shutil.rmtree(self._out_path.as_posix())

    async def run(self, has_gpu: bool = False):
        """
        Proces the video with a local docker runner. Results are uploaded to the output_s3 location
        :param has_gpu: True if the docker container should use the nvidia runtime
        :return:
        """
        info(f'Processing {self._video_url} with {self._model_s3} and {self._track_s3} to {self._output_s3}')

        info(f'Downloading {self._video_url} to {self._in_path}')
        # Run the download in the background
        if not await asyncio.to_thread(download_video, self._video_url, self._in_path):
            err(f'Failed to download {self._video_url} to {self._in_path}.')
            return

        # Set up the command to run to be AWS SageMaker compliant, /opt/ml/input, etc. These are the default,
        # but included here for clarity
        command = [f"dettrack", "--model-s3", self._model_s3] + \
                  ["--config-s3", self._track_s3] + \
                  ["-i", f"{self._in_path}"] + \
                  ["-o", f"{self._out_path}"]

        # Add the optional arguments if they exist. If these are missing, defaults are included in the Docker container
        if self._args:
            command += ["--args", f"{self._args}"]

        info(f'Using command {command}')

        self._start_utc = datetime.utcnow()
        await self.wait_for_container(has_gpu, command, os.environ.get('MODE', 'dev'))

    def get_num_tracks(self):
        """
        Get the number of tracks in the output directory. Parses the json files in the tar.gz files
        and counts the number of unique track ids
        :return: The number of tracks in the output directory
        """
        unique_track_ids = set()
        for tar_file in self._out_path.glob('*.tar.gz'):
            with tarfile.open(tar_file.as_posix(), "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith('.json') and 'processing' not in member.name:
                        f = tar.extractfile(member)
                        data = json.load(f)
                        for v in data[1]:
                            unique_track_ids.add(v[1]['track_uuid'])
        return len(unique_track_ids)

    def get_results(self):
        """
        Get the results from processing
        :return: The s3 location and local path of the results if they exist, None otherwise, the number of tracks,
        and the total time
        """
        total_time = datetime.utcnow() - self._start_utc
        if len(list(self._out_path.glob('*.tar.gz'))) > 0:
            track_path = Path(list(self._out_path.glob('*.tar.gz'))[0])
            s3_loc = f'{self._output_s3}/output/{track_path.name}'
            return s3_loc, track_path, self.get_num_tracks(), total_time.total_seconds()

        return None, None, None, None

    def failed(self) -> bool:
        """
        Check if container exited
        :return: True if exited and no data created
        """
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={'name': self._container_name})
        if len(containers) == 1:
            container = containers[0]
            if container.status == 'exited' and not self.is_successful():
                return True

        return False

    def is_successful(self) -> bool:
        """
        Check if the container has successfully completed
        :return: True if a .tar.gz was created, False otherwise
        """
        # Complete if the output directory has a tar.gz file in it
        if len(list(self._out_path.glob('*.tar.gz'))) > 0:
            return True

        return False

    def get_container_status(self) -> str | None:
        """
        Get the status of the container
        :return: The status of the container, or None if it does not exist
        """
        docker_client = docker.from_env()
        try:
            container = docker_client.containers.get(self._container_name)
            return container.status
        except docker.errors.NotFound:
            pass
        return None

    def is_running(self):
        """
        Check if the container is running
        :return: True if the container is not running, False otherwise
        """
        status = self.get_container_status()
        if status == 'running':
            return True

        return False

    async def wait_for_container(self, has_gpu: bool, command: [str], mode: str):
        async with Docker() as docker_aoi:

            try:

                # If the volume mount fastapi-localtrack_scratch exists, bind it to the temp directory -
                # this is pass through from the parent docker container in production
                binds = [f"{self._temp_path}:{self._temp_path}"]
                volumes = await docker_aoi.volumes.list()
                for v in volumes['Volumes']:
                    if 'scratch' in v['Name'] and mode == 'prod':
                        binds = [f"{v['Name']}:{self._temp_path}"]
                        break

                debug(f"Using binds {binds}")
                debug(f"AWS_DEFAULT_REGION={os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')}")
                debug(f"AWS_ACCESS_KEY_ID={os.environ.get('MINIO_ACCESS_KEY', 'localtrack')[0:5]}**")
                debug(f"AWS_SECRET_ACCESS_KEY={os.environ.get('MINIO_SECRET_KEY', 'ReplaceMePassword')[0:5]}**")
                debug(f"AWS_ENDPOINT_URL={os.environ.get('MINIO_ENDPOINT_URL', 'http://localhost:7000')}")

                # Create the configuration for the docker container
                config = {
                    'Image': self._image_name,
                    'HostConfig': {
                        'NetworkMode': 'host',
                        'Binds': binds,
                    },
                    'Env': [
                        f"JOB_NAME={self._job_name}",
                        f"AWS_DEFAULT_REGION={os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')}",
                        f"AWS_ACCESS_KEY_ID={os.environ.get('MINIO_ACCESS_KEY', 'localtrack')}",
                        f"AWS_SECRET_ACCESS_KEY={os.environ.get('MINIO_SECRET_KEY', 'ReplaceMePassword')}",
                        f"AWS_ENDPOINT_URL={os.environ.get('MINIO_EXTERNAL_ENDPOINT_URL', 'http://localhost:7000')}"
                    ],
                    'Cmd': command
                }

                # Check if the runtime nvidia is available, and if so, use it
                if has_gpu:
                    config['HostConfig']['Runtime'] = 'nvidia'
                    info(f"NVIDIA runtime available")

                # Run with network mode host to allow access to the local minio server
                self._container = await docker_aoi.containers.create_or_replace(
                    config=config,
                    name=self._container_name,
                )
                info(f'Running docker container {self._container.id} {self._container_name} with command {command}')
                await self._container.start()
            except Exception as e:
                err(e)


async def main():
    yaml_path = Path(os.path.dirname(__file__)).parent.parent / 'config.yml'
    print(f"YAML_PATH environment variable not set. Using {yaml_path}")
    if not yaml_path.exists():
        raise FileNotFoundError(f"Could not find {yaml_path}")

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
        track_prefix = config['minio']['track_prefix']
        job_id = 1
        output_s3 = f's3://localtrack/{track_prefix}/test/{job_id}'

        # Create a docker runner and run it
        p = DockerRunner(job_id=job_id,
                         job_name='test',
                         track_s3=config['monitors']['docker']['strongsort_track_config'],
                         output_s3=output_s3,
                         video_url='http://localhost:8090/video/V4361_20211006T162656Z_h265_10frame.mp4',
                         model_s3='s3://localtrack/models/yolov5x_mbay_benthic_model.tar.gz',
                         args='--iou-thres 0.5 --conf-thres 0.01 --agnostic-nms --max-det 100')
        await p.run()

        if p.is_successful():
            info(f'Processing complete: {p.is_successful()}')
        else:
            err(f'Processing complete: {p.is_successful()}')


if __name__ == '__main__':
    os.environ['AWS_DEFAULT_PROFILE'] = 'minio-localtrack'
    os.environ['MINIO_ACCESS_KEY'] = 'localtrack'
    os.environ['MINIO_ENDPOINT_URL'] = 'http://localhost:9000'
    os.environ['MINIO_EXTERNAL_ENDPOINT_URL'] = 'http://localhost:9000'
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
