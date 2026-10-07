#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python -m pip install -r requirements.txt
python update_server.py --host 127.0.0.1 --port 8000
