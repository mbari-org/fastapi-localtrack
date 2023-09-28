[![MBARI](https://www.mbari.org/wp-content/uploads/2014/11/logo-mbari-3b.png)](http://www.mbari.org)
[![Python](https://img.shields.io/badge/language-Python-blue.svg)](https://www.python.org/downloads/)

**fastapi-localtrack** code is a lightweight API to process video. It uses the Python web framework [FastAPI](https://fastapi.tiangolo.com/).
 
# Requirements

For deployment, you will need:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

For development, you will need:
- [Python >=3.10](https://www.python.org/downloads/)
 
# TODO

- [ ] Update documentation to reflect additional endpoints and return of job_id in metadata
- [ ] Wire in daemon to github actions

# Deployment

## Clone the repository

```shell
git clone https://github.com/mbari-org/fastapi-localtrack
cd fastapi-localtrack
```

## Build and start the docker containers

```shell
./bin/docker_build.sh
./bin/docker_run.sh
```

Your server is now running at `http://localhost:3000/docs`
Data is stored in the minio server at `http://localhost:9000`

You can access the minio server at http://localhost:9000.  The default credentials are:
- Access Key: **localtrack**
- Secret Key: **ReplaceMePassword**

## Try it out

Open the browser to http://localhost:3000/docs to see the API documentation.

### Health Check
Check the health of the server by going to `http://localhost:3000/health`.  You should see the following response:
This checks if docker is running and if any models are available
```json
{"status":"ok"}
```

### See all jobs
Check the status of all jobs at `http://localhost:3000/health`

```json

```

### Model weights

YOLOv5 model weights in .pt files or contained in a tar.gz file as packaged in the 
[deepsea-ai train](http://docs.mbari.org/deepsea-ai/commands/train/) command are currently supported.
The assumption is that each are .pt or .tar.gz file is unique, creating a key that
is used for training the model.

### Minio

[minio](https://min.io/) is an open source S3 compatible object store.  It is used to store models, track configuration files 
and results from track processing.  It needs to be running to use the API and is started automatically when 
you run the docker container.

### Authentication

The credentials can be changed in the  .env file. See [.env](.env) for details.
 