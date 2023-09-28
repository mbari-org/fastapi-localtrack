# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/docker_runner.py
# Description:  Miscellaneous utility functions for the daemon

import logging
import os
import asyncio
import boto3
import pathlib
import requests

logger = logging.getLogger(__name__)


async def upload_files_to_s3(bucket: str, local_path: str, s3_path: str, suffixes: list[str] = None) -> int:
    """
    Upload all the files in the local path with the given suffixes to the s3 path
    :param bucket: the bucket to upload to
    :param local_path: the local path to upload from
    :param s3_path: the s3 path to upload to
    :param suffixes: the suffixes to upload, e.g. ['tar.gz', 'mp4']
    :return: Number of files uploaded
    """

    logger.info(f'Uploading files from {local_path} to s3://{bucket}/{s3_path} with suffixes {suffixes}')

    if 'AWS_DEFAULT_PROFILE' in os.environ:
        session = boto3.Session(profile_name=os.environ['AWS_DEFAULT_PROFILE'])
        s3 = session.client('s3')
    else:
        s3 = boto3.client('s3')

    num_uploaded = 0
    try:
        for obj in pathlib.Path(local_path).iterdir():
            if obj.is_file():
                for s in suffixes:
                    if obj.suffix == s:
                        logger.debug(f'Uploading {obj.as_posix()} to s3://{bucket}/{s3_path}')
                        await asyncio.to_thread(s3.upload_file, obj.as_posix(), bucket, f'{s3_path}/{obj.name}')
                        num_uploaded += 1
    except Exception as e:
        logger.exception(f'Error uploading files: {e}')
        raise e
    finally:
        logger.info(f'Uploaded {num_uploaded} files to s3://{bucket}/{s3_path}')
        return num_uploaded


async def verify_upload(bucket: str, prefix: str) -> bool:
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
        await upload_files_to_s3(bucket, check_path.parent, prefix, ['.txt'])
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
