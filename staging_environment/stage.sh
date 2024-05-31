#!/bin/bash
sudo rm data/postgres -r

docker compose rm --all --stop --force

source .env
echo $CR_PAT | docker login ghcr.io -u fossinating --password-stdin

docker image pull ghcr.io/fossinating/tarheel-compass-data:staging
docker image pull ghcr.io/fossinating/tarheel-compass-server:staging

docker compose up -d

# TODO: Stage with a copy of the live database