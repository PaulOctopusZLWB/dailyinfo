#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
RUNTIME_DIR="${INFO_RADAR_RUNTIME_DIR:-$HOME/Library/Application Support/InfoRadar}"

if [[ "$SCRIPT_DIR" == "$RUNTIME_DIR" && -x "$RUNTIME_DIR/.venv/bin/python" ]]; then
  cd "$RUNTIME_DIR"
  export PYTHONPATH="$RUNTIME_DIR/app/src"
  export INFO_RADAR_ALLOWED_CLIENT_NETS="${INFO_RADAR_ALLOWED_CLIENT_NETS:-127.0.0.0/8,::1/128,10.0.0.0/8}"
  exec "$RUNTIME_DIR/.venv/bin/python" -m info_radar.cli web \
    --host "${INFO_RADAR_HOST:-0.0.0.0}" \
    --port "${INFO_RADAR_PORT:-8787}" \
    --reports-dir "${INFO_RADAR_REPORTS_DIR:-$RUNTIME_DIR/published}" \
    --static-dir "${INFO_RADAR_STATIC_DIR:-$RUNTIME_DIR/app/web}" \
    --credentials-path "${INFO_RADAR_CREDENTIALS_PATH:-$RUNTIME_DIR/.env}"
fi

PROJECT_DIR="${SCRIPT_DIR:h:h}"

cd "$PROJECT_DIR"

export INFO_RADAR_ALLOWED_CLIENT_NETS="${INFO_RADAR_ALLOWED_CLIENT_NETS:-127.0.0.0/8,::1/128,10.0.0.0/8}"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  exec "$PROJECT_DIR/.venv/bin/python" -m info_radar.cli web \
    --host "${INFO_RADAR_HOST:-0.0.0.0}" \
    --port "${INFO_RADAR_PORT:-8787}" \
    --reports-dir "${INFO_RADAR_REPORTS_DIR:-$PROJECT_DIR/.info_radar/published}" \
    --static-dir "${INFO_RADAR_STATIC_DIR:-$PROJECT_DIR/web}" \
    --credentials-path "${INFO_RADAR_CREDENTIALS_PATH:-$PROJECT_DIR/.env}"
fi

exec uv run info-radar web \
  --host "${INFO_RADAR_HOST:-0.0.0.0}" \
  --port "${INFO_RADAR_PORT:-8787}" \
  --reports-dir "${INFO_RADAR_REPORTS_DIR:-$PROJECT_DIR/.info_radar/published}" \
  --static-dir "${INFO_RADAR_STATIC_DIR:-$PROJECT_DIR/web}" \
  --credentials-path "${INFO_RADAR_CREDENTIALS_PATH:-$PROJECT_DIR/.env}"
