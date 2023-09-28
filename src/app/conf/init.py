# fastapi-localtrack, Apache-2.0 license
# Filename: app/conf/init.py
# Description:  Configuration for the application.
# This needs to be imported first in order to set up the logger and other configuration.

import os
from pathlib import Path
import tempfile
import yaml

from app.logger import info

yaml_path = Path(__file__).parent.parent.parent.parent / 'config.yml'
info(f"YAML_PATH environment variable not set. Using {yaml_path}")
if not yaml_path.exists():
    raise FileNotFoundError(f"Could not find {yaml_path}")

temp_path = Path(tempfile.gettempdir()) / 'fastapi-localtrack'

# Read the yaml configuration file and set configuration variables
with yaml_path.open('r') as yaml_file:
    data = yaml.safe_load(yaml_file)
    root_bucket = data['minio']['root_bucket']
    model_prefix = data['minio']['model_prefix']
    video_prefix = data['minio']['video_prefix']
    default_args = data['defaults']['args']
    default_video_url = data['defaults']['video_url']

    # if running this on an arm64 machine, use the arm64 docker image
    if os.uname().machine == 'arm64':
        engine = data['monitors']['docker']['strongsort_container_arm64']
    else:
        engine = data['monitors']['docker']['strongsort_container']

    database_path = Path(data['database']['path'])
    if os.environ.get('DATABASE_DIR'):
        database_path = Path(os.environ['DATABASE_DIR'])

# A list of fun short names from sherman lagoon
lagoon_names = [
    'sherman',
    'fillmore',
    'ernie',
    'megan',
    'herman',
    'thor',
    'shelly',
    'hawthorne',
    'stillwater',
    'fiona',
    'trixie',
    'olivia',
    'captain_quigley',
]

# A list of fun short names to append to the sherman names that represent states of being
lagoon_states = [
    'sleeping',
    'sitting',
    'standing',
    'walking',
    'running',
    'jumping',
    'flying',
    'swimming',
    'diving',
    'surfing',
    'fishing',
    'eating',
    'drinking',
    'singing',
    'dancing',
    'laughing',
]

