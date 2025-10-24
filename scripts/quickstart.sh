#!/bin/bash

# Quick Start Script for BSC Token Data Collection System

set -e

echo "================================"
echo "BSC Token Data Collection System"
echo "Quick Start Script"
echo "================================"
echo ""

# Check if Python 3.9+ is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Found Python $PYTHON_VERSION"
echo ""

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "Dependencies installed"
echo ""

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo ".env file created (please edit it with your configuration)"
fi

# Initialize database
echo "Initializing database..."
python -m src.main init-db
echo ""

# Check health
echo "Checking data source health..."
python -m src.main health
echo ""

echo "================================"
echo "Setup completed successfully!"
echo "================================"
echo ""
echo "You can now run:"
echo "  python -m src.main collect  # Collect token data"
echo "  python -m src.main query    # Query tokens"
echo "  python -m src.main analyze  # Analyze market"
echo ""
echo "For more commands, run: python -m src.main --help"
echo ""
