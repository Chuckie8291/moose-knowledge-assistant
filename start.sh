#!/bin/bash
set -e
echo "=== Starting Moose Knowledge Assistant ==="
cd /app
exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
