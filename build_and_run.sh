#!/bin/bash

IMAGE_NAME="system-trade"

if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker and try again."
    exit 1
fi

docker rmi $IMAGE_NAME

docker build -t $IMAGE_NAME .

# docker run --rm \
docker run \
  --interactive \
  --tty \
  --detach \
  --init \
  --env-file .env \
  --name $IMAGE_NAME \
  $IMAGE_NAME
