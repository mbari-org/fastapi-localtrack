from urllib.parse import urlparse

import docker
import os
import pathlib
import boto3
import yaml
from app.conf import yaml_path
import requests

from app.logger import info

# Test video urls hosted on localhost
test_video_url_1min = 'http://localhost:8090/video/V4361_20211006T163856Z_h265_1min.mp4'
test_video_url_1sec = 'http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec.mp4'
test_video_url_10frame = 'http://localhost:8090/video/V4361_20211006T162656Z_h265_10frame.mp4'
test_video_url_missing = 'http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec_missing.mp4'

password = 'ReplaceMePassword'
user = 'localtrack'


def init_credentials():
    # Set the AWS credentials for the minio server
    temp_path = pathlib.Path(__file__).parent / 'tmp'
    env_path = temp_path / 'aws' / 'credentials.txt'
    os.environ['AWS_SHARED_CREDENTIALS_FILE'] = env_path.as_posix()
    os.environ['AWS_DEFAULT_PROFILE'] = 'minio-test'
    env_path.parent.mkdir(parents=True, exist_ok=True)

    # Add the credentials file to the environment
    with env_path.open('w+') as f:
        f.write('[minio-test]\n')
        f.write(f'aws_access_key_id = {user}\n')
        f.write(f'aws_secret_access_key = {password}\n')
        f.write('endpoint_url = http://127.0.0.1:7000\n')
        f.write('region = us-west-2\n')


def run_minio():
    # Run the minio docker container on port 7000
    client = docker.from_env()
    base_path = pathlib.Path(__file__).parent.parent
    minio_data_path = base_path / 'minio_data'
    minio_data_path.mkdir(parents=True, exist_ok=True)
    volumes = {minio_data_path.as_posix(): {'bind': '/data', 'mode': 'rw'}}
    env = {'MINIO_ROOT_USER': user, 'MINIO_ROOT_PASSWORD': password}
    # Stop the container named minio-test if it exists
    try:
        client.containers.get('minio-test').stop()
    except docker.errors.NotFound:
        pass

    # Remove the container named minio-test if it exists
    try:
        client.containers.get('minio-test').remove()
    except docker.errors.NotFound:
        pass

    # Run the minio container
    client.containers.run('minio/minio:latest',
                          detach=True,
                          name='minio-test',
                          command='server --console-address ":9001" /data',
                          volumes=volumes,
                          environment=env,
                          ports={'9000/tcp': 7000, '9001/tcp': 7001})
    # Wait for the minio server to start
    info('Waiting for minio server to start')
    while True:
        try:
            client.containers.get('minio-test')
            info('Minio server started')
            break
        except docker.errors.NotFound:
            pass

    # Fetch yaml config
    with open(yaml_path, 'r') as yaml_file:
        data = yaml.safe_load(yaml_file)
        root_bucket = data['minio']['root_bucket']
        model_prefix = data['minio']['model_prefix']
        video_prefix = data['minio']['video_prefix']
        model = data['aws_public']['model']
        track_config = data['aws_public']['track_config']
        video_example = data['aws_public']['video_example']


    def smart_download(root_dir: str, url: str):
        p = urlparse(url)
        path = base_path / 'data' / 's3' / root_dir / pathlib.Path(p.path[1:]).name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f'https://{p.netloc}.s3.amazonaws.com/{p.path[1:]}'
            info(f'Downloading {url} to {path.as_posix()}')
            response = requests.get(url)
            if response.status_code == 200:
                with path.open('wb') as f:
                    f.write(response.content)

    smart_download(model_prefix, model)
    smart_download(f'{model_prefix}/track-config', track_config)
    smart_download(video_prefix, video_example)

    # Upload the test data to the minio server using boto3 with credentials
    s3 = boto3.client('s3',
                      endpoint_url='http://127.0.0.1:7000',
                      aws_access_key_id=user,
                      aws_secret_access_key=password)
    for b in [model_prefix, video_prefix]:
        try:
            s3.create_bucket(Bucket='m3-video-processing')
        except s3.exceptions.BucketAlreadyOwnedByYou:
            pass

    def upload(prefix: str, url: str):
        p = urlparse(url)
        name = pathlib.Path(p.path[1:]).name
        path = base_path / 'data' / 's3' / prefix / name
        s3.upload_file(path.as_posix(),
                       root_bucket,
                       f'{prefix}/{name}')

    upload(model_prefix, model)
    upload(f'{model_prefix}/track-config', track_config)
    upload(video_prefix, video_example)


if __name__ == '__main__':
    init_credentials()
    run_minio()