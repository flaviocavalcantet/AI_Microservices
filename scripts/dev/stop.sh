#!/bin/bash
# Stop All Services Script
# Stops all microservices

set -e

echo "Stopping AI Platform services..."
docker-compose down

echo "Services stopped!"
