#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${INFO_RADAR_PROJECT_DIR:-$HOME/Documents/info_radar}"
UV_BIN="${INFO_RADAR_UV_BIN:-$HOME/.local/bin/uv}"
BRANCH="${INFO_RADAR_UPDATE_BRANCH:-main}"
SKIP_PULL=0

if [[ "${1:-}" == "--no-pull" ]]; then
  SKIP_PULL=1
fi

if [[ ! -x "$UV_BIN" ]]; then
  print -u2 "info-radar update: uv not found at $UV_BIN"
  exit 1
fi

cd "$PROJECT_DIR"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  print -u2 "info-radar update: tracked worktree changes must be committed before deployment"
  exit 1
fi

if (( ! SKIP_PULL )); then
  git fetch origin "$BRANCH"
  git merge --ff-only "origin/$BRANCH"
fi

export UV_CACHE_DIR="${UV_CACHE_DIR:-$PROJECT_DIR/.tmp/uv-cache}"
"$UV_BIN" sync --frozen
"$PROJECT_DIR/ops/bin/install-web-service.sh"

for attempt in {1..20}; do
  if /usr/bin/curl -fsS http://127.0.0.1:8787/api/health >/dev/null; then
    printf 'Info Radar hosted update complete: %s@%s\n' "$BRANCH" "$(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 1
done

print -u2 "info-radar update: service failed health verification"
exit 1
