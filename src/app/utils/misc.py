## fastapi-localtrack, Apache-2.0 license
# Filename: app/conf/init.py
# Description: Miscellaneous utility functions

import os

import boto3
import pathlib
import requests

from app.logger import info, debug, err, exception
from app import logger


def list_by_suffix(bucket: str, prefix: str, suffixes: list[str]) -> list[str]:
    """
    Fetch all the objects in the bucket with the given prefix and save them to the local path
    :param bucket: the bucket to fetch from
    :param prefix: the prefix to fetch
    :param suffixes: the suffixes to fetch, e.g. ['tar.gz', 'pt']
    :return: list of objects with the given suffixes, s3://bucket/prefix/object.suffix
    """
    s3 = boto3.client(
        's3',
        endpoint_url=os.environ['MINIO_ENDPOINT_URL'],
        aws_access_key_id=os.environ['MINIO_ACCESS_KEY'],
        aws_secret_access_key=os.environ['MINIO_SECRET_KEY'],
        region_name='us-west-2',
        config=boto3.session.Config(signature_version='s3v4')
    )
    objects = []

    try:
        debug(f'Listing objects in s3://{bucket}/{prefix}')
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' in response:
            info(f'Found {len(response["Contents"])} objects in s3://{bucket}/{prefix}')
            for obj in response['Contents']:
                for s in suffixes:
                    if pathlib.Path(obj['Key']).suffix == s:
                        debug(f'Found {obj["Key"]} in s3://{bucket}')
                        objects.append(f"s3://{bucket}/{obj['Key']}")
        else:
            info(f'Bucket {bucket} is empty')
    except Exception as e:
        exception(f'Error listing objects: {e}')
        raise e

    return objects


def check_video_availability(video_url):
    """
    Check if a video is available at a url
    :param video_url:  video url to check
    :return: True if available, False otherwise
    """
    try:
        response = requests.head(video_url)  # Sends a HEAD request (faster than GET for checking availability)
        response.raise_for_status()  # Raises an exception for 4xx and 5xx status codes
        info(f"Video {video_url} is available.")
        return True
    except requests.exceptions.HTTPError as e:
        info(f"Video {video_url} is not available: {e}")
        return False
    except requests.exceptions.RequestException as e:
        info(f"Video {video_url} is not reachable: {e}")
        return False


if __name__ == '__main__':
    # Get the path to the current file
    temp_path = pathlib.Path(__file__).resolve().parent / 'tmp'
    logger.create_logger_file(temp_path, 'misc')
    check_video_availability('http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec.mp4')
