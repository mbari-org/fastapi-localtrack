# fastapi-accutrack, Apache-2.0 license
# Filename: daemon/docker_runner.py
# Description: Checks for new models and uploads them to S3

from aiohttp import ClientSession, ClientTimeout, ClientResponse


class HttpClient:

    async def request(self, method: str, url: str, timeout: int) -> ClientResponse:
        async with ClientSession(timeout=ClientTimeout(timeout)) as session:
            async with session.request(method, url) as response:
                return response