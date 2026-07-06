#!/bin/bash
set -e
echo "=== Build: installing dependencies ==="
pip install -r backend/requirements.txt
echo "=== Build: setting up uvicorn wrapper ==="
chmod +x bin/uvicorn
export PATH="/app/bin:$PATH"
echo "=== Build: verifying ==="
python -c "import fastapi, uvicorn, openai, faiss, sentence_transformers; print('All imports OK')"
which uvicorn
echo "=== Build complete ==="
