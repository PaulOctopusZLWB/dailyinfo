#!/bin/zsh
set -euo pipefail

CONFIG_PATH="${INFO_RADAR_REMOTE_CONFIG:-$HOME/.config/info-radar/remote.env}"
if [[ -f "$CONFIG_PATH" ]]; then
  source "$CONFIG_PATH"
fi

REMOTE_HOST="${INFO_RADAR_REMOTE_HOST:?Set INFO_RADAR_REMOTE_HOST in $CONFIG_PATH or the environment}"
REMOTE_USER="${INFO_RADAR_REMOTE_USER:-$USER}"
REMOTE_VAULT="${INFO_RADAR_REMOTE_VAULT:-/Users/$REMOTE_USER/Documents/Obsidian/Supcon}"
LOCAL_VAULT="${INFO_RADAR_LOCAL_VAULT:-$HOME/Documents/Obsidian/Supcon}"
RADAR_SUBDIR="${INFO_RADAR_OBSIDIAN_SUBDIR:-信息雷达}"
HOST_KEY_ALIAS="${INFO_RADAR_SSH_HOST_KEY_ALIAS:-info-radar-mini}"
KNOWN_HOSTS="${INFO_RADAR_SSH_KNOWN_HOSTS:-$HOME/.config/info-radar/known_hosts}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$LOCAL_VAULT/.info-radar-pull-backups/$TIMESTAMP"
RSYNC_ARGS=(--archive --itemize-changes --backup --backup-dir="$BACKUP_DIR")
SSH_COMMAND="/usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=$HOST_KEY_ALIAS -o UserKnownHostsFile=$KNOWN_HOSTS"

if [[ ! -f "$KNOWN_HOSTS" ]]; then
  print -u2 "info-radar pull: known-hosts file not found at $KNOWN_HOSTS"
  exit 1
fi

if [[ "${1:-}" == "--dry-run" ]]; then
  RSYNC_ARGS+=(--dry-run)
fi

mkdir -p "$LOCAL_VAULT/$RADAR_SUBDIR" "$BACKUP_DIR"
/usr/bin/rsync -e "$SSH_COMMAND" "${RSYNC_ARGS[@]}" \
  "$REMOTE_USER@$REMOTE_HOST:$REMOTE_VAULT/$RADAR_SUBDIR/" \
  "$LOCAL_VAULT/$RADAR_SUBDIR/"

printf 'Info Radar Obsidian pull complete from %s@%s:%s/%s\n' \
  "$REMOTE_USER" "$REMOTE_HOST" "$REMOTE_VAULT" "$RADAR_SUBDIR"
