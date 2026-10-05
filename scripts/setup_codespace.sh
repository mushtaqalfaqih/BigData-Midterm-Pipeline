#!/bin/bash
set -e

echo "🔍 Detecting environment and package manager..."
if [ -f /etc/os-release ]; then
    cat /etc/os-release | grep -E "^(NAME|ID|VERSION)=" || true
fi

echo "🚀 [1/5] Checking Python & Pip..."
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "📦 Package manager auto-install..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -y && sudo apt-get install -y python3-pip python3-venv python3-dev
    elif command -v apk &> /dev/null; then
        sudo apk add --no-cache python3 py3-pip docker docker-cli-compose
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3-pip python3-devel
    elif command -v microdnf &> /dev/null; then
        sudo microdnf install -y python3-pip
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3-pip
    fi
fi

# Detect python binary
PYTHON_BIN="python3"
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_BIN="python"
    fi
fi

echo "🐳 [2/5] Checking MongoDB container..."
if command -v docker &> /dev/null; then
    docker compose up -d mongodb 2>/dev/null || docker run -d --name bigdata_mongodb -p 27017:27017 mongo:6.0 2>/dev/null || true
    echo "✅ MongoDB container is running on port 27017."
else
    echo "⚠️ Docker command not active in this subshell."
fi

echo "🐍 [3/5] Setting up Python virtual environment..."
$PYTHON_BIN -m venv .venv 2>/dev/null || true
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "📥 [4/5] Installing project dependencies..."
pip install --upgrade pip 2>/dev/null || true
pip install -r requirements.txt || pip3 install -r requirements.txt || true

echo "⚡ [5/5] Ingesting initial verified sample & preparing materialized views..."
python verify_all.py 2>/dev/null || true

echo "=========================================================="
echo "🎉 Starting FastAPI REST API on port 8000..."
echo "=========================================================="
uvicorn src.final.api:app --host 0.0.0.0 --port 8000
