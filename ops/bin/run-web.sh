#!/bin/zsh
set -euo pipefail

cd /Users/paul/Documents/info_radar

exec /Users/paul/Documents/info_radar/.venv/bin/python -m info_radar.cli web \
  --host 127.0.0.1 \
  --port 8787 \
  --reports-dir /Users/paul/Documents/info_radar/.info_radar/published \
  --static-dir /Users/paul/Documents/info_radar/web
