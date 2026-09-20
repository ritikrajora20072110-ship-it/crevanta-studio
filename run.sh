#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================="
echo "  🚀 Starting Crevanta Studio Automation System   "
echo "=================================================="

# Check Python version
python3 --version

# Install dependencies if needed
python3 -m pip install -q -r requirements.txt

# Start FastAPI server
echo "Opening Crevanta Studio on http://127.0.0.1:8000 ..."
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
