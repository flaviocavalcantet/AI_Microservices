#!/bin/bash
# Run All Tests Script
# Executes all tests with coverage reporting

set -e

echo "=========================================="
echo "Running Tests - AI Platform"
echo "=========================================="
echo ""

# Activate virtual environment if needed
if [ -d "venv" ]; then
    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest not installed"
    echo "Install with: pip install pytest pytest-cov"
    exit 1
fi

# Run tests with coverage
echo "Running all tests with coverage..."
pytest \
    --cov=services \
    --cov=shared \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=xml \
    -v \
    tests/ services/*/tests/ shared/*/tests/

echo ""
echo "=========================================="
echo "Coverage report generated in htmlcov/"
echo "Open htmlcov/index.html to view results"
echo "=========================================="
