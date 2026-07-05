#!/bin/bash
set -e
echo "=== Build: installing dependencies ==="
pip install -r backend/requirements.txt
echo "=== Build: verifying ==="
python -c "import fastapi, uvicorn, openai, faiss, sentence_transformers; print('All imports OK')"
echo "=== Build complete ==="
