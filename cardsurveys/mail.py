"""Outgoing mail: SMTP in production, console or files in development and tests."""
from __future__ import annotations

import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from flask import current_app


def send(to: str, subject: str, body: str) -> None:
    cfg = current_app.config
    msg = EmailMessage()
    msg["From"] = cfg["MAIL_SENDER"]
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    backend = cfg["MAIL_BACKEND"]
    if backend == "smtp":
        if cfg["SMTP_SSL"]:
            server: smtplib.SMTP = smtplib.SMTP_SSL(cfg["SMTP_HOST"], cfg["SMTP_PORT"], context=ssl.create_default_context(), timeout=20)
        else:
            server = smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=20)
        with server:
            if cfg["SMTP_STARTTLS"] and not cfg["SMTP_SSL"]:
                server.starttls(context=ssl.create_default_context())
            if cfg["SMTP_USER"]:
                server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            server.send_message(msg)
    elif backend == "file":
        folder = Path(cfg["MAIL_DIR"])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{time.time_ns()}.eml").write_bytes(bytes(msg))
    else:
        current_app.logger.info("mail to %s: %s\n%s", to, subject, body)
