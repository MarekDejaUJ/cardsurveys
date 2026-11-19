# Installing Card Surveys on a server

The installer supports Debian and Ubuntu (apt) and Fedora, RHEL and Rocky Linux (dnf). It needs Python 3.11 or later, outgoing access to the Python package index during installation, and, for account e-mails, an SMTP relay.

## System installation (root)

Copy the `cardsurveys` folder of the repository to the server and run, from inside it:

```sh
sudo ./deploy/install.sh --server-name survey.example.org --web nginx \
     --smtp-host smtp.example.org --smtp-port 587 --smtp-starttls \
     --mail-sender "Card Surveys <no-reply@example.org>"
```

The installer:

1. installs `python3` (with `venv`), `rsync`, `curl`, `sqlite` and, when asked, nginx or Apache;
2. creates the system account `cardsurveys`;
3. copies the code to `/opt/cardsurveys` and creates a virtual environment with the pinned requirements;
4. writes `/etc/cardsurveys/cardsurveys.env` (readable by root and the service account only) with a new secret key;
5. creates or upgrades the database in `/var/lib/cardsurveys`;
6. installs and starts `cardsurveys.service` (Gunicorn on `127.0.0.1:8002`) and `cardsurveys-backup.timer` (daily backup at 03:15);
7. configures nginx or Apache as a reverse proxy for the path `/cards` and redirects the bare address of the host to it;
8. runs `deploy/smoke_test.sh`.

Then create the administrator and, optionally, the demonstration surveys:

```sh
sudo /opt/cardsurveys/deploy/manage.sh create-admin --email you@uj.edu.pl
sudo /opt/cardsurveys/deploy/manage.sh seed-demos
```

`create-admin` asks for the password. The administrator account is confirmed at once; other accounts confirm their address through the e-mailed link.

Options: `--prefix` (URL path, default `/cards`), `--port` (default 8002), `--web nginx|apache|none`, `--https` (secure cookies and an `https` public URL), `--app-dir`, `--data-dir`, `--user`, `--no-packages`. Without `--smtp-host`, account e-mails are written as files to `/var/lib/cardsurveys/mail`; set `CARDS_MAIL_BACKEND=smtp` and the SMTP variables in the configuration file later and restart the service.

## Installation without root

On a host where only a user account is available:

```sh
./deploy/install.sh --user-mode --port 32417
```

The code and the virtual environment go to `~/cardsurveys`, the data to `~/cardsurveys/var`, the configuration to `~/cardsurveys/.env`, and the service runs as a user-level systemd unit. The service keeps running after logout only when an administrator enables lingering for the account (`loginctl enable-linger USER`). The web server is then configured by the administrator with the example in `deploy/apache.conf.example` or `deploy/nginx.conf.example`.

On an account without lingering and without a web server, Gunicorn can serve the site directly on a high port and run in a tmux session:

```sh
./deploy/install.sh --user-mode --tmux --listen 0.0.0.0:32417 --server-name host.example.org:32417
```

The site then answers at `http://host.example.org:32417/cards/`. The installer adds two cron entries for the account (start at boot, backup at 03:15); `tmux attach -t cardsurveys` shows the running application and errors go to `~/cardsurveys/var/gunicorn.log`. After a change in `~/cardsurveys/.env`, stop the session (`tmux kill-session -t cardsurveys`) and start it again (`tmux new-session -d -s cardsurveys ~/cardsurveys/deploy/run.sh`). Plain HTTP suits a demonstration; a study with participants needs HTTPS (section HTTPS).

## Accounts without e-mail

On a server that sends no e-mail, set `CARDS_EMAIL_CONFIRMATION=0` (installer option `--no-email-confirmation`). An account with an address in an allowed domain then works right after registration, and the application sends no account e-mail. The administrator sets a new password for a researcher who forgot one (account list, "set a new password"); the password is shown once and the researcher changes it in the account settings. Without confirmation, nothing proves that the person registering holds the address, so this setting suits a demonstration or a closed group; with `CARDS_EMAIL_CONFIRMATION=1` and an SMTP server, accounts still marked as unconfirmed confirm their address before the next login.

## Existing Apache virtual host

Inside an existing `VirtualHost` three lines suffice (modules `proxy`, `proxy_http`, `headers`):

```apache
ProxyPass        /cards http://127.0.0.1:8002/cards
ProxyPassReverse /cards http://127.0.0.1:8002/cards
RequestHeader set X-Forwarded-Proto expr=%{REQUEST_SCHEME}
```

## HTTPS

Use the institution's certificate or certbot (`certbot --nginx -d survey.example.org` or `certbot --apache`). With HTTPS in place set `CARDS_SECURE_COOKIES=1` and `CARDS_PUBLIC_BASE_URL=https://survey.example.org` in the configuration file and restart: `sudo systemctl restart cardsurveys`.

## Privacy of logs

The application stores no network address. Gunicorn's access log is off, and the nginx and Apache examples use a log format without client addresses. Other logs of the host (for example a central proxy) are outside the application and should follow the same rule when a study promises it.

## Backups and restore

`cardsurveys-backup.timer` runs `deploy/backup.sh` daily: an online SQLite backup with an integrity check, compressed, kept for `CARDS_BACKUP_DAYS` days (default 30) in `/var/lib/cardsurveys/backups`. A backup on demand: `sudo systemctl start cardsurveys-backup.service`. To restore, stop the service, decompress a backup over `cardsurveys.sqlite3`, and start the service again.

## Updates

Copy the newer `cardsurveys` folder to the server and run from inside it:

```sh
sudo ./deploy/update.sh        # or ./deploy/update.sh --user-mode
```

The script takes a backup, copies the code, installs the requirements, upgrades the database schema and restarts the service, then runs the smoke test.

## Capacity

Each answer writes a few rows to one SQLite file in write-ahead-log mode, shared by the Gunicorn workers. A load test with 100 respondents answering at the same moment is part of the test suite (`tools/load_test.py`); run it against a new server before a large launch. For heavier use, set `CARDS_DATABASE_URL` to a PostgreSQL database and install a PostgreSQL driver into the virtual environment.

## Moving a prepared survey to the server

Export the bundle in the studio ("Download the bundle") and import it on the server, in the studio or with:

```sh
sudo /opt/cardsurveys/deploy/manage.sh import-survey survey.json --owner you@uj.edu.pl --publish
```
