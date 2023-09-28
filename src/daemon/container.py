# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/container.py
# Description: Container for dependency injection

import os
from pathlib import Path
from dependency_injector import containers, providers

from daemon import model_sync_client, docker_client, monitor, dispatcher


class Container(containers.DeclarativeContainer):

    yaml_path = Path(os.path.dirname(__file__)).parent.parent / 'config.yml'
    if not yaml_path.exists():
        raise FileNotFoundError(f"Could not find {yaml_path}")

    config = providers.Configuration(yaml_files=[yaml_path.as_posix()])

    model_sync_client = providers.Factory(model_sync_client.ModelSyncClient)
    docker_client = providers.Factory(docker_client.DockerClient)

    sync_monitor = providers.Factory(
        monitor.ModelSyncMonitor,
        model_sync_client=model_sync_client,
        minio=config.minio,
        options=config.monitors.models,
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
            sync_monitor,
        ),
    )
