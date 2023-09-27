# Development notes
 
Install for local development with

## Follow the README.md instructions for installing the conda environment

The tests require the example data to be downloaded and a working web server that
can service video with test video. This can be done with the following:

```shell
./bin/start.sh
./test/run_nginx.sh
```

```shell
conda activate fastapi-microtrack
export PYTHONPATH=$PWD/src
export AWS_DEFAULT_PROFILE=minio-localtrack
cd src/app && uvicorn main:app --reload
```
 
This will start the server on port 8000. Open the browser to http://localhost:8000/docs to see the API documentation.
 
## Testing

Run the pytest tests from the root directory with:

```shell
pytest
```

