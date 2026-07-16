#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="${SCRIPT_DIR:h:h}"
RUNTIME_DIR="${INFO_RADAR_RUNTIME_DIR:-$HOME/Library/Application Support/InfoRadar}"
LAUNCH_AGENT="$HOME/Library/LaunchAgents/com.paul.info-radar-web.plist"
SERVICE="gui/$(id -u)/com.paul.info-radar-web"

mkdir -p "$RUNTIME_DIR/app" "$RUNTIME_DIR/published" "$HOME/Library/LaunchAgents"

/usr/bin/rsync -a --delete "$PROJECT_DIR/src/" "$RUNTIME_DIR/app/src/"
/usr/bin/rsync -a --delete "$PROJECT_DIR/web/" "$RUNTIME_DIR/app/web/"
/usr/bin/rsync -a --delete "$PROJECT_DIR/.venv/" "$RUNTIME_DIR/.venv/"
/usr/bin/rsync -a "$PROJECT_DIR/.info_radar/published/" "$RUNTIME_DIR/published/"

# The project venv is editable during development, but a resident LaunchAgent must
# not follow its .pth file back into the macOS-protected Documents directory.
/usr/bin/find "$RUNTIME_DIR/.venv" -path '*/site-packages/__editable__.info_radar-*.pth' -delete

cp "$PROJECT_DIR/ops/bin/run-web.sh" "$RUNTIME_DIR/run-web.sh"
chmod 755 "$RUNTIME_DIR/run-web.sh"

if [[ ! -f "$RUNTIME_DIR/.env" ]]; then
  if [[ -f "$PROJECT_DIR/.env" ]]; then
    cp -p "$PROJECT_DIR/.env" "$RUNTIME_DIR/.env"
  else
    printf '%s\n' '# Local API credentials for info_radar.' > "$RUNTIME_DIR/.env"
  fi
fi

if ! grep -q '^INFO_RADAR_WEB_OUTPUT_DIR=' "$RUNTIME_DIR/.env"; then
  printf '\nINFO_RADAR_WEB_OUTPUT_DIR="%s"\n' "$RUNTIME_DIR/published" >> "$RUNTIME_DIR/.env"
fi
chmod 600 "$RUNTIME_DIR/.env"

cp "$PROJECT_DIR/ops/launchd/com.paul.info-radar-web.plist" "$LAUNCH_AGENT"
launchctl bootout "$SERVICE" 2>/dev/null || true
bootstrapped=0
for attempt in {1..15}; do
  if launchctl bootstrap "gui/$(id -u)" "$LAUNCH_AGENT" 2>/dev/null; then
    bootstrapped=1
    break
  fi
  sleep 1
done
if (( ! bootstrapped )); then
  print -u2 "Info Radar service could not be registered with launchd"
  exit 1
fi
launchctl kickstart -k "$SERVICE"

printf 'Info Radar service installed at %s\n' "$RUNTIME_DIR"
