#!/usr/bin/env bash
# Sets up the default buckets and uploads example data
# Requires awscli and minio client
# Assumes minio is running on localhost:9000 and the minio-microtrack profile is configured as minio-microtrack per the README instructions
ROOT_BUCKET=m3-video-processing

echo "Creating a bucket called s3//${ROOT_BUCKET}"
aws s3 mb --profile minio-microtrack --endpoint-url http://127.0.0.1:9000 s3://${ROOT_BUCKET}

echo "List buckets"
aws s3 ls --profile minio-microtrack --endpoint-url http://127.0.0.1:9000

echo "Download example data and save to the m3-video-processing bucket"
# Do the work in a temporary directory
mkdir -p tmp/models tmp/track_config
cd tmp
aws s3 cp --no-sign-request s3://902005-public/models/Megadetector/best.pt models/Megadetector.pt
aws s3 cp --no-sign-request s3://902005-public/models/yolov5x_mbay_benthic_model.tar.gz models/yolov5x_mbay_benthic_model.tar.gz
aws s3 cp --no-sign-request s3://902005-public/models/Megadetector/best.pt models/Megadetector.pt
aws s3 cp --no-sign-request s3://902005-public/models/strong_sort_benthic.yaml track_config/strong_sort_benthic.yaml
aws s3 sync . --profile  minio-microtrack --endpoint-url http://127.0.0.1:9000 s3://${ROOT_BUCKET}

# Clean up
cd ..
rm -rf tmp