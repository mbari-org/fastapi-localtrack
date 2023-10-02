[![MBARI](https://www.mbari.org/wp-content/uploads/2014/11/logo-mbari-3b.png)](http://www.mbari.org)
[![Python](https://img.shields.io/badge/language-Python-blue.svg)](https://www.python.org/downloads/)

**fastapi-localtrack** code is a lightweight API to process video. It uses the Python web framework [FastAPI](https://fastapi.tiangolo.com/).
 
-  New videos queued to process are handled by a daemon that scans for new videos every 15 seconds
-  New models are scanned for every minute and uploaded to minio where they are available for processing
-  Currently only YOLOv5 models are supported

# Requirements

For deployment, you will need:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

For development, you will need:
- [Python >=3.10](https://www.python.org/downloads/)
- [Anaconda](https://www.anaconda.com/)
 
# TODO
 
- [ ] Wire in daemon and pytest to github actions
- [ ] Standardize .names convention for local and cloud to be the same


# Deployment

## Clone the repository

```shell
git clone https://github.com/mbari-org/fastapi-localtrack
cd fastapi-localtrack
```

## Build and start the docker containers

```shell
./bin/docker_build.sh
./bin/run_prod.sh
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

```json
{"status":"ok"}
```

### See all jobs
Check the status of all jobs at `http://localhost:3000/status`

```json
{
  "jobs": [
    {
      "id": 1,
      "name": "yolov5s.pt V4361_20211006T162656Z_h265_10frame hawthorne standing",
      "status": "QUEUED"
    }
  ]
}
```

### Process a video

```shell
curl -X 'POST' \
  'http://localhost:8001/predict' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "model": "MegadetectorTest.pt",
  "video": "http://localhost:8090/video/V4361_20211006T162656Z_h265_10frame.mp4",
  "metadata": {},
  "args": "--conf-thres=0.01 --iou-thres=0.4 --max-det=100 --agnostic-nms --imgsz 640"
}'
```

This should return a job id which can be used to retrieve the results or inspect the status
```json
{
  "message": "http://localhost:8090/video/V4361_20211006T162656Z_h265_10frame.mp4 queued for processing",
  "job_id": 22,
  "job_name": "MegadetectorTest.pt V4361_20211006T162656Z_h265_10frame hawthorne jumping"
}
```


### Model weights

YOLOv5 model weights in .pt files or contained in a tar.gz file as packaged in the 
[deepsea-ai train](http://docs.mbari.org/deepsea-ai/commands/train/) command are currently supported.
The assumption is that each .pt or .tar.gz file is unique as 
it is used to create a key that is used for training the model.

### Minio

[minio](https://min.io/) is an open source S3 compatible object store.  It is used to store models, track configuration files 
and track results from processing video.  It needs to be running to use the API and is started automatically when 
you run the [./bin/run_prod.sh](./bin/docker_run.sh).

### Authentication

The credentials can be changed in the .env file. See [.env](.env) for details.
 
### Notification

To setup the receiving notification service add the NOTIFY_URL to the [.env](.env) file. 
The results will be available in the minio server if the notification service goes down.