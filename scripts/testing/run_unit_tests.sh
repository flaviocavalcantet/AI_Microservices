#!/bin/bash
# Run Unit Tests Only
# Executes only unit tests (domain layer)

set -e

if [ -d "venv" ]; then
    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate
fi

echo "Running unit tests..."
pytest \
    --cov=services \
    --cov=shared \
    -v \
    -k "unit" \
    tests/ services/*/tests/ shared/*/tests/
