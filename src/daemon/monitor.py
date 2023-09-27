# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/monitor.py
# Description:  Miscellaneous utility functions for the daemon

import logging
import time
from pathlib import Path
from typing import Dict, Any

from daemon.http_client import HttpClient
from daemon.docker_client import DockerClient


class Monitor:

    def __init__(self, check_every: int) -> None:
        self.check_every = check_every
        self.logger = logging.getLogger(self.__class__.__name__)

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
        self._database_path = Path(database_path)
        self._root_bucket = minio.pop("root_bucket")
        self._track_prefix = minio.pop("track_prefix")
        self._s3_strongsort_track_config = minio.pop("strongsort_track_config")
        DockerClient.startup(self._database_path)
        super().__init__(check_every=options.pop("check_every"))

    async def check(self) -> None:
        time_start = time.time()

        response = await self._client.process(
            database_path=self._database_path,
            root_bucket=self._root_bucket,
            track_prefix=self._track_prefix,
            s3_track_config=self._s3_strongsort_track_config
        )

        time_end = time.time()
        time_took = time_end - time_start

        self.logger.info( f"Check  request took: {round(time_took, 3)} seconds")


class HttpMonitor(Monitor):

    def __init__(
            self,
            http_client: HttpClient,
            options: Dict[str, Any],
    ) -> None:
        self._client = http_client
        self._method = options.pop("method")
        self._url = options.pop("url")
        self._timeout = options.pop("timeout")
        super().__init__(check_every=options.pop("check_every"))

    async def check(self) -> None:
        time_start = time.time()

        response = await self._client.request(
            method=self._method,
            url=self._url,
            timeout=self._timeout,
        )

        time_end = time.time()
        time_took = time_end - time_start

        self.logger.info(
            "Check\n"
            "    %s %s\n"
            "    response code: %s\n"
            "    content length: %s\n"
            "    request took: %s seconds",
            self._method,
            self._url,
            response.status,
            response.content_length,
            round(time_took, 3)
        )
