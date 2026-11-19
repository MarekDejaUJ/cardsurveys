"""Settings read from environment variables (prefix CARDS_)."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str) -> list[str]:
    return [x.strip().lower() for x in os.environ.get(name, default).split(",") if x.strip()]


def _prefix(value: str) -> str:
    value = value.strip()
    if not value or value == "/":
        return ""
    return "/" + value.strip("/")


def load_config(overrides: dict | None = None) -> dict:
    base = Path(os.environ.get("CARDS_HOME", Path.cwd()))
    db_path = base / "appdata" / "cardsurveys.sqlite3"
    cfg = {
        "SECRET_KEY": os.environ.get("CARDS_SECRET_KEY", "dev-change-me"),
        "SQLALCHEMY_DATABASE_URI": os.environ.get("CARDS_DATABASE_URL", "sqlite:///" + db_path.as_posix()),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "URL_PREFIX": _prefix(os.environ.get("CARDS_URL_PREFIX", "/cards")),
        "PUBLIC_BASE_URL": os.environ.get("CARDS_PUBLIC_BASE_URL", "").rstrip("/"),
        "SESSION_COOKIE_SECURE": _bool("CARDS_SECURE_COOKIES", False),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_NAME": "cards_session",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=float(os.environ.get("CARDS_SESSION_HOURS", "8"))),
        "BEHIND_PROXY": _bool("CARDS_BEHIND_PROXY", False),
        "LANGUAGES": _list("CARDS_LANGUAGES", "pl,en"),
        "DEFAULT_LANGUAGE": os.environ.get("CARDS_DEFAULT_LANGUAGE", "pl").strip().lower(),
        "ALLOWED_EMAIL_DOMAINS": _list("CARDS_ALLOWED_EMAIL_DOMAINS", "uj.edu.pl,student.uj.edu.pl,doctoral.uj.edu.pl"),
        "REGISTRATION_OPEN": _bool("CARDS_REGISTRATION_OPEN", True),
        # off: an account works right after registration and the application sends no account e-mail
        "EMAIL_CONFIRMATION": _bool("CARDS_EMAIL_CONFIRMATION", True),
        "MAIL_BACKEND": os.environ.get("CARDS_MAIL_BACKEND", "console").strip().lower(),
        "SMTP_HOST": os.environ.get("CARDS_SMTP_HOST", "localhost"),
        "SMTP_PORT": int(os.environ.get("CARDS_SMTP_PORT", "25")),
        "SMTP_STARTTLS": _bool("CARDS_SMTP_STARTTLS", False),
        "SMTP_SSL": _bool("CARDS_SMTP_SSL", False),
        "SMTP_USER": os.environ.get("CARDS_SMTP_USER", ""),
        "SMTP_PASSWORD": os.environ.get("CARDS_SMTP_PASSWORD", ""),
        "MAIL_SENDER": os.environ.get("CARDS_MAIL_SENDER", "Card Surveys <no-reply@localhost>"),
        "MAIL_DIR": os.environ.get("CARDS_MAIL_DIR", str(base / "appdata" / "mail")),
        "VERIFY_TOKEN_HOURS": 48,
        "RESET_TOKEN_HOURS": 1,
        "MAX_CONTENT_LENGTH": 4 * 1024 * 1024,
        "WTF_CSRF_TIME_LIMIT": None,
        "PASSWORD_MIN_LENGTH": 10,
        "RATE_LIMITS": {
            "login": (10, 15 * 60),
            "register": (5, 60 * 60),
            "reset": (5, 60 * 60),
            "verify_resend": (5, 60 * 60),
            "respondent_start": (120, 60),
        },
    }
    if overrides:
        cfg.update(overrides)
    return cfg
