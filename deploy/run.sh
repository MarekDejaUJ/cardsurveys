#!/usr/bin/env bash
# Run Card Surveys in the foreground with the configuration of a user installation, for an
# account whose user services stop at logout. Start it in a detached tmux session:
#   tmux new-session -d -s cardsurveys ~/cardsurveys/deploy/run.sh
# Errors go to $CARDS_HOME/gunicorn.log; ./deploy/update.sh --user-mode reloads it after an update.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${CARDS_ENV_FILE:-$APP_DIR/.env}"
[ -r "$ENV_FILE" ] || { echo "cannot read $ENV_FILE" >&2; exit 1; }
vars=("PYTHONDONTWRITEBYTECODE=1")
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|\#*) continue;; esac
  vars+=("$line")
  case "$line" in CARDS_HOME=*) HOME_DIR="${line#CARDS_HOME=}";; esac
done < "$ENV_FILE"
HOME_DIR="${HOME_DIR:-$APP_DIR/var}"
mkdir -p "$HOME_DIR"
cd "$APP_DIR"
exec env "${vars[@]}" "$APP_DIR/.venv/bin/gunicorn" --config "$APP_DIR/deploy/gunicorn.conf.py" \
  --pid "$HOME_DIR/gunicorn.pid" --error-logfile "$HOME_DIR/gunicorn.log" wsgi:app
