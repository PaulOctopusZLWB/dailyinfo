#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="${SCRIPT_DIR:h:h}"

cd "$PROJECT_DIR"

export INFO_RADAR_ALLOWED_CLIENT_NETS="${INFO_RADAR_ALLOWED_CLIENT_NETS:-127.0.0.0/8,::1/128,10.0.0.0/8}"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  exec "$PROJECT_DIR/.venv/bin/python" -m info_radar.cli web \
    --host "${INFO_RADAR_HOST:-0.0.0.0}" \
    --port "${INFO_RADAR_PORT:-8787}" \
    --reports-dir "${INFO_RADAR_REPORTS_DIR:-$PROJECT_DIR/.info_radar/published}" \
    --static-dir "${INFO_RADAR_STATIC_DIR:-$PROJECT_DIR/web}"
fi

exec uv run info-radar web \
  --host "${INFO_RADAR_HOST:-0.0.0.0}" \
  --port "${INFO_RADAR_PORT:-8787}" \
  --reports-dir "${INFO_RADAR_REPORTS_DIR:-$PROJECT_DIR/.info_radar/published}" \
  --static-dir "${INFO_RADAR_STATIC_DIR:-$PROJECT_DIR/web}"
