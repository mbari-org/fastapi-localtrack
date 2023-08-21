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
from app import logger
from app.job.cache import JobCache
from app.logger import info, debug
from app.utils.misc import list_by_suffix

if 'TMP_PATH' in os.environ:
    temp_path = Path(os.environ['TMP_PATH'])
else:
    temp_path = Path(__file__).parent.resolve().parent / 'tmp'
    
temp_path.mkdir(parents=True, exist_ok=True)
info(f'Logging to {temp_path / "logs"}')

logger = logger.create_logger_file(temp_path / 'logs')

# Bucket for storing models, tracks, etc
s3_root_bucket = 'm3-video-processing'
s3_model_prefix = 'models'
s3_track_config_prefix = 'track_config'
s3_track_prefix = 'tracks'

info(f'Creating job cache in {temp_path / "job_cache"}')
job_cache = JobCache(temp_path / 'job_cache')

info(f'Fetching models from s3://{s3_root_bucket}/{s3_model_prefix}')
model_s3 = list_by_suffix(s3_root_bucket, s3_model_prefix, ['.gz', '.pt'])

debug(f'Creating dictionary of model names to model paths')
model_paths = {model.split('.')[0]: model for model in model_s3}

local_config_ini_path = Path(__file__).parent / 'local_config.ini'

minio_endpoint_url = 'http://localhost:9000'