#!/bin/zsh
set -euo pipefail

cd /Users/paul/Documents/info_radar

export INFO_RADAR_ALLOWED_CLIENT_NETS="${INFO_RADAR_ALLOWED_CLIENT_NETS:-127.0.0.0/8,::1/128,10.0.0.0/8}"

exec /Users/paul/Documents/info_radar/.venv/bin/python -m info_radar.cli web \
  --host 0.0.0.0 \
  --port 8787 \
  --reports-dir /Users/paul/Documents/info_radar/.info_radar/published \
  --static-dir /Users/paul/Documents/info_radar/web
