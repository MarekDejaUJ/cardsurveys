#!/usr/bin/env bash
# Run a Card Surveys command with the server configuration, as the service account.
#   ./deploy/manage.sh create-admin --email you@uj.edu.pl
#   ./deploy/manage.sh seed-demos
#   ./deploy/manage.sh import-survey survey.json --publish
#   ./deploy/manage.sh list-surveys
#   ./deploy/manage.sh export-data 3 /tmp/study-3
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${CARDS_ENV_FILE:-}"
if [ -z "$ENV_FILE" ]; then
  if [ -f "$APP_DIR/.env" ]; then ENV_FILE="$APP_DIR/.env"; else ENV_FILE=/etc/cardsurveys/cardsurveys.env; fi
fi
[ -r "$ENV_FILE" ] || { echo "cannot read $ENV_FILE (run with sudo?)" >&2; exit 1; }
vars=("PYTHONDONTWRITEBYTECODE=1" "FLASK_SKIP_DOTENV=1")
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|\#*) continue;; esac
  vars+=("$line")
done < "$ENV_FILE"
SVC_USER="${CARDS_SERVICE_USER:-cardsurveys}"
cd "$APP_DIR"
if [ "$(id -u)" -eq 0 ] && id "$SVC_USER" >/dev/null 2>&1; then
  exec runuser -u "$SVC_USER" -- env "${vars[@]}" "$APP_DIR/.venv/bin/flask" --app cardsurveys "$@"
fi
exec env "${vars[@]}" "$APP_DIR/.venv/bin/flask" --app cardsurveys "$@"
