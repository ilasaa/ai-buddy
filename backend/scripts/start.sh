#!/bin/sh
set -eu
alembic upgrade head
python -m scripts.seed_demo
python -m scripts.preload_embeddings
python -m scripts.index_knowledge
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
