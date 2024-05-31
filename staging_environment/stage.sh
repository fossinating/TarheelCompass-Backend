#!/bin/bash
sudo rm data/postgres -r

docker compose rm --all --stop --force

source .env

if ! echo $CR_PAT | docker login ghcr.io -u fossinating --password-stdin; then
echo "Failed to log in, stopping"
exit 1
fi

if ! docker image pull ghcr.io/fossinating/tarheel-compass-data:latest && docker image pull ghcr.io/fossinating/tarheel-compass-server:latest; then
echo "Failed to pull images"
exit 1
fi

if ! docker compose up -d; then
echo "Failed to start"
exit 1
fi

# TODO: Stage with a copy of the live database