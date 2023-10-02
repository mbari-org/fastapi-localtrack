# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/monitor.py
# Description:  Miscellaneous utility functions for the daemon

import os
import time
from pathlib import Path
from typing import Dict, Any

from daemon.model_sync_client import ModelSyncClient
from daemon.docker_client import DockerClient
from daemon.logger import info


class Monitor:

    def __init__(self, check_every: int) -> None:
        self.check_every = check_every

    async def check(self) -> None:
        raise NotImplementedError()


class DockerMonitor(Monitor):
    def __init__(
            self,
            docker_client: DockerClient,
            database_path: Path,
            minio: Dict[str, Any],
            options: Dict[str, Any],
    ) -> None:
        self._client = docker_client
        if os.environ.get('DATABASE_DIR'):
            self._database_path = Path(os.environ.get('DATABASE_DIR'))
        else:
            self._database_path = Path(database_path)

        if os.environ.get('ROOT_BUCKET'):
            self._root_bucket = os.environ.get('ROOT_BUCKET')
        else:
            self._root_bucket = minio.get("root_bucket")

        if os.environ.get('TRACK_PREFIX'):
            self._track_prefix = os.environ.get('TRACK_PREFIX')
        else:
            self._track_prefix = minio.get("track_prefix")
        self._s3_strongsort_track_config = options.get("strongsort_track_config")
        DockerClient.startup(self._database_path)
        super().__init__(check_every=options.get("check_every"))

    async def check(self) -> None:
        time_start = time.time()

        await self._client.process(
            database_path=self._database_path,
            root_bucket=self._root_bucket,
            track_prefix=self._track_prefix,
            s3_track_config=self._s3_strongsort_track_config
        )

        time_end = time.time()
        time_took = time_end - time_start

        info( f"DockerClient took: {round(time_took, 3)} seconds")


class ModelSyncMonitor(Monitor):

    def __init__(
            self,
            model_sync_client: ModelSyncClient,
            options: Dict[str, Any],
            minio: Dict[str, Any],
    ) -> None:
        self._client = model_sync_client

        if os.environ.get('ROOT_BUCKET'):
            self._root_bucket = os.environ.get('ROOT_BUCKET')
        else:
            self._root_bucket = minio.get("root_bucket")

        if os.environ.get('MODEL_PREFIX'):
            self._model_prefix = os.environ.get('MODEL_PREFIX')
        else:
            self._model_prefix = minio.get("model_prefix")

        if os.environ.get('MODEL_DIR'):
            self._model_path = os.environ.get('MODEL_DIR')
        else:
            self._model_path = options.get("path")

        super().__init__(check_every=options.get("check_every"))

    async def check(self) -> None:
        time_start = time.time()

        ok, num_models = await self._client.run(
            root_bucket=self._root_bucket,
            model_prefix=self._model_prefix,
            model_path=self._model_path
        )

        time_end = time.time()
        time_took = time_end - time_start

        info(f'ModelSyncClient took: {round(time_took, 3)} seconds. Result: {ok}. Found {num_models} models')
