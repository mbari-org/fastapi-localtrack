# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/docker_runner.py
# Description:  Miscellaneous utility functions for the daemon

import os
import boto3
import pathlib
import tempfile
import requests
from botocore.exceptions import NoCredentialsError, ClientError
from .logger import debug, info, err, exception


async def upload_file(obj, bucket, s3_path) -> bool:
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=os.environ['MINIO_ENDPOINT_URL'],
            aws_access_key_id=os.environ['MINIO_ACCESS_KEY'],
            aws_secret_access_key=os.environ['MINIO_SECRET_KEY'],
            region_name='us-west-2',
            config=boto3.session.Config(signature_version='s3v4')
        )
        # First check if the file exists in the bucket
        try:
            debug(f'Checking if file {s3_path} exists in s3://{bucket}')
            s3.head_object(Bucket=bucket, Key=s3_path)
            info(f'File {s3_path} already exists in s3://{bucket}')
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                debug(f'File {s3_path} does not exist in s3://{bucket}')
            else:
                exception(f'Error checking if file exists: {e}')
                pass
        except Exception as ex:
            exception(f'Error checking if file exists: {ex}')
            pass

        s3.upload_file(obj, bucket, s3_path)
        info(f'File uploaded successfully to s3://{bucket}/{s3_path}')
        return True
    except FileNotFoundError:
        exception("The file was not found")
        return False
    except NoCredentialsError:
        exception("Credentials not available")
        raise Exception("Credentials not available. Check your AWS credentials")


async def upload_files_to_s3(bucket: str, local_path: str, s3_path: str, suffixes: list[str] = None) -> int:
    """
    Upload all the files in the local path with the given suffixes to the s3 path
    :param bucket: the bucket to upload to
    :param local_path: the local path to upload from
    :param s3_path: the s3 path to upload to
    :param suffixes: the suffixes to upload, e.g. ['tar.gz', 'mp4']
    :return: Number of files uploaded
    """

    info(f'Uploading files from {local_path} to s3://{bucket}/{s3_path} with suffixes {suffixes}')

    num_uploaded = 0
    try:
        local_path = pathlib.Path(local_path)
        if not local_path.exists():
            err(f"Could not find {local_path}")
            return 0

        # Recursively glob all files in the local path
        for obj in pathlib.Path(local_path).rglob('*'):
            if obj.is_file():
                for s in suffixes:
                    if obj.suffix == s:
                        if await upload_file(obj, bucket, f'{s3_path}/{obj.name}'):
                            num_uploaded += 1
    except Exception as e:
        exception(f'Error uploading files: {e}')
        return 0
    finally:
        return num_uploaded


async def verify_upload(bucket: str, prefix: str) -> bool:
    """
    Verify that the upload_files_to_s3 function works
    :param bucket: The bucket to upload to
    :param prefix: The prefix to upload to
    :return:
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        check_path = pathlib.Path(temp_dir) / 'check.txt'
        with check_path.open('w') as f:
            f.write("testing s3 upload")

        try:
            num_uploaded = await upload_files_to_s3(bucket, check_path.parent, prefix, ['.txt'])
            if num_uploaded == 1:
                return True
        except Exception:
            return False
        finally:
            check_path.unlink()

    return False


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
        info(f"Video {url} downloaded successfully to {save_path}.")
        return True
    else:
        err(f"Failed to download {url} to {save_path}")
        return False


if __name__ == '__main__':
    # Get the path to the current file
    temp_path = pathlib.Path(__file__).resolve().parent / 'tmp'
    download_video('http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec.mp4',
                   temp_path / 'V4361_20211006T162656Z_h265_1sec-test.mp4')
    download_video('http://localhost:8090/video/V4361_20211006T162656Z_h265_1sec.mp4',
                   temp_path)
