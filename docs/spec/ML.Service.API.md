
# API

--- 
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
  model: "mbari-315k"
  metadata: {
	  /* Can be any json */
	  /* It should be passed through to the response when the model run has completed */
  }
}
```

*TODO* - Should we just encode metadata as a base64 string instead of JSON and pass it through?

### 202

If the server finds the video exists and the model exists.

### 400

If the video can't be reached

### 404

If the model name isn't in the list of models
