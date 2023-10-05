# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/docker_runner.py
# Description: Docker runner to process videos locally

from datetime import datetime

import asyncio

import yaml
from aiodocker import Docker, DockerError
import os
import tarfile
import shutil
import json
from urllib.parse import urlparse
from pathlib import Path

from daemon.misc import download_video, upload_files_to_s3

from .logger import info, debug, err

DEFAULT_CONTAINER_NAME = 'strongsort'


class DockerRunner:

    def __init__(self,
                 image_name: str,
                 track_s3: str,
                 job_id: int,
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
        self.image_name = image_name
        self.track_s3 = track_s3
        self.container = None
        self.total_time = None
        self.args = args
        self.video_url = video_url
        self.model_s3 = model_s3
        self.output_s3 = output_s3
        self.temp_path = Path('/tmp')
        self.in_path = self.temp_path / str(job_id) / 'input'
        self.out_path = self.temp_path / str(job_id) / 'output'
        self.in_path.mkdir(parents=True, exist_ok=True)
        self.out_path.mkdir(parents=True, exist_ok=True)

    def __del__(self):
        """
        Clean up the input/output directories
        :return:
        """
        debug(f'Deleting {self.__class__.__name__} instance')

        # Clean up the input directory
        debug(f'Removing {self.in_path.as_posix()}')
        if self.in_path.exists():
            shutil.rmtree(self.in_path.as_posix())

        # Clean up the output directory
        debug(f'Removing {self.out_path.as_posix()}')
        if self.out_path.exists():
            shutil.rmtree(self.out_path.as_posix())

    async def run(self, has_gpu: bool = False):
        """
        Proces the video with a local docker runner. Results are uploaded to the output_s3 location
        :param has_gpu: True if the docker container should use the nvidia runtime
        :return:
        """
        info(f'Processing {self.video_url} with {self.model_s3} and {self.track_s3} to {self.output_s3}')

        info(f'Downloading {self.video_url} to {self.in_path}')
        if not download_video(self.video_url, self.in_path):
            err(f'Failed to download {self.video_url} to {self.in_path}.'
                f' Are you sure your nginx server is running?')
            return

        home = Path.home().as_posix()
        profile = os.environ.get('AWS_DEFAULT_PROFILE', 'default')
        info(f'Using credentials file in {home}/.aws and profile {profile}')

        # Setup the command to run to be AWS SageMaker compliant, /opt/ml/input, etc. These are the default,
        # but included here for clarity
        command = [f"dettrack", "--model-s3", self.model_s3] + \
                  ["--config-s3", self.track_s3] + \
                  ["-i", f"{self.in_path}"] + \
                  ["-o", f"{self.out_path}"]

        # Add the optional arguments if they exist. If these are missing, defaults are included in the Docker container
        if self.args:
            command += ["--args", f"{self.args}"]

        info(f'Using command {command}')

        # Run the docker container asynchronously and wait for it to finish
        start_utc = datetime.utcnow()
        await self.wait_for_container(has_gpu, self.image_name, command, self.temp_path, self.out_path)
        info(f'Using command {command}')
        self.total_time = datetime.utcnow() - start_utc

        # Upload the results to s3
        p = urlparse(self.output_s3)
        await upload_files_to_s3(bucket=p.netloc,
                                 s3_path=p.path.lstrip('/'),
                                 local_path=self.out_path.as_posix(),
                                 suffixes=['.gz', '.json', ".mp4", ".txt"])

    def get_num_tracks(self):
        """
        Get the number of tracks in the output directory. Parses the json files in the tar.gz files
        and counts the number of unique track ids
        :return: The number of tracks in the output directory
        """
        unique_track_ids = set()
        for tar_file in self.out_path.glob('*.tar.gz'):
            with tarfile.open(tar_file.as_posix(), "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith('.json') and 'processing' not in member.name:
                        f = tar.extractfile(member)
                        data = json.load(f)
                        for v in data[1]:
                            unique_track_ids.add(v[1]['track_uuid'])
        return len(unique_track_ids)

    def get_id(self):
        """
        Get the container id
        :return: The container id if it exists, None otherwise
        """
        if self.container:
            return self.container.id
        else:
            return None

    def get_results(self):
        """
        Get the results from processing
        :return: The s3 location and local path of the results if they exist, None otherwise, the number of tracks,
        and the total time
        """
        if len(list(self.out_path.glob('*.tar.gz'))) > 0:
            track_path = Path(list(self.out_path.glob('*.tar.gz'))[0])
            s3_loc = f'{self.output_s3}/output/{track_path.name}'
            return s3_loc, track_path, self.get_num_tracks(), self.total_time.total_seconds()

        return None, None, None, None

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

    @staticmethod
    async def wait_for_container(has_gpu: bool, image_name: str, command: [str], temp_path: Path, output_path: Path):
        async with Docker() as docker_aoi:
            try:
                await docker_aoi.images.inspect(image_name)
            except DockerError as e:
                if e.status == 404:
                    await docker_aoi.pull(image_name)
                else:
                    err(f'Error retrieving {image_name} image.')
                    raise DockerError(e.status, f'Error retrieving {image_name} image.')

            try:
                container_name = f'{DEFAULT_CONTAINER_NAME}-{datetime.now().strftime("%Y%m%d%H%M%S")}'

                # If the volume mount fastapi-localtrack_scratch exists, bind it to the temp directory -
                # this is pass through from the parent docker container in production
                binds = [f"{temp_path}:{temp_path}"]
                volumes = await docker_aoi.volumes.list()
                for v in volumes['Volumes']:
                    if v['Name'] == 'fastapi-localtrack_scratch':
                        binds = [f"fastapi-localtrack_scratch:{temp_path}"]
                        break

                debug(f"Using binds {binds}")
                debug(f"AWS_DEFAULT_REGION={os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')}")
                debug(f"AWS_ACCESS_KEY_ID={os.environ.get('MINIO_ACCESS_KEY', 'localtrack')[0:5]}**")
                debug(f"AWS_SECRET_ACCESS_KEY={os.environ.get('MINIO_SECRET_KEY', 'ReplaceMePassword')[0:5]}**")
                debug(f"AWS_ENDPOINT_URL={os.environ.get('MINIO_ENDPOINT_URL', 'http://localhost:9000')}")

                # Create the configuration for the docker container
                config = {
                    'Image': image_name,
                    'HostConfig': {
                        'NetworkMode': 'host',
                        'Binds': binds,
                    },
                    'Env': [
                        f"AWS_DEFAULT_REGION={os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')}",
                        f"AWS_ACCESS_KEY_ID={os.environ.get('MINIO_ACCESS_KEY', 'localtrack')}",
                        f"AWS_SECRET_ACCESS_KEY={os.environ.get('MINIO_SECRET_KEY', 'ReplaceMePassword')}",
                        f"AWS_ENDPOINT_URL={os.environ.get('MINIO_EXTERNAL_ENDPOINT_URL', 'http://localhost:9000')}"
                    ],
                    'Cmd': command,
                    'AttachStdin': True,
                    'AttachStdout': True,
                    'AttachStderr': True,
                    'Tty': False,
                    'OpenStdin': True,
                    'StdinOnce': True

                }

                # Check if the runtime nvidia is available, and if so, use it
                if has_gpu:
                    config['HostConfig']['Runtime'] = 'nvidia'
                    info(f"NVIDIA runtime available")

                # Run with network mode host to allow access to the local minio server
                container = await docker_aoi.containers.create_or_replace(
                    config=config,
                    name=container_name,
                )
                info(f'Running docker container {container.id} {container_name} with command {command}')
                info(f'Waiting for container {container.id} to finish')

                await container.start()
                await container.wait()

                # Redirect the logs to a file since they can be large
                log_path = output_path / 'logs.txt'
                info(f"Saving docker container {container.id} {container_name} log output to {log_path}")
                with log_path.open('w') as f:
                    logs = await container.log(stdout=True, stderr=True)
                    f.write('\n'.join(logs))

                await container.delete(force=True)
            except Exception as e:
                raise e


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
