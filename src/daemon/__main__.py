# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/__main__.py
# Description: Dispatcher to run jobs and monitor for new models

from dependency_injector.wiring import Provide, inject

from aiodocker import Docker, DockerError
from daemon.dispatcher import Dispatcher
from daemon.container import Container
from daemon.logger import create_logger_file, info, err
import asyncio
import yaml
import os
from pathlib import Path
from daemon.misc import verify_upload

# Setup logging
log_path = Path(os.path.dirname(__file__)).parent.parent / 'logs'
create_logger_file(log_path, 'daemon')


@inject
def main(dispatcher: Dispatcher = Provide[Container.dispatcher]) -> None:
    dispatcher.run()


async def minio_check(data: dict) -> bool:
    # Override the minio config if the environment variables are set
    if os.getenv('ROOT_BUCKET') and os.getenv('TRACK_PREFIX'):
        data['minio']['root_bucket'] = os.getenv('ROOT_BUCKET')
        data['minio']['track_prefix'] = os.getenv('TRACK_PREFIX')

    # Verify that we can upload to minio
    try:
        return await verify_upload(prefix=data['minio']['track_prefix'],
                                   bucket=data['minio']['root_bucket'])
    except Exception:
        return False

    return False


def env_check() -> bool:
    """
    Check that the environment variables are set
    :return:
    """
    if not os.getenv('MINIO_ENDPOINT_URL') or not os.getenv('MINIO_ACCESS_KEY') or not os.getenv('MINIO_SECRET_KEY'):
        info(f"MINIO_ENDPOINT_URL, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY environment variables must be set")
        return False
    return True


async def docker_check(data: dict) -> bool:
    # if running this on an arm64 machine, use the arm64 docker image
    if os.uname().machine == 'arm64':
        image_name = data['monitors']['docker']['strongsort_container_arm64']
    else:
        image_name = data['monitors']['docker']['strongsort_container']
    async with Docker() as docker_aoi:
        try:
            return await docker_aoi.images.inspect(image_name)
        except DockerError as e:
            if e.status == 404:
                await docker_aoi.pull(image_name)
            else:
                raise DockerError(e.status, f'Error retrieving {image_name} image.')

        return False


async def run():
    yaml_path = Path(os.path.dirname(__file__)).parent.parent / 'config.yml'
    if not yaml_path.exists():
        raise FileNotFoundError(f"Could not find {yaml_path}")

    # Parse the config file
    with yaml_path.open('r') as yaml_file:
        data = yaml.safe_load(yaml_file)
        if not data:
            info(f"Could not parse {yaml_path}")
            return False

        check_minio = await minio_check(data)
        check_docker = await docker_check(data)

        # Exit if we can't upload to minio or pull docker images
        if not check_minio:
            err(f"Could not upload to minio")
            return False
        if not check_docker:
            err(f"Could not pull docker image")
            return False

        # Initialize the container
        container = Container()
        container.init_resources()
        container.wire(modules=[__name__])
        return True


if __name__ == "__main__":
    if env_check() and asyncio.run(run()):
        main()
