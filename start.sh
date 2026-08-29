#!/bin/bash
# JobCopilot - One-Click Launch Script

set -e

echo "=================================================================="
echo "🚀 Starting JobCopilot Local-First Autonomous Career Engine..."
echo "=================================================================="

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Ensure Virtual Environment exists
if [ ! -d "backend/venv" ]; then
    echo "📦 Initializing Python virtual environment..."
    python3 -m venv backend/venv
    backend/venv/bin/pip install --upgrade pip
    backend/venv/bin/pip install -r backend/requirements.txt
fi

echo "✨ Launching JobCopilot Engine at http://localhost:8000"
backend/venv/bin/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
