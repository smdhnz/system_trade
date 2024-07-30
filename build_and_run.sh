#!/bin/bash

IMAGE_NAME="system-trade"

if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker and try again."
    exit 1
fi

if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo "Image '$IMAGE_NAME' does not exist. Building..."
    docker build -t $IMAGE_NAME .
else
    echo "Image '$IMAGE_NAME' already exists."
fi

docker run \
  --interactive \
  --tty \
  --detach \
  --init \
  --rm \
  --env-file .env \
  --name $IMAGE_NAME \
  $IMAGE_NAME
