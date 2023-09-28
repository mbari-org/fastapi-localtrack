# Development notes
 
Install for local development with

```shell
./bin/run_dev.sh
```
 
This will start an NGINX server, FastAPI server on port 8000, and
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

