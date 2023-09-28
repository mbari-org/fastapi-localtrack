# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/model_sync_client.py
# Description: Checks for new models and uploads them to S3

from pathlib import Path

from app.logger import err
from daemon.misc import upload_files_to_s3


class ModelSyncClient:

    async def run(self, root_bucket: str, model_prefix: str, model_path: Path) -> (bool, int):
        try:
            num_uploaded = await upload_files_to_s3(root_bucket, model_path, model_prefix, ['.pt', '.gz'])
            return True, num_uploaded
        except Exception as e:
            err(f'Error uploading models: {e}')
            return False, 0
