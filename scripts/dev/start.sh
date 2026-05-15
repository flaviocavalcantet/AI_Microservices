#!/bin/bash
# Start All Services Script
# Starts all microservices using docker-compose

set -e

echo "Starting AI Platform services..."

# Load environment
if [ -f ".env" ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

# Build images
echo "Building Docker images..."
docker-compose build --pull

# Start services
echo "Starting services..."
docker-compose up -d

echo "Services started!"
echo ""
echo "Service URLs:"
echo "  API Service: http://localhost:5000"
echo "  Auth Service: http://localhost:5001"
echo "  AI Worker: http://localhost:5002"
echo "  Notification Service: http://localhost:5003"
echo "  MongoDB: mongodb://admin:admin123@localhost:27017"
echo "  RabbitMQ: amqp://localhost:5672"
echo "  RabbitMQ Management: http://localhost:15672"
echo "  Flower (Celery): http://localhost:5555"
echo ""
echo "View logs: docker-compose logs -f [service-name]"
