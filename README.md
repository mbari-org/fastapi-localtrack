[![MBARI](https://www.mbari.org/wp-content/uploads/2014/11/logo-mbari-3b.png)](http://www.mbari.org)
[![semantic-release](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg)](https://github.com/semantic-release/semantic-release)
![license-GPL](https://img.shields.io/badge/license-GPL-blue)
[![Python](https://img.shields.io/badge/language-Python-blue.svg)](https://www.python.org/downloads/)

**fastapi-accutrack** code is a lightweight API to process video. It uses the Python web framework [FastAPI](https://fastapi.tiangolo.com/).
 
# Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) for downloading test data

# Deploy locally

## Clone the repository
```shell
git clone http://github.com/mbari-org/fastapi-accutrack
cd fastapi-accutrack
```

## Configure minio

[minio](https://min.io/) is an open source S3 compatible object store.  It is used to store models, track configuration files and results from track processing.  The docker-compose file will start a minio server on port 9000.  

The default credentials are:
- AWS Access Key ID [None]: **accutrack** 
- AWS Secret Access Key [None]: **ReplaceMePassword**.

These can be changed in the docker-compose file, or by setting up a .env file with the keys
MINIO_ACCESS_KEY=<your new kay>
MINIO_ROOT_PASSWORD=<your new password>

It is OK to leave the other fields blank, e.g. minio does not require a region.  
```shell
pip install awscli
aws configure --profile minio-accutrack
```

## Start the FastAPI accutrack services
  
```shell
docker-compose up -d
``` 

To stop the server, run
```shell
docker-compose down
```

Your server is now running at `http://localhost:3000/docs`

# Setup buckets and upload test data
```shell
./bin/setup.sh
```
 
# Running

## Health Check
Check the health of the server by going to `http://localhost:3000/health`.  You should see the following response:

```json
{"status":"ok"}
```

## TODO: add examples