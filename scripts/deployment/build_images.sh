#!/bin/bash
# Build Docker Images Script
# Builds all service Docker images

set -e

echo "Building Docker images for all services..."

docker-compose build --pull

echo "Docker images built successfully!"
docker images | grep ai_platform || echo "No images found"
