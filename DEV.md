# Development notes
 
Install for local development with

```shell
conda env create
./bin/run_dev.sh
```
 
This will start an NGINX server, FastAPI server on port 8000, and
run the daemon for processing.  Adding the `build` argument will
rebuild the docker images, then start the servers.

Open the browser to http://localhost:8000/docs to see the API documentation.
 
## Testing

Run the pytest tests from the root directory with:

```shell
conda activate fastapi-localtrack
./bin/run_tests.sh
```

You should see output like:

```shell    
dev-minio-server is up-to-date
dev-nginx is up-to-date
Starting dev-setup-minio ... done
Wait for the nginx server to start
Fetch a few videos to serve in the default nginx/video directory
Nginx server running at http://localhost:8090
Minio server running at http://localhost:7000 username: localtrack password: ReplaceMePassword
FastAPI server running at http://localhost:8001
FastAPI docs running at http://localhost:8001/docs
================================================================================================================================================ test session starts ================================================================================================================================================
platform darwin -- Python 3.11.5, pytest-7.4.2, pluggy-1.3.0 -- /usr/local/Caskroom/miniconda/base/envs/fastapi-localtrack/bin/python
cachedir: .pytest_cache
rootdir: /Users/dcline/Dropbox/code/fastapi-accutrack
plugins: anyio-4.0.0
collecting ... [2023-10-05 19:00:25,157] [INFO] [LOCALTRACK]: Logging to /Users/dcline/Dropbox/code/fastapi-accutrack/tests/test_model.py_20231006.log
collected 1 item                                                                                                                                                                                                                                                                                                    

tests/test_model.py::test_model_discovery [2023-10-05 19:00:30,622] [INFO] [LOCALTRACK]: YAML_PATH environment variable not set. Using /Users/dcline/Dropbox/code/fastapi-accutrack/config.yml
[2023-10-05 19:00:30,650] [INFO] [LOCALTRACK]: Initializing the database
[2023-10-05 19:00:30,650] [INFO] [LOCALTRACK]: Initializing job cache database in /Users/dcline/fastapi_localtrack_dev/sqlite_data as /Users/dcline/fastapi_localtrack_dev/sqlite_data/sqlite_job_cache_docker.db
[2023-10-05 19:00:31,080] [INFO] [LOCALTRACK]: Video http://localhost:8090/video/V4361_20211006T162656Z_h265_10frame.mp4 is available.
[2023-10-05 19:00:31,080] [INFO] [LOCALTRACK]: Fetching models from s3://localtrack/models
[2023-10-05 19:00:31,202] [DEBUG] [LOCALTRACK]: Listing objects in s3://localtrack/models
[2023-10-05 19:00:31,809] [INFO] [LOCALTRACK]: Found 3 objects in s3://localtrack/models
[2023-10-05 19:00:31,809] [DEBUG] [LOCALTRACK]: Found models/MegadetectorTest.pt in s3://localtrack
[2023-10-05 19:00:31,809] [DEBUG] [LOCALTRACK]: Creating dictionary of model names to model paths
[2023-10-05 19:00:31,809] [DEBUG] [LOCALTRACK]: Found 1 models
[2023-10-05 19:00:31,810] [INFO] [LOCALTRACK]: Received Ctrl+C signal. Stopping the application..

...                                                                                                                                                                         .[ 50%]

```

## Clean up 

```shell
./bin/stop_docker.sh
```
