
# API Specification

--- 
## GET /health

This checks if any models are available and the health of the database

### 200

```json
{"status":"ok"}
```

### 503 

If not healthy

## GET /models

Retrieve a list of available models that can be used.

### 200

```
[
 "mbari-315k",
 "midwater-20230701",
 "etc"
]
```

---
## POST /predict

Upload json body.

```json
{
  video: "http://some.hostname.com/path/to/video.mp4"
  model: "mbari-315k",
  /* Optional arguments to pass to the model */
  args: " --conf-thres=0.01 --iou-thres=0.4 --max-det=100 ", 
  metadata: {
    /* Can be any json */
    /* It should be passed through to the response when the model run has completed */
  }
}
```

### 202

If the server finds the video exists and the model exists.

### 400

If the video can't be reached

### 404

If the model name isn't in the list of models

---
## POST /status_by_id

Retrieve status for a give job by its id.

### 200 

```json
{
  "status": "SUCCESS",
  "last_updated": "2023-10-02 20:41:15.546944",
  "created_at": "2023-10-02 20:40:43",
  "name": "MegadetectorTest.pt V4361_20211006T162656Z_h265_10frame ernie running",
  "job_id": 19,
  "video": "http://localhost:8090/video/V4361_20211006T162656Z_h265_10frame.mp4",
  "args": "--conf-thres=0.01 --iou-thres=0.4 --max-det=100 --agnostic-nms --imgsz 640",
  "model": "s3://localtrack/models/MegadetectorTest.pt",
  "metadata": {},
  "processing_time_secs": 17.380639,
  "num_tracks": 2,
  "s3_path": "s3://localtrack/tracks/20231002T204058Z/output/output/V4361_20211006T162656Z_h265_10frame.tracks.tar.gz"
}
```

### 404

Job not found