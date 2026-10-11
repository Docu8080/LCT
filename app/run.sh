#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv-runtime/bin/python ]; then
  python3 -m venv .venv-runtime
  .venv-runtime/bin/python -m pip install -r requirements.lock.txt
fi
exec .venv-runtime/bin/python -X pycache_prefix=data/python-cache -m uvicorn server:app --host 127.0.0.1 --port "${PORT:-8080}"
