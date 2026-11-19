"""Accounts: e-mail domain rule, tokens, rate limits, the signed-in user."""
from __future__ import annotations

import functools
import hashlib
from datetime import timedelta

from flask import abort, current_app, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .extensions import db
from .models import RateEvent, User, utcnow


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def email_domain_allowed(email: str) -> bool:
    """True when the address belongs exactly to one of the allowed domains."""
    email = normalize_email(email)
    if email.count("@") != 1:
        return False
    local, domain = email.split("@")
    if not local or not domain or " " in email:
        return False
    return domain in current_app.config["ALLOWED_EMAIL_DOMAINS"]


def password_problems(password: str) -> list[str]:
    problems = []
    if len(password or "") < current_app.config["PASSWORD_MIN_LENGTH"]:
        problems.append("password_too_short")
    if password and (password.isdigit() or password.isalpha()):
        problems.append("password_too_simple")
    return problems


# ---------------------------------------------------------------- tokens


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def _fingerprint(user: User) -> str:
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def make_token(user: User, purpose: str) -> str:
    return _serializer(purpose).dumps({"uid": user.id, "fp": _fingerprint(user), "v": int(user.verified)})


def read_token(token: str, purpose: str, hours: float) -> User | None:
    try:
        data = _serializer(purpose).loads(token, max_age=int(hours * 3600))
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data.get("uid"))
    if user is None or data.get("fp") != _fingerprint(user):
        return None
    if purpose == "verify" and user.verified:
        return user
    return user


# ---------------------------------------------------------------- rate limits


def rate_limited(name: str, key: str) -> bool:
    """Record an event and report whether the limit for (name, key) is exceeded."""
    limit, window = current_app.config["RATE_LIMITS"][name]
    full_key = f"{name}:{hashlib.sha256(key.encode()).hexdigest()[:32]}"
    since = utcnow() - timedelta(seconds=window)
    RateEvent.query.filter(RateEvent.created_at < utcnow() - timedelta(days=1)).delete()
    count = RateEvent.query.filter(RateEvent.key == full_key, RateEvent.created_at >= since).count()
    if count >= limit:
        return True
    db.session.add(RateEvent(key=full_key))
    db.session.commit()
    return False


# ---------------------------------------------------------------- signed-in user


def current_user() -> User | None:
    if "user" in g:
        return g.user
    user = None
    uid = session.get("uid")
    if uid:
        user = db.session.get(User, uid)
        unconfirmed = not user.verified and current_app.config["EMAIL_CONFIRMATION"] if user is not None else False
        if user is None or not user.active or unconfirmed or session.get("sv") != user.session_version:
            session.pop("uid", None)
            user = None
    g.user = user
    return user


def login(user: User) -> None:
    lang = session.get("ui_lang")
    session.clear()
    if user.ui_language or lang:
        session["ui_lang"] = user.ui_language or lang
    session.permanent = True
    session["uid"] = user.id
    session["sv"] = user.session_version
    user.last_login_at = utcnow()
    g.user = user


def logout() -> None:
    session.pop("uid", None)
    session.pop("sv", None)
    g.user = None


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("auth.login", next=request.full_path))
        if not user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
