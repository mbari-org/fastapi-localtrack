# Development notes
 
Install for local development with


**Follow the README.md instructions for installing the conda environment**

The tests require the example data to be downloaded and a working web server that
can service video with test video. This can be done with the following:

```shell
./bin/start.sh
./test/run_nginx.sh
```

Once that is done, you can run the api app and the daemon with:
```shell
conda activate fastapi-microtrack
export PYTHONPATH=$PWD/src:$PWD/tests
export AWS_DEFAULT_PROFILE=minio-localtrack
cd src/app
python -m daemon &
uvicorn main:app --reload
```
 
This will start the FastAPI server on port 8000, and
run the daemon for processing. 

Open the browser to http://localhost:8000/docs to see the API documentation.
 
## Testing

Run the pytest tests from the root directory with:

```shell
pytest
```

You should see output like:

```shell

=========================================================================================== test session starts ===========================================================================================
platform darwin -- Python 3.11.5, pytest-7.4.2, pluggy-1.3.0
rootdir: /Users/dcline/Dropbox/code/fastapi-accutrack
plugins: anyio-4.0.0
collected 18 items                                                                                                                                                                                        

tests/test_database.py ........                                                                                                                                                                     [ 44%]
tests/test_health.py .                                                                                                                                                                              [ 50%]

```

