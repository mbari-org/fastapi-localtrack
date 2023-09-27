# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/docker_runner.py
# Description:  Miscellaneous utility functions for the daemon

import logging
import os

import boto3
import pathlib
import requests

logger = logging.getLogger(__name__)


def list_by_suffix(bucket: str, prefix: str, suffixes: list[str]) -> list[str]:
    """
    Fetch all the objects in the bucket with the given prefix and save them to the local path
    :param bucket: the bucket to fetch from
    :param prefix: the prefix to fetch
    :param suffixes: the suffixes to fetch, e.g. ['tar.gz', 'pt']
    :return: list of objects with the given suffixes, s3://bucket/prefix/object.suffix
    """
    if 'AWS_DEFAULT_PROFILE' in os.environ:
        logger.info(f'Using AWS profile {os.environ["AWS_DEFAULT_PROFILE"]}')
        session = boto3.Session(profile_name=os.environ['AWS_DEFAULT_PROFILE'])
    else:
        session = boto3.Session()
    s3 = session.client('s3')
    objects = []

    try:
        logger.debug(f'Listing objects in s3://{bucket}/{prefix}')
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' in response:
            logger.info(f'Found {len(response["Contents"])} objects in s3://{bucket}/{prefix}')
            for obj in response['Contents']:
                for s in suffixes:
                    if pathlib.Path(obj['Key']).suffix == s:
                        logger.debug(f'Found {obj["Key"]} in s3://{bucket}')
                        objects.append(f"s3://{bucket}/{obj['Key']}")
        else:
            logger.info(f'Bucket {bucket} is empty')
    except Exception as e:
        logger.exception(f'Error listing objects: {e}')
        raise e

    return objects


def upload_files_to_s3(bucket: str, local_path: str, s3_path: str, suffixes: list[str] = None) -> None:
    """
    Upload all the files in the local path with the given suffixes to the s3 path
    :param bucket: the bucket to upload to
    :param local_path: the local path to upload from
    :param s3_path: the s3 path to upload to
    :param suffixes: the suffixes to upload, e.g. ['tar.gz', 'mp4']
    :return: None
    """

    logger.info(f'Uploading files from {local_path} to s3://{bucket}/{s3_path}')

    if 'AWS_DEFAULT_PROFILE' in os.environ:
        session = boto3.Session(profile_name=os.environ['AWS_DEFAULT_PROFILE'])
        s3 = session.client('s3')
    else:
        s3 = boto3.client('s3')

    try:
        for obj in pathlib.Path(local_path).iterdir():
            if obj.is_file():
                for s in suffixes:
                    if obj.suffix == s:
                        logger.debug(f'Uploading {obj.as_posix()} to s3://{bucket}/{s3_path}')
                        s3.upload_file(obj.as_posix(), bucket, f'{s3_path}/{obj.name}')
    except Exception as e:
        logger.exception(f'Error uploading files: {e}')
        raise e


def verify_upload(bucket: str, prefix: str) -> bool:
    """
    Verify that the upload_files_to_s3 function works
    :param bucket: The bucket to upload to
    :param prefix: The prefix to upload to
    :return:
    """
    check_path = pathlib.Path.cwd() / 'check.txt'
    with check_path.open('w') as f:
        f.write("testing s3 upload")

    try:
        upload_files_to_s3(bucket, check_path.parent, prefix, ['.txt'])
        return True
    except Exception as e:
        return False
    finally:
        check_path.unlink()


def download_video(url: str, save_path: pathlib.Path) -> bool:
    """
    Download a video from a url to a local path
    :param url:  url to download from
    :param save_path:  local path to save to
    :return: True if successful, False otherwise
    """
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        # If the save_path is a directory, use the filename from the url
        if save_path.is_dir():
            save_path = save_path / pathlib.Path(url).name

        with save_path.open('wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        logger.info(f"Video {url} downloaded successfully to {save_path}.")
        return True
    else:
        logger.error(f"Failed to download {url} to {save_path}")
        return False


if __name__ == '__main__':
    # Get the path to the current file
    temp_path = pathlib.Path(__file__).resolve().parent / 'tmp'
    download_video('http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec.mp4',
                   temp_path / 'V4361_20211006T162656Z_h265_1sec-test.mp4')
    download_video('http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec.mp4',
                   temp_path)
