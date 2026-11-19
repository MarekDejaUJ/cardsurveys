# Changelog

Versions follow Semantic Versioning (<https://semver.org/>): the third number changes with fixes, the second with new features that keep earlier surveys, bundles and exports working, the first with a change that breaks them. The survey bundle format and the export format (`cardsurveys-export-1`) carry their own version, which changes only with an incompatible change. Every export records the version of the system that wrote it, and the page footer shows the version of the installation. Every release is tagged in Git as `cardsurveys-vX.Y.Z`.

## 1.4.0 (2026-11-19)

- Form screens with the respondent's material (`panel_from`, `panel_label`) in a panel above the questions, as in tap-order blocks.
- Questions in random order (`shuffle_questions`): the named questions change places at random among the positions they hold, once per respondent, and `screens.csv` records the order shown (`question_order`).
- Paradata of a screen (`paradata`): the browser records the links opened on the screen and how often and how long the page was left, and `screens.csv` gives `leaves`, `away_ms` and `links`. A refused form submission keeps the counts. The privacy page states what is recorded. The database gains four columns of `screen_times` (migration `0002`, applied by `manage.sh init-db`).
- Web addresses in question labels become links that open in a new tab.
- The studio editor keeps every setting of a module: the material panel of tap-order blocks, the anchor card that closes the block, the note on the anchor card and the position of the attention card were lost when such a module was saved in the editor.
- Polish privacy page: "Osoby wypełniające ankietę" in place of "Respondenci".

## 1.3.0 (2026-11-19)

- Tap-order blocks whose anchor card closes the block (`anchor_closes`): tapping the anchor ends the order of the block, the cards left untapped lie below the anchor, marked "=" and tied with one another, and the anchor is placed after the last card when every other card is tapped. "Undo" reopens the block. The response of such a block ends at the anchor, its untapped pairs are recorded with the relation `tie`, and the tap events record the automatic placement as `auto`. Tasks without the setting keep the full order of every card.
- A note on the anchor card (`anchor_note`), shown under the criterion on every block of the task.
- The position of the instructed card in attention blocks (`attention_position`): `last` as before or `first`, with the default label "Tap this card first"; beside an anchor that closes the block, the anchor is left out of the count.
- The browser tests wait for every new page before tapping, and a browser test covers the closing anchor.

## 1.2.2 (2026-11-18)

- Polish interface: the name "Card Surveys" in both languages, with the Polish home-page title "Card Surveys: ankiety z układaniem kart" and the name in the subjects and texts of the account e-mails; "porównania parami" in place of "pytania o pary" and "bloki porządkowania" in place of "bloki kolejności", in the interface, the demonstration surveys, the new-module templates and the example export. The English interface, the keys of the catalog and the behavior stay unchanged; demonstration surveys already in a database keep their titles.

## 1.2.1 (2026-11-18)

- Gender-neutral wording of the Polish interface: "osoba wypełniająca ankietę" and "osoby odpowiadające" in place of "respondent", "osoby prowadzące badania" in place of "badacze", "administracja serwisu" in place of "administrator", the roles "prowadzenie badań" and "administracja", and "Należy do" and "Przekaż do" in the list of surveys of the administration page. The English interface, the keys of the catalog and the behavior stay unchanged.

## 1.2.0 (2026-11-17)

- Accounts without e-mail confirmation (`CARDS_EMAIL_CONFIRMATION=0`, installer option `--no-email-confirmation`): an account with an allowed address works right after registration and the application sends no account e-mail; a second registration with the same address is refused with a message; "forgot password" asks the holder to contact the administrator. The address stays marked as unconfirmed, so switching confirmation on later asks those accounts to confirm before the next login.
- The administrator sets a new password for an account in the account list; the password is shown once and the account's open sessions end.
- Direct serving without a web server in front: installer option `--listen ADDR:PORT` (Gunicorn listens there and the proxy headers are ignored), and the bare address of the host redirects to the application.
- User installations on an account whose user services stop at logout: installer option `--tmux` runs the application in a tmux session (`deploy/run.sh`), with cron entries that start it at boot and make the nightly backup; `deploy/update.sh --user-mode` reloads such a session after an update, and `deploy/backup.sh` reads the configuration file when cron runs it.
- Guide for a rented server behind Cloudflare: domain, DNS, tunnel, account e-mails through Cloudflare Email Service, off-site backups in R2, server hardening (`docs/DEPLOY_VPS_CLOUDFLARE.md`).

## 1.1.3 (2026-11-17)

- The load test (`tools/load_test.py`) sends the page address as the referrer with every answer, as a browser does, so the test runs against a server with HTTPS.

## 1.1.2 (2026-11-17)

- Forms work over HTTPS: the referrer policy (response header and page meta tag) is `same-origin`, so browsers send the referrer within the site, which the CSRF check over HTTPS requires, and send none to other sites. With the policy `no-referrer` every form submission over HTTPS was refused with status 400.

## 1.1.1 (2026-11-17)

- The nginx and Apache configurations redirect the bare address of the host to the application, so a host name of its own (for example a subdomain) opens the surveys' start page without the path `/cards`.

## 1.1.0 (2026-11-17)

- Tap-order blocks can show the respondent's material from earlier stimulus and choice modules in a panel beside every block (`panel_from`, at most four modules, and `panel_label`); the bundle check refuses a panel that names a later or unknown module.
- The export description (`description.json`) records the name and version of the system that wrote it; the page footer shows the version.
- Example exports of three demonstration surveys (Subjective Order Blocks, tap-order blocks with an anchor, the arrow board), answered by simulated respondents, in `docs/examples/`, with the generator `tools/example_exports.py`.

## 1.0.0 (2026-11-17)

First version.

- Researcher accounts for addresses in `uj.edu.pl`, `student.uj.edu.pl` and `doctoral.uj.edu.pl`, with e-mail verification and an administrator account.
- Surveys as sequences of modules: consent, information, forms with conditional questions, boards (tier, tier with an aside region, arrow with confirmation of blank pairs, pile, plane, pairwise questions), Subjective Order Blocks, tap-order blocks (anchor card, gate question, repeated, attention and practice blocks, variants by an earlier answer), random assignment to arms by permuted blocks within strata, materials by arm, a free choice of material, debriefing with withdrawal, thanks, and a second session.
- Block designs from a verified library of balanced incomplete block designs.
- Content entered per language, with a language registry (Polish and English); interface in Polish and English.
- Survey bundles for moving surveys between installations; exports with the codebook, one table per kind of record and the board folders.
- Installation on a Linux server (Debian, Ubuntu, Fedora, RHEL families) with systemd, nginx or Apache, and daily backups.
