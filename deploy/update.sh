#!/usr/bin/env bash
# Update an installation from a newer copy of the cardsurveys folder:
#   sudo ./deploy/update.sh              (system installation in /opt/cardsurveys)
#   ./deploy/update.sh --user-mode       (installation in ~/cardsurveys)
# Takes a backup, copies the code, installs the requirements, upgrades the database and restarts the service.
set -euo pipefail
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_MODE=0; APP_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --user-mode) USER_MODE=1; shift;;
    --app-dir) APP_DIR="$2"; shift 2;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
if [ "$USER_MODE" -eq 1 ]; then
  [ -z "$APP_DIR" ] && [ -f "$SRC_DIR/.env" ] && APP_DIR="$SRC_DIR"
  APP_DIR="${APP_DIR:-$HOME/cardsurveys}"; ENV_FILE="$APP_DIR/.env"; CTL="systemctl --user"
else
  [ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
  [ -z "$APP_DIR" ] && [ "$SRC_DIR" = "/opt/cardsurveys" ] && APP_DIR="$SRC_DIR"
  APP_DIR="${APP_DIR:-/opt/cardsurveys}"; ENV_FILE="/etc/cardsurveys/cardsurveys.env"; CTL="systemctl"
fi
if [ "$USER_MODE" -eq 0 ]; then
  systemctl start cardsurveys-backup.service
else
  ( while IFS= read -r l; do case "$l" in ''|\#*) ;; *) export "$l";; esac; done < "$ENV_FILE"; "$APP_DIR/deploy/backup.sh" )
fi
if [ "$SRC_DIR" != "$APP_DIR" ]; then
  rsync -a --delete --exclude ".venv" --exclude "appdata" --exclude "var" --exclude ".env" --exclude "__pycache__" \
    --exclude ".pytest_cache" --exclude "test-results" "$SRC_DIR/" "$APP_DIR/"
fi
[ "$USER_MODE" -eq 0 ] && chown -R root:root "$APP_DIR" && chmod -R go-w,a+rX "$APP_DIR"
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
CARDS_ENV_FILE="$ENV_FILE" "$APP_DIR/deploy/manage.sh" init-db
PIDFILE="$(grep '^CARDS_HOME=' "$ENV_FILE" | cut -d= -f2)/gunicorn.pid"
if [ "$USER_MODE" -eq 1 ] && [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill -HUP "$(cat "$PIDFILE")"     # started by deploy/run.sh (tmux): new workers load the new code
else
  $CTL restart cardsurveys.service
fi
sleep 2
PORT="$(grep '^CARDS_BIND=' "$ENV_FILE" | cut -d: -f2)"
PREFIX="$(grep '^CARDS_URL_PREFIX=' "$ENV_FILE" | cut -d= -f2)"
"$APP_DIR/deploy/smoke_test.sh" "http://127.0.0.1:${PORT:-8002}${PREFIX}"
