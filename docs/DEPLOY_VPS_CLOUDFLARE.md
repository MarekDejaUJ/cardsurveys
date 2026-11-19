# Card Surveys on a VPS behind Cloudflare

This guide sets up Card Surveys on a small rented server (VPS) whose only public face is Cloudflare. Cloudflare holds the domain and its DNS, serves the site over HTTPS through a tunnel (the server opens no web ports to the internet), sends the account e-mails and keeps an off-site copy of the backups. The server keeps every survey answer.

```
respondent   --HTTPS-->    Cloudflare (domain, certificate)
             --tunnel-->   VPS: nginx -> Card Surveys -> SQLite
Card Surveys --SMTP 465--> Cloudflare Email Service -> researchers' inboxes
daily backup --rclone-->   Cloudflare R2 (off-site copy)
```

Verified on Ubuntu 24.04 LTS (Card Surveys 1.1.3): installation, nginx, HTTPS behind a proxy with secure cookies, account e-mails over SMTP, respondents, export, backup and update. The tunnel, Cloudflare's SMTP endpoint and the R2 copy depend on the Cloudflare account and are checked with the test steps of each section.

## 1. The server

Requirements: Ubuntu 24.04 LTS, 1-2 vCPU, 2-4 GB RAM, 20-40 GB disk, a data center in the European Union. An IPv4 address is convenient for installing packages; with the tunnel the server needs no open web port.

Choose a provider that publishes a data processing agreement (DPA) under the GDPR and lets you pick the data-center country. Examples: OVHcloud (France; a data center in Poland), Hetzner (Germany, Finland), netcup (Germany). Order the server with Ubuntu 24.04 and an SSH key: on Windows create one with `ssh-keygen -t ed25519` in PowerShell and paste the contents of `%USERPROFILE%\.ssh\id_ed25519.pub` into the provider's form.

## 2. First login and basic security

Log in as root (`ssh root@SERVER_IP`), then create your own account and lock the server down:

```sh
adduser marek                                   # your user name; asks for a password used by sudo
usermod -aG sudo marek
mkdir -p /home/marek/.ssh && cp ~/.ssh/authorized_keys /home/marek/.ssh/
chown -R marek:marek /home/marek/.ssh && chmod 700 /home/marek/.ssh

# key-only SSH, no root login (a drop-in read first, ahead of the provider's cloud-init file)
printf 'PasswordAuthentication no\nPermitRootLogin no\n' > /etc/ssh/sshd_config.d/00-hardening.conf
sshd -t && systemctl restart ssh

# firewall: only SSH from outside (the tunnel needs no incoming port)
ufw allow OpenSSH && ufw --force enable

# automatic security updates (on by default on Ubuntu 24.04; this confirms it)
apt update && apt install -y unattended-upgrades && dpkg-reconfigure -f noninteractive unattended-upgrades
timedatectl set-timezone Europe/Warsaw
```

Open a second terminal and check `ssh marek@SERVER_IP` works before closing the root session. From now on use `sudo`.

## 3. Domain and DNS at Cloudflare

1. Register the domain in the Cloudflare dashboard (Domain Registration). Not every country ending is offered; `.com`, `.org`, `.net` and similar are. A domain registered at Cloudflare uses Cloudflare DNS.
2. In the domain's settings, under SSL/TLS, switch on **Always Use HTTPS**.
3. Choose the address of the surveys, for example `ankiety.example.org`. The tunnel (section 5) creates its DNS record.

## 4. Card Surveys

Copy the release ZIP to the server (`scp cardsurveys-1.1.3.zip marek@SERVER_IP:`) and install:

```sh
sudo apt install -y unzip
unzip cardsurveys-1.1.3.zip && cd cardsurveys-1.1.3
sudo ./deploy/install.sh --server-name ankiety.example.org --web nginx --https
sudo rm -f /etc/nginx/sites-enabled/default && sudo systemctl reload nginx
sudo /opt/cardsurveys/deploy/manage.sh create-admin --email you@uj.edu.pl
```

`--https` sets secure cookies and the public address `https://ankiety.example.org`; removing nginx's default site makes every request reach Card Surveys. The installer ends with a smoke test. Locally the site answers at `http://localhost/cards/` (`curl -I -H "Host: ankiety.example.org" http://localhost/` shows a redirect to `/cards/`).

## 5. Cloudflare Tunnel

1. Dashboard: **Networking > Tunnels > Create Tunnel**, give it a name (for example `ankiety`), select **Create Tunnel**.
2. Choose Debian/Ubuntu and the server's architecture (usually 64-bit x86), copy the command under **Install and Run** and run it on the server with `sudo`. It installs `cloudflared` and starts it as a service (`sudo cloudflared service install <TOKEN>`).
3. When the tunnel shows **Healthy**, select **Continue**, then in the tunnel: **Routes > Add route > Published application**. Hostname: `ankiety` on your domain; Service URL: `http://localhost:80`. Select **Add route**; Cloudflare creates the DNS record.
4. Test from any browser: `https://ankiety.example.org/` opens the start page of Card Surveys with a valid certificate, and logging in as the administrator works.

The tunnel is an outgoing connection, so the firewall of section 2 stays closed for the web. `sudo systemctl status cloudflared` shows the connector.

## 6. Account e-mails through Cloudflare

Card Surveys e-mails researchers only (address confirmation and password reset); respondents receive no e-mail. Cloudflare Email Service sends to any recipient on the Workers Paid plan; the service is marked beta, and switching to another SMTP provider later changes only the configuration file.

1. Dashboard: **Compute > Email Service > Email Sending > Onboard Domain**, choose the domain, **Done**. Cloudflare adds the records for bounces, SPF and DKIM on `cf-bounce` and a DMARC record when the domain has none; they are active within 5-15 minutes.
2. Create an API token (My Profile > API Tokens) with the permission **Email Sending: Edit** for the account.
3. On the server, edit or add these lines in `/etc/cardsurveys/cardsurveys.env` (`sudo nano /etc/cardsurveys/cardsurveys.env`):

```
CARDS_MAIL_BACKEND=smtp
CARDS_SMTP_HOST=smtp.mx.cloudflare.net
CARDS_SMTP_PORT=465
CARDS_SMTP_SSL=1
CARDS_SMTP_STARTTLS=0
CARDS_SMTP_USER=api_token
CARDS_SMTP_PASSWORD=<the API token>
CARDS_MAIL_SENDER=Ankiety <no-reply@example.org>
```

then `sudo systemctl restart cardsurveys`. The username is the literal text `api_token`; the token is the password.

4. Test: register an account with your UJ address on the site (or use "forgot password"). The message arrives in the inbox; its headers show `dkim=pass` and `dmarc=pass`. Errors appear in `sudo journalctl -u cardsurveys -n 50`.

Optional, receiving: **Email Routing** (free) forwards mail sent to addresses on the domain, for example `postmaster@example.org`, to an existing inbox.

## 7. Off-site copy of the backups in Cloudflare R2

The server makes a compressed database backup every night at 03:15 and keeps 30 days in `/var/lib/cardsurveys/backups`. A copy outside the server protects against losing the server.

1. Dashboard: **R2 > Create bucket**, name `cardsurveys-backups`, location jurisdiction **European Union**.
2. **R2 > Manage API tokens > Create API token** with Object Read & Write for that bucket; note the Access Key ID, the Secret Access Key and the S3 endpoint `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` (for an EU bucket the endpoint shown with the bucket).
3. On the server:

```sh
sudo apt install -y rclone
sudo rclone config create r2 s3 provider Cloudflare access_key_id <KEY_ID> \
     secret_access_key <SECRET> endpoint <S3_ENDPOINT> acl private no_check_bucket true
sudo rclone copy /var/lib/cardsurveys/backups r2:cardsurveys-backups/daily   # first copy, also a test
sudo rclone ls r2:cardsurveys-backups/daily | head
( sudo crontab -l 2>/dev/null; echo '45 3 * * * rclone copy /var/lib/cardsurveys/backups r2:cardsurveys-backups/daily --max-age 3d --log-file /var/log/cardsurveys-r2.log' ) | sudo crontab -
```

Restore: download a backup (`sudo rclone copy r2:cardsurveys-backups/daily/<file> /tmp/`), then stop the service, decompress the backup over `/var/lib/cardsurveys/cardsurveys.sqlite3` and start the service (`docs/INSTALL.md`, Backups and restore).

## 8. Everyday use

| Task | How |
|---|---|
| Survey links | every survey has its link, `https://ankiety.example.org/cards/s/<code>`; the code cannot be guessed |
| Colleagues | register with an address in an allowed domain (`CARDS_ALLOWED_EMAIL_DOMAINS`) |
| Update | copy the new release ZIP, unzip, `sudo ./deploy/update.sh` (backup, upgrade, restart, smoke test) |
| Logs | `sudo journalctl -u cardsurveys`, `sudo journalctl -u cloudflared` |
| Load test before a large study | `python3 tools/load_test.py https://ankiety.example.org/cards <code> --respondents 100 --concurrency 50` on a test survey |
| Server reboot | the services start by themselves |

## 9. Data protection

The answers are stored on the VPS; Cloudflare carries the traffic and the account e-mails, and R2 holds the backup copy. For a study: conclude the provider's data processing agreement (VPS and Cloudflare), name the processors and the data-center country in the privacy information and the consent text, and agree the arrangement with the data protection officer of the institution. The application stores no network address; Cloudflare sees visitors' addresses as the carrier of the traffic.

## Checklist

| Step | Done when |
|---|---|
| Server | `ssh marek@SERVER_IP` works with the key; `sudo ufw status` shows only OpenSSH |
| Domain | the domain is active in Cloudflare; Always Use HTTPS on |
| Card Surveys | installer smoke test passed; administrator created |
| Tunnel | Healthy; `https://ankiety.example.org/` opens the start page |
| E-mail | a registration e-mail arrives in a UJ inbox with `dkim=pass` |
| Backups | `rclone ls` lists a backup in R2; the cron entry exists |
