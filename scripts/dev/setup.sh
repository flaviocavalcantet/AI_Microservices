#!/bin/bash
# Development Setup Script
# Initializes the project for local development

set -e

echo "=========================================="
echo "AI Platform - Development Setup"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
python_version=$(python --version | awk '{print $2}')
echo "Python version: $python_version"

if ! python -m venv --help > /dev/null 2>&1; then
    echo "Error: Python venv module not available"
    exit 1
fi

# Create virtual environment
echo -e "${BLUE}Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python -m venv venv
    echo -e "${GREEN}Virtual environment created${NC}"
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel

# Install root dependencies
echo -e "${BLUE}Installing root dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Install service dependencies
echo -e "${BLUE}Installing service dependencies...${NC}"
for service_dir in services/*/; do
    if [ -f "$service_dir/requirements.txt" ]; then
        echo "Installing dependencies for $(basename $service_dir)..."
        pip install -r "$service_dir/requirements.txt"
    fi
done

# Install shared module dependencies
echo -e "${BLUE}Installing shared module dependencies...${NC}"
for shared_dir in shared/*/; do
    if [ -f "$shared_dir/requirements.txt" ]; then
        echo "Installing dependencies for $(basename $shared_dir)..."
        pip install -r "$shared_dir/requirements.txt"
    fi
done

# Setup environment files
echo -e "${BLUE}Setting up environment files...${NC}"
if [ ! -f ".env" ]; then
    cp config/environments/.env.development .env
    echo -e "${GREEN}.env file created from .env.development${NC}"
else
    echo ".env file already exists"
fi

# Create .env file in each service if needed
for service_dir in services/*/; do
    service_name=$(basename $service_dir)
    if [ ! -f "$service_dir/.env" ]; then
        cp config/environments/.env.development "$service_dir/.env"
        echo "Created .env for $service_name"
    fi
done

# Install pre-commit hooks (optional)
if command -v pre-commit &> /dev/null; then
    echo -e "${BLUE}Installing pre-commit hooks...${NC}"
    pre-commit install
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Update .env files with your configuration"
echo "3. Start services: docker-compose up -d"
echo "4. Run tests: pytest"
echo ""
