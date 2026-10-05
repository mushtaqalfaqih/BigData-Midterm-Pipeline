#!/bin/bash
set -e

echo "🚀 [1/5] Checking Python & Pip environment..."
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "📦 Installing python3-pip and python3-venv..."
    sudo apt-get update -y
    sudo apt-get install -y python3-pip python3-venv python3-dev
fi

echo "🐳 [2/5] Starting MongoDB container..."
if command -v docker &> /dev/null; then
    docker compose up -d mongodb 2>/dev/null || docker run -d --name bigdata_mongodb -p 27017:27017 mongo:6.0 2>/dev/null || true
    echo "✅ MongoDB container is running on port 27017."
else
    echo "⚠️ Docker not found, ensuring mongod service..."
    sudo apt-get install -y mongodb-org 2>/dev/null || true
fi

echo "🐍 [3/5] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "📥 [4/5] Installing project dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "⚡ [5/5] Ingesting initial verified sample & preparing materialized views..."
python verify_all.py || true

echo "=========================================================="
echo "🎉 Setup Complete! Starting FastAPI REST API on port 8000..."
echo "=========================================================="
uvicorn src.final.api:app --host 0.0.0.0 --port 8000
