#!/bin/bash
# Run Integration Tests Only
# Executes only integration tests (application layer)

set -e

if [ -d "venv" ]; then
    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate
fi

echo "Running integration tests..."
pytest \
    --cov=services \
    --cov=shared \
    -v \
    -k "integration" \
    tests/ services/*/tests/ shared/*/tests/
