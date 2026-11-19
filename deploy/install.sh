#!/usr/bin/env bash
# Card Surveys: installation on a Linux server (Debian/Ubuntu with apt, Fedora/RHEL with dnf).
#
# System installation (as root, from the cardsurveys folder of the repository):
#   sudo ./deploy/install.sh --server-name survey.example.org --web nginx
# Installation for one user without root (user-level systemd; the web server is configured by the administrator):
#   ./deploy/install.sh --user-mode
# Installation for one user, served directly on a high port, kept running by tmux and cron:
#   ./deploy/install.sh --user-mode --tmux --listen 0.0.0.0:32417 --server-name host.example.org:32417
#
# Options:
#   --prefix PATH        URL prefix of the application (default /cards)
#   --port N             local port of Gunicorn (default 8002)
#   --listen ADDR:PORT   Gunicorn listens on this address with no web server in front (for example 0.0.0.0:32417)
#   --tmux               user mode: run in a tmux session, started again at boot by cron, with a nightly backup by cron
#   --web KIND           nginx | apache | none (default none)
#   --server-name HOST   host name for the web server configuration and the public URL
#   --https              the site is served over HTTPS (secure cookies, https public URL)
#   --app-dir DIR        code and virtual environment (default /opt/cardsurveys; ~/cardsurveys in user mode)
#   --data-dir DIR       database, backups and mail files (default /var/lib/cardsurveys; ~/cardsurveys/var in user mode)
#   --user NAME          service account (default cardsurveys; the current user in user mode)
#   --smtp-host HOST     SMTP relay for account e-mails (without it, e-mails are written to files in the data folder)
#   --smtp-port N        SMTP port (default 25)
#   --smtp-starttls      use STARTTLS
#   --mail-sender TEXT   sender of account e-mails, for example "Card Surveys <no-reply@uj.edu.pl>"
#   --no-email-confirmation  accounts work right after registration; no account e-mail is sent
#   --no-packages        do not install system packages
set -euo pipefail

PREFIX="/cards"; PORT="8002"; WEB="none"; SERVER_NAME=""; HTTPS=0
APP_DIR=""; DATA_DIR=""; SVC_USER=""; USER_MODE=0; PACKAGES=1
SMTP_HOST=""; SMTP_PORT="25"; SMTP_STARTTLS=0; MAIL_SENDER=""
LISTEN=""; TMUX_MODE=0; EMAIL_CONFIRMATION=1

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --listen) LISTEN="$2"; shift 2;;
    --tmux) TMUX_MODE=1; shift;;
    --no-email-confirmation) EMAIL_CONFIRMATION=0; shift;;
    --web) WEB="$2"; shift 2;;
    --server-name) SERVER_NAME="$2"; shift 2;;
    --https) HTTPS=1; shift;;
    --app-dir) APP_DIR="$2"; shift 2;;
    --data-dir) DATA_DIR="$2"; shift 2;;
    --user) SVC_USER="$2"; shift 2;;
    --user-mode) USER_MODE=1; shift;;
    --smtp-host) SMTP_HOST="$2"; shift 2;;
    --smtp-port) SMTP_PORT="$2"; shift 2;;
    --smtp-starttls) SMTP_STARTTLS=1; shift;;
    --mail-sender) MAIL_SENDER="$2"; shift 2;;
    --no-packages) PACKAGES=0; shift;;
    -h|--help) sed -n '2,27p' "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
say() { printf '\n== %s\n' "$*"; }

BEHIND_PROXY=1
if [ -n "$LISTEN" ]; then PORT="${LISTEN##*:}"; BEHIND_PROXY=0; fi
[ "$TMUX_MODE" -eq 1 ] && [ "$USER_MODE" -eq 0 ] && { echo "--tmux works with --user-mode" >&2; exit 2; }
[ "$TMUX_MODE" -eq 1 ] && ! command -v tmux >/dev/null && { echo "tmux not found" >&2; exit 1; }

if [ "$USER_MODE" -eq 1 ]; then
  SVC_USER="$(id -un)"
  APP_DIR="${APP_DIR:-$HOME/cardsurveys}"
  DATA_DIR="${DATA_DIR:-$APP_DIR/var}"
  ENV_FILE="$APP_DIR/.env"
  WEB="none"; PACKAGES=0
else
  [ "$(id -u)" -eq 0 ] || { echo "run as root (sudo), or use --user-mode" >&2; exit 1; }
  SVC_USER="${SVC_USER:-cardsurveys}"
  APP_DIR="${APP_DIR:-/opt/cardsurveys}"
  DATA_DIR="${DATA_DIR:-/var/lib/cardsurveys}"
  ENV_FILE="/etc/cardsurveys/cardsurveys.env"
  fi

if [ "$PACKAGES" -eq 1 ]; then
  say "system packages"
  if command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q
    pkgs="python3 python3-venv rsync curl sqlite3"
    [ "$WEB" = nginx ] && pkgs="$pkgs nginx"
    [ "$WEB" = apache ] && pkgs="$pkgs apache2"
    apt-get install -y -q $pkgs
  elif command -v dnf >/dev/null; then
    pkgs="python3 rsync curl sqlite"
    [ "$WEB" = nginx ] && pkgs="$pkgs nginx"
    [ "$WEB" = apache ] && pkgs="$pkgs httpd"
    dnf install -y -q $pkgs
  else
    echo "neither apt-get nor dnf found; install python3 (with venv), rsync and curl yourself and rerun with --no-packages" >&2
    exit 1
  fi
fi

if [ "$USER_MODE" -eq 0 ] && ! id "$SVC_USER" >/dev/null 2>&1; then
  say "service account $SVC_USER"
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SVC_USER"
fi

say "application files in $APP_DIR"
mkdir -p "$APP_DIR" "$DATA_DIR" "$DATA_DIR/backups" "$DATA_DIR/mail"
rsync -a --delete --exclude ".venv" --exclude "appdata" --exclude "var" --exclude ".env" --exclude "__pycache__" \
  --exclude ".pytest_cache" --exclude "test-results" "$SRC_DIR/" "$APP_DIR/"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
  say "configuration $ENV_FILE"
  mkdir -p "$(dirname "$ENV_FILE")"
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  SCHEME="http"; [ "$HTTPS" -eq 1 ] && SCHEME="https"
  PUBLIC=""; [ -n "$SERVER_NAME" ] && PUBLIC="$SCHEME://$SERVER_NAME"
  if [ -n "$SMTP_HOST" ]; then MAIL_BACKEND="smtp"; else MAIL_BACKEND="file"; fi
  cat > "$ENV_FILE" <<ENV
CARDS_SECRET_KEY=$SECRET
CARDS_HOME=$DATA_DIR
CARDS_DATABASE_URL=sqlite:///$DATA_DIR/cardsurveys.sqlite3
CARDS_URL_PREFIX=$PREFIX
CARDS_BIND=${LISTEN:-127.0.0.1:$PORT}
CARDS_PUBLIC_BASE_URL=$PUBLIC
CARDS_BEHIND_PROXY=$BEHIND_PROXY
CARDS_SECURE_COOKIES=$HTTPS
CARDS_LANGUAGES=pl,en
CARDS_DEFAULT_LANGUAGE=pl
CARDS_ALLOWED_EMAIL_DOMAINS=uj.edu.pl,student.uj.edu.pl,doctoral.uj.edu.pl
CARDS_REGISTRATION_OPEN=1
CARDS_EMAIL_CONFIRMATION=$EMAIL_CONFIRMATION
CARDS_MAIL_BACKEND=$MAIL_BACKEND
CARDS_MAIL_DIR=$DATA_DIR/mail
CARDS_SMTP_HOST=${SMTP_HOST:-localhost}
CARDS_SMTP_PORT=$SMTP_PORT
CARDS_SMTP_STARTTLS=$SMTP_STARTTLS
CARDS_SMTP_USER=
CARDS_SMTP_PASSWORD=
CARDS_MAIL_SENDER=${MAIL_SENDER:-Card Surveys <no-reply@localhost>}
ENV
fi

if [ "$USER_MODE" -eq 0 ]; then
  chown -R root:root "$APP_DIR"
  chmod -R go-w,a+rX "$APP_DIR"
  chown -R "$SVC_USER:$SVC_USER" "$DATA_DIR"
  chmod 750 "$DATA_DIR"
  chown root:"$SVC_USER" "$ENV_FILE"
  chmod 640 "$ENV_FILE"
else
  chmod 600 "$ENV_FILE"
fi

say "database"
CARDS_SERVICE_USER="$SVC_USER" CARDS_ENV_FILE="$ENV_FILE" "$APP_DIR/deploy/manage.sh" init-db

say "service"
APACHE_LOG="/var/log/httpd"; [ -d /etc/apache2 ] && APACHE_LOG="/var/log/apache2"
render() {
  sed -e "s#@APACHE_LOG@#$APACHE_LOG#g" -e "s#@USER@#$SVC_USER#g" -e "s#@APP_DIR@#$APP_DIR#g" -e "s#@ENV_FILE@#$ENV_FILE#g" -e "s#@DATA_DIR@#$DATA_DIR#g" \
      -e "s#@PREFIX@#$PREFIX#g" -e "s#@PORT@#$PORT#g" -e "s#@SERVER_NAME@#${SERVER_NAME:-_}#g" "$1"
}
if [ "$USER_MODE" -eq 0 ]; then
  render "$APP_DIR/deploy/cardsurveys.service" > /etc/systemd/system/cardsurveys.service
  render "$APP_DIR/deploy/cardsurveys-backup.service" > /etc/systemd/system/cardsurveys-backup.service
  cp "$APP_DIR/deploy/cardsurveys-backup.timer" /etc/systemd/system/cardsurveys-backup.timer
  systemctl daemon-reload
  systemctl enable --now cardsurveys.service cardsurveys-backup.timer
  systemctl restart cardsurveys.service
elif [ "$TMUX_MODE" -eq 1 ]; then
  tmux kill-session -t cardsurveys 2>/dev/null || true
  tmux new-session -d -s cardsurveys "$APP_DIR/deploy/run.sh"
  if ( crontab -l 2>/dev/null | grep -v '# cardsurveys$'
       echo "@reboot tmux new-session -d -s cardsurveys $APP_DIR/deploy/run.sh # cardsurveys"
       echo "15 3 * * * $APP_DIR/deploy/backup.sh >/dev/null # cardsurveys" ) | crontab - ; then
    echo "cron: start at boot and nightly backup at 03:15"
  else
    echo "note: cron is not available for this account; after a reboot start again with: tmux new-session -d -s cardsurveys $APP_DIR/deploy/run.sh"
  fi
else
  mkdir -p "$HOME/.config/systemd/user"
  render "$APP_DIR/deploy/cardsurveys-user.service" > "$HOME/.config/systemd/user/cardsurveys.service"
  systemctl --user daemon-reload
  systemctl --user enable --now cardsurveys.service
  systemctl --user restart cardsurveys.service
  if [ "$(loginctl show-user "$SVC_USER" -p Linger --value 2>/dev/null)" != "yes" ]; then
    echo "note: the service stops when you log out until an administrator runs: loginctl enable-linger $SVC_USER"
  fi
fi

if [ "$WEB" = nginx ]; then
  say "nginx"
  if [ -d /etc/nginx/sites-available ]; then
    render "$APP_DIR/deploy/nginx.conf.example" > /etc/nginx/sites-available/cardsurveys
    ln -sf /etc/nginx/sites-available/cardsurveys /etc/nginx/sites-enabled/cardsurveys
  else
    render "$APP_DIR/deploy/nginx.conf.example" > /etc/nginx/conf.d/cardsurveys.conf
  fi
  if command -v getenforce >/dev/null && [ "$(getenforce)" = Enforcing ]; then setsebool -P httpd_can_network_connect 1; fi
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
elif [ "$WEB" = apache ]; then
  say "apache"
  if [ -d /etc/apache2/sites-available ]; then
    render "$APP_DIR/deploy/apache.conf.example" > /etc/apache2/sites-available/cardsurveys.conf
    a2enmod -q proxy proxy_http headers
    a2ensite -q cardsurveys
    apache2ctl configtest
    systemctl reload apache2
  else
    render "$APP_DIR/deploy/apache.conf.example" > /etc/httpd/conf.d/cardsurveys.conf
    if command -v getenforce >/dev/null && [ "$(getenforce)" = Enforcing ]; then setsebool -P httpd_can_network_connect 1; fi
    apachectl configtest
    systemctl enable --now httpd
    systemctl reload httpd
  fi
fi

say "smoke test"
sleep 2
"$APP_DIR/deploy/smoke_test.sh" "http://127.0.0.1:$PORT$PREFIX"

cat <<DONE

Card Surveys is installed.
  code and environment: $APP_DIR
  data and backups:     $DATA_DIR
  configuration:        $ENV_FILE
Next steps:
  1. administrator account:
     $APP_DIR/deploy/manage.sh create-admin --email you@uj.edu.pl
  2. demonstration surveys (optional):
     $APP_DIR/deploy/manage.sh seed-demos
  3. a prepared survey bundle:
     $APP_DIR/deploy/manage.sh import-survey /path/to/survey.json --publish
DONE
[ "$EMAIL_CONFIRMATION" -eq 0 ] && echo "Accounts work right after registration; the application sends no account e-mail (CARDS_EMAIL_CONFIRMATION=0 in $ENV_FILE)."
[ "$TMUX_MODE" -eq 1 ] && echo "The application runs in the tmux session cardsurveys (tmux attach -t cardsurveys; detach with Ctrl-b d)."
[ -z "$SMTP_HOST" ] && [ "$EMAIL_CONFIRMATION" -eq 1 ] && echo "Account e-mails are written to $DATA_DIR/mail until CARDS_MAIL_BACKEND=smtp and the SMTP settings are set in $ENV_FILE."
exit 0
