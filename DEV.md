# Development notes
 
Install for local development with

## Follow the README.md instructions for installing the conda environment

The tests require the test/runserver.sh script to be running in the background.

```shell
./test/run_nginx.sh
```

```shell
conda activate fastapi-microtrack
export PYTHONPATH=$PWD/src
cd src/app && uvicorn main:app --reload
```
 
This will start the server on port 8000. 

```shell  

## Testing

Run the pytest tests from the root directory with:

```shell
pytest
```

