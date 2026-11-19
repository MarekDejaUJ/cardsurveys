#!/usr/bin/env bash
# Online backup of the SQLite database (safe while the service runs) and removal of old backups.
#   CARDS_DATABASE_URL  sqlite:////path/to/cardsurveys.sqlite3 (from the configuration file)
#   CARDS_HOME          data folder; backups go to $CARDS_HOME/backups
#   CARDS_BACKUP_DAYS   days to keep (default 30)
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# run from cron in a user installation: the settings come from the configuration file
if [ -z "${CARDS_DATABASE_URL:-}" ] && [ -r "$APP_DIR/.env" ]; then
  while IFS= read -r l; do case "$l" in ''|\#*) ;; *) export "$l";; esac; done < "$APP_DIR/.env"
fi
DB="${CARDS_DATABASE_URL#sqlite:///}"
DEST="${CARDS_HOME:?}/backups"
KEEP="${CARDS_BACKUP_DAYS:-30}"
mkdir -p "$DEST"
STAMP="$(date +%Y-%m-%d_%H%M)"
"$APP_DIR/.venv/bin/python" - "$DB" "$DEST/cardsurveys-$STAMP.sqlite3" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
dst.close(); src.close()
if ok != "ok":
    sys.exit("backup integrity check failed: " + ok)
PY
gzip -f "$DEST/cardsurveys-$STAMP.sqlite3"
find "$DEST" -name 'cardsurveys-*.sqlite3.gz' -mtime +"$KEEP" -delete
echo "backup written: $DEST/cardsurveys-$STAMP.sqlite3.gz"
