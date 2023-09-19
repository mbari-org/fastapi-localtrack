#!/usr/bin/env bash
# Start the minio server and download example data
# Requires awscli and minio client
# Assumes awscli profile is configured as minio-accutrack per the README instructions
# Run with ./start.sh

# Get the directory of this script
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && cd .. && pwd )"

# Setup environment variables
ROOT_BUCKET=m3-video-processing
PROFILE=minio-accutrack
ENDPOINT_URL=http://127.0.0.1:9000

# Enable plugin endpoint, add endpoint url and set max bandwidth to 62MB/s
aws configure set plugins.endpoint awscli_plugin_endpoint
aws configure set --profile minio-accutrack endpoint_url ${ENDPOINT_URL}
aws configure --profile ${PROFILE} set s3.max_bandwidth 62MB/s

# Setup minio and wait 3 seconds for it to start
docker stop minio-server
docker rm --force minio-server
docker-compose up -d
sleep 3

# Create buckets
buckets=("tracks"  "track-config" "models")
for bucket in "${buckets[@]}"; do
    echo "Creating bucket ${bucket}"
    aws s3 mb --profile ${PROFILE} s3://${ROOT_BUCKET}/${bucket}
done

echo "List buckets in ${ROOT_BUCKET}"
aws s3 ls --profile ${PROFILE} s3://${ROOT_BUCKET}

echo "Download example data and save to the m3-video-processing bucket"
# Do the work in a temporary directory then sync to the bucket
temp=$(date +%s)
mkdir -p ${temp}/models/track-config
aws s3 cp --no-sign-request s3://902005-public/models/Megadetector/best.pt ${temp}/models/Megadetector.pt
aws s3 cp --no-sign-request s3://902005-public/models/track-config/strong_sort_benthic.yaml ${temp}/track-config/strong_sort_benthic.yaml
aws s3 cp --no-sign-request s3://902005-public/models/yolov5x_mbay_benthic_model.tar.gz ${temp}/models/yolov5x_mbay_benthic_model.tar.gz
aws s3 sync ${temp} --profile ${PROFILE} s3://${ROOT_BUCKET}

# Clean up
rm -rf ${temp}