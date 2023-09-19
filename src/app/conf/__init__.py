# !/usr/bin/env python
__author__ = "Danelle Cline"
__copyright__ = "Copyright 2023, MBARI"
__credits__ = ["MBARI"]
__license__ = "GPL"
__maintainer__ = "Danelle Cline"
__email__ = "dcline at mbari.org"
__doc__ = '''

Configuration for the application.
This needs to be imported first in order to set up the logger, the cache
and other configuration.

@author: __author__
@status: __status__
@license: __license__
'''
import os
from pathlib import Path

from deepsea_ai.config.config import Config
from app import logger
from app.logger import info

if 'TMP_PATH' in os.environ:
    temp_path = Path(os.environ['TMP_PATH'])
else:
    temp_path = Path(__file__).parent.resolve().parent / 'tmp'
    
temp_path.mkdir(parents=True, exist_ok=True)
info(f'Logging to {temp_path / "logs"}')

# Create a logger to log to a subdirectory of the temp path
logger = logger.create_logger_file(temp_path / 'logs')
local_config_ini_path = Path(__file__).parent / 'local_config.ini'

cfg = Config(local_config_ini_path.as_posix())
s3_root_bucket = cfg('minio', 's3_root_bucket')
s3_model_prefix = cfg('minio', 's3_model_prefix')
