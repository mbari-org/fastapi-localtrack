
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
