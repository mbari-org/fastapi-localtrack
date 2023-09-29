
# API Specification

## POST /notify

Include a mulit-part body. There should be 2 multipart sections:

1. `file` - contains the `tar.gz` of the json files
2. `metadata` - contains the metadata that was passed into the request to the /predict endpoint and the job_id

### 200

OK