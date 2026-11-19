"""Researcher accounts."""
from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .. import i18n, mail
from ..extensions import db
from ..models import User, utcnow
from ..security import (current_user, email_domain_allowed, login, login_required, logout, make_token, normalize_email,
                        password_problems, rate_limited, read_token)
from ..templating import public_url

bp = Blueprint("auth", __name__)


def _safe_next(target: str | None) -> str:
    if target and target.startswith("/") and not target.startswith("//") and not urlparse(target).netloc:
        return target
    return url_for("researcher.dashboard")


def send_verification(user: User) -> None:
    lang = user.ui_language or i18n.interface_language()
    link = public_url(url_for("auth.verify", token=make_token(user, "verify")))
    mail.send(user.email, i18n.t("mail.verify_subject", lang), i18n.t("mail.verify_body", lang, link=link,
                                                                       hours=current_app.config["VERIFY_TOKEN_HOURS"]))


def send_reset(user: User) -> None:
    lang = user.ui_language or i18n.interface_language()
    link = public_url(url_for("auth.reset", token=make_token(user, "reset")))
    mail.send(user.email, i18n.t("mail.reset_subject", lang), i18n.t("mail.reset_body", lang, link=link,
                                                                     hours=current_app.config["RESET_TOKEN_HOURS"]))


@bp.route("/register", methods=("GET", "POST"))
def register():
    if not current_app.config["REGISTRATION_OPEN"]:
        return render_template("auth/register.html", closed=True)
    errors: list[str] = []
    email = ""
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        password = request.form.get("password", "")
        if rate_limited("register", "global"):
            abort(429)
        if not email_domain_allowed(email):
            errors.append("auth.domain_not_allowed")
        if password != request.form.get("password2", ""):
            errors.append("auth.passwords_differ")
        errors += ["auth." + p for p in password_problems(password)]
        if not errors and not current_app.config["EMAIL_CONFIRMATION"]:
            if User.query.filter_by(email=email).first() is not None:
                errors.append("auth.account_exists")
            else:
                user = User(email=email, role="researcher", active=True, ui_language=i18n.interface_language())
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash(i18n.t("auth.account_ready"), "ok")
                return redirect(url_for("auth.login"))
        elif not errors:
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User(email=email, role="researcher", active=True, ui_language=i18n.interface_language())
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                send_verification(user)
            elif not user.verified:
                send_verification(user)
            # the same answer whether or not the address already has an account
            return render_template("auth/check_mail.html", email=email)
    return render_template("auth/register.html", errors=errors, email=email,
                           domains=current_app.config["ALLOWED_EMAIL_DOMAINS"])


@bp.route("/verify/<token>")
def verify(token: str):
    user = read_token(token, "verify", current_app.config["VERIFY_TOKEN_HOURS"])
    if user is None:
        return render_template("auth/verify.html", ok=False), 400
    if not user.verified:
        user.verified_at = utcnow()
        db.session.commit()
    return render_template("auth/verify.html", ok=True)


@bp.route("/resend", methods=("GET", "POST"))
def resend():
    if not current_app.config["EMAIL_CONFIRMATION"]:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        if rate_limited("verify_resend", email or "-"):
            abort(429)
        user = User.query.filter_by(email=email).first()
        if user is not None and not user.verified and user.active:
            send_verification(user)
        return render_template("auth/check_mail.html", email=email)
    return render_template("auth/resend.html")


@bp.route("/login", methods=("GET", "POST"), endpoint="login")
def login_view():
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        if rate_limited("login", email or "-"):
            abort(429)
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(request.form.get("password", "")):
            flash(i18n.t("auth.bad_login"), "error")
        elif not user.active:
            flash(i18n.t("auth.inactive"), "error")
        elif not user.verified and current_app.config["EMAIL_CONFIRMATION"]:
            flash(i18n.t("auth.not_verified"), "error")
        else:
            login(user)
            db.session.commit()
            return redirect(_safe_next(request.args.get("next")))
    return render_template("auth/login.html")


@bp.route("/logout", methods=("POST",), endpoint="logout")
def logout_view():
    logout()
    return redirect(url_for("public.index"))


@bp.route("/forgot", methods=("GET", "POST"))
def forgot():
    if not current_app.config["EMAIL_CONFIRMATION"]:
        return render_template("auth/forgot.html", by_admin=True)
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        if rate_limited("reset", email or "-"):
            abort(429)
        user = User.query.filter_by(email=email).first()
        if user is not None and user.active and user.verified:
            send_reset(user)
        return render_template("auth/check_mail.html", email=email, reset=True)
    return render_template("auth/forgot.html")


@bp.route("/reset/<token>", methods=("GET", "POST"))
def reset(token: str):
    user = read_token(token, "reset", current_app.config["RESET_TOKEN_HOURS"])
    if user is None or not user.active:
        return render_template("auth/reset.html", invalid=True), 400
    errors: list[str] = []
    if request.method == "POST":
        password = request.form.get("password", "")
        if password != request.form.get("password2", ""):
            errors.append("auth.passwords_differ")
        errors += ["auth." + p for p in password_problems(password)]
        if not errors:
            user.set_password(password)
            db.session.commit()
            flash(i18n.t("auth.password_changed"), "ok")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", invalid=False, errors=errors)


@bp.route("/settings", methods=("GET", "POST"))
@login_required
def settings():
    user = current_user()
    errors: list[str] = []
    if request.method == "POST":
        action = request.form.get("action")
        if action == "language":
            code = request.form.get("ui_language")
            if code in i18n.interface_languages():
                user.ui_language = code
                db.session.commit()
                return redirect(url_for("auth.settings", lang=code))
        elif action == "password":
            if not user.check_password(request.form.get("current", "")):
                errors.append("auth.bad_current_password")
            new = request.form.get("password", "")
            if new != request.form.get("password2", ""):
                errors.append("auth.passwords_differ")
            errors += ["auth." + p for p in password_problems(new)]
            if not errors:
                user.set_password(new)
                db.session.commit()
                login(user)
                db.session.commit()
                flash(i18n.t("auth.password_changed"), "ok")
                return redirect(url_for("auth.settings"))
    return render_template("auth/settings.html", errors=errors)
