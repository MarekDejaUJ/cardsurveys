# Card Surveys

Card Surveys is a web system for surveys in which respondents arrange cards. A respondent orders cards, sorts them into rows or piles, connects them with arrows, places them on a plane, answers questions about pairs, sorts small blocks of items into levels, or taps the cards of a block in order. Every arrangement is stored as the set of statements it makes about pairs of cards, so that the data can be analyzed as structures and not only as scores.

The system serves researchers of the Jagiellonian University: an account can be created with an address in `uj.edu.pl`, `student.uj.edu.pl` or `doctoral.uj.edu.pl`. Respondents need no account.

Author: Marek Deja, Institute of Information Studies, Jagiellonian University. Licence: GNU General Public License, version 3 or later (`LICENSE`).

## Techniques

| Technique | The respondent | What is recorded |
|---|---|---|
| Tier board | puts each card in one of k rows; a lower row comes first | orders with ties and at most k levels |
| Tier board with an aside region | as above, or sets a card aside | as above; a card set aside stands in no relation to any card |
| Arrow board | draws arrows; arrows that follow from them appear dashed; optional confirmation that blank pairs are unrelated | every consistent order (strict partial order) |
| Pile board | sorts cards into piles | which cards belong together (a partition) |
| Plane board | places each card at a point | orders of dimension at most two |
| Pairwise questions | answers each pair: before, after, unrelated, cannot decide | every answer pattern; consistency is checked afterwards |
| Subjective Order Blocks | sorts the items of each small block into k levels or a side bin | for every pair in a block: one before the other, or no order |
| Tap-order blocks | taps the cards of each block in order; an optional anchor card appears in every block | a full order of every block; with the anchor, whether each item lies above or below the reference |

Block techniques draw their blocks from verified balanced incomplete block designs (every item equally often, every pair of items together equally often). Tap-order blocks also offer a question after every block, repeated blocks for a within-session check, attention blocks, practice blocks, and variants that choose a different item set according to an earlier answer.

A survey is a sequence of modules: consent, information screens, forms with questions (including questions shown only for certain earlier answers), boards, block tasks, random assignment to arms (permuted blocks within strata of earlier answers), materials shown by arm, a free choice of material, an explanation at the end, and thanks. A second session can repeat marked tasks.

## Languages

Every text a respondent sees is entered per language. A survey declares its languages (Polish and English by default) and its default language; respondents get the language of their browser and can switch. The interface itself exists in Polish and English. A further language needs a catalog file in `cardsurveys/catalogs/` and an entry in `CARDS_LANGUAGES`; surveys can then add it without changes to the code.

## Moving surveys between installations

A whole survey is one JSON file, the survey bundle (format described in `docs/BUNDLE_FORMAT.md`). A bundle is imported in the studio (upload or paste) or on the server:

```sh
./deploy/manage.sh import-survey survey.json --publish
```

Import checks the bundle; publishing additionally requires every text in every survey language.

## Data

The studio offers one ZIP per survey: the bundle, a description with the codebook, one CSV file per table (responses, answers, block screens, pair observations, screen times, arm assignments) and, for each board task, a folder with `study.json`, `responses.csv`, `placements.csv`, `judgments.csv` and `confirmations.csv`. The columns are listed in `docs/DATA.md`, and `docs/examples/` holds example exports of the demonstration surveys. Preview responses never enter the data.

The system stores no network address and no browser description. A respondent who withdraws loses every answer; only the information that a response was withdrawn remains.

## Versions

The system follows Semantic Versioning; `CHANGELOG.md` lists the changes of every version. The page footer shows the version of the installation, and every export records the version that wrote it. Releases are tagged in Git as `cardsurveys-vX.Y.Z`.

## Running locally

Python 3.11 or later.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
export CARDS_HOME=$PWD
.venv/bin/flask --app cardsurveys init-db
.venv/bin/flask --app cardsurveys create-admin --email you@uj.edu.pl
.venv/bin/flask --app cardsurveys seed-demos
.venv/bin/python run.py
```

Open `http://127.0.0.1:5002/cards/`. In development, account e-mails are printed to the console (`CARDS_MAIL_BACKEND=console`).

## Installing on a server

`deploy/install.sh` installs the system on Debian, Ubuntu, Fedora or RHEL: a service account, the code in `/opt/cardsurveys`, data in `/var/lib/cardsurveys`, configuration in `/etc/cardsurveys/cardsurveys.env`, Gunicorn under systemd, a daily backup timer, and optionally nginx or Apache in front. Without root, `--user-mode` installs into the home folder with a user-level service. Details, TLS, SMTP and updates: `docs/INSTALL.md`; a rented server behind Cloudflare (domain, HTTPS tunnel, account e-mails, off-site backups): `docs/DEPLOY_VPS_CLOUDFLARE.md`.

## Tests

```sh
.venv/bin/python -m pytest                 # unit and integration tests
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -m browser      # widgets and full surveys in Chromium, desktop and phone size
python tools/load_test.py http://127.0.0.1/cards SLUG --respondents 100 --concurrency 100
```

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `CARDS_SECRET_KEY` | key that signs sessions and e-mail links | `dev-change-me` (never on a server) |
| `CARDS_HOME` | folder for the database and mail files in development | current folder |
| `CARDS_DATABASE_URL` | SQLAlchemy URL of the database | `sqlite:///$CARDS_HOME/appdata/cardsurveys.sqlite3` |
| `CARDS_URL_PREFIX` | path under which every page is served | `/cards` |
| `CARDS_PUBLIC_BASE_URL` | scheme and host used in links and e-mails | taken from the request |
| `CARDS_BEHIND_PROXY` | `1` trusts the forwarded headers of the reverse proxy | `0` |
| `CARDS_SECURE_COOKIES` | `1` sends cookies over HTTPS only | `0` |
| `CARDS_LANGUAGES` | languages offered to surveys and to the interface | `pl,en` |
| `CARDS_DEFAULT_LANGUAGE` | default interface language | `pl` |
| `CARDS_ALLOWED_EMAIL_DOMAINS` | domains allowed to register | `uj.edu.pl,student.uj.edu.pl,doctoral.uj.edu.pl` |
| `CARDS_REGISTRATION_OPEN` | `0` closes self-registration | `1` |
| `CARDS_SESSION_HOURS` | length of a researcher session | `8` |
| `CARDS_MAIL_BACKEND` | `smtp`, `file` or `console` | `console` |
| `CARDS_SMTP_HOST`, `CARDS_SMTP_PORT`, `CARDS_SMTP_STARTTLS`, `CARDS_SMTP_SSL`, `CARDS_SMTP_USER`, `CARDS_SMTP_PASSWORD` | SMTP relay | `localhost`, `25` |
| `CARDS_MAIL_SENDER` | sender of account e-mails | `Card Surveys <no-reply@localhost>` |
| `CARDS_BIND`, `CARDS_WORKERS`, `CARDS_THREADS` | Gunicorn address and capacity | `127.0.0.1:8002`, `2`, `4` |
| `CARDS_BACKUP_DAYS` | days to keep backups | `30` |
