# fastapi-accutrack, Apache-2.0 license
# Filename: daemon/container.py
# Description: Container for dependency injection

import logging
import os
import sys
from pathlib import Path
from daemon.misc import verify_upload

import yaml
from dependency_injector import containers, providers

from . import http_client, docker_client, monitor, dispatcher


class Container(containers.DeclarativeContainer):

    # Get a path to the yaml file, or use the default
    yaml_path = os.getenv('YAML_PATH')
    if not yaml_path:
        yaml_path = Path(os.path.dirname(__file__)).parent.parent / 'config.yml'
        print(f"YAML_PATH environment variable not set. Using {yaml_path}")
        if not yaml_path.exists():
            raise FileNotFoundError(f"Could not find {yaml_path}")

    # Verify ability to upload to minio before starting the daemon
    with yaml_path.open('r') as yaml_file:
        data = yaml.safe_load(yaml_file)
        if not verify_upload(prefix=data['minio']['track_prefix'], bucket=data['minio']['root_bucket']):
            raise Exception("Could not upload to minio. Please check your credentials.")
    config = providers.Configuration(yaml_files=[yaml_path.as_posix()])

    logging = providers.Resource(
        logging.basicConfig,
        stream=sys.stdout,
        level=config.log.level,
        format=config.log.format,
    )

    http_client = providers.Factory(http_client.HttpClient)
    docker_client = providers.Factory(docker_client.DockerClient)

    example_monitor = providers.Factory(
        monitor.HttpMonitor,
        http_client=http_client,
        options=config.monitors.example,
    )

    docker_monitor = providers.Factory(
        monitor.DockerMonitor,
        database_path=config.database.path,
        docker_client=docker_client,
        minio=config.minio,
        options=config.monitors.docker,
    )

    dispatcher = providers.Factory(
        dispatcher.Dispatcher,
        monitors=providers.List(
            docker_monitor,
            example_monitor,
        ),
    )
