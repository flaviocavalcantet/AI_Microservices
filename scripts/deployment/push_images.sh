#!/bin/bash
# Push Docker Images Script
# Pushes Docker images to container registry

set -e

# Configuration
REGISTRY="${REGISTRY:-docker.io}"
NAMESPACE="${NAMESPACE:-aiplatform}"
VERSION="${VERSION:-latest}"

echo "Pushing Docker images to $REGISTRY/$NAMESPACE..."

SERVICES=("api_service" "auth_service" "ai_worker" "notification_service")

for service in "${SERVICES[@]}"; do
    image_name="$REGISTRY/$NAMESPACE/$service:$VERSION"
    echo "Pushing $image_name..."
    docker tag "ai_platform_${service}:latest" "$image_name"
    docker push "$image_name"
done

echo "Images pushed successfully!"
