#!/bin/bash
cd .. && docker buildx bake -f docker-bake.hcl && cd dev_environment && docker compose down && docker compose up -d