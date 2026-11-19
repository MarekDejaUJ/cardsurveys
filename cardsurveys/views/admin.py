"""Administration: accounts and an overview of every survey."""
from __future__ import annotations

import secrets

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from .. import i18n
from ..extensions import db
from ..models import Response, Survey, User, utcnow
from ..security import admin_required, current_user
from .auth import send_verification

bp = Blueprint("admin", __name__)


@bp.route("/")
@admin_required
def users():
    return _users_page()


def _users_page(**extra):
    rows = User.query.order_by(User.created_at.desc()).all()
    survey_counts = {u.id: Survey.query.filter_by(owner_id=u.id).count() for u in rows}
    return render_template("admin/users.html", users=rows, survey_counts=survey_counts,
                           domains=current_app.config["ALLOWED_EMAIL_DOMAINS"], registration_open=current_app.config["REGISTRATION_OPEN"],
                           **extra)


@bp.route("/users/<int:user_id>", methods=("POST",))
@admin_required
def user_action(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    me = current_user()
    action = request.form.get("action")
    if user.id == me.id and action in ("deactivate", "researcher", "delete", "password"):
        flash(i18n.t("admin.not_on_self"), "error")
        return redirect(url_for("admin.users"))
    if action == "activate":
        user.active = True
    elif action == "deactivate":
        user.active = False
        user.session_version += 1
    elif action == "admin":
        user.role = "admin"
    elif action == "researcher":
        user.role = "researcher"
    elif action == "verify":
        user.verified_at = user.verified_at or utcnow()
    elif action == "resend":
        if not user.verified and current_app.config["EMAIL_CONFIRMATION"]:
            send_verification(user)
    elif action == "password":
        # shown once to the administrator, who passes it on; the holder changes it in the account settings
        password = secrets.token_urlsafe(9) + "-" + str(secrets.randbelow(10))
        user.set_password(password)
        db.session.commit()
        return _users_page(new_password={"email": user.email, "password": password})
    elif action == "delete":
        if Survey.query.filter_by(owner_id=user.id).count():
            flash(i18n.t("admin.user_has_surveys"), "error")
            return redirect(url_for("admin.users"))
        db.session.delete(user)
    else:
        abort(400)
    db.session.commit()
    flash(i18n.t("admin.done"), "ok")
    return redirect(url_for("admin.users"))


@bp.route("/surveys")
@admin_required
def surveys():
    rows = Survey.query.order_by(Survey.updated_at.desc()).all()
    counts = {s.id: Response.query.filter_by(survey_id=s.id, preview=False).count() for s in rows}
    return render_template("admin/surveys.html", surveys=rows, counts=counts)


@bp.route("/surveys/<int:survey_id>/owner", methods=("POST",))
@admin_required
def change_owner(survey_id: int):
    survey = db.session.get(Survey, survey_id)
    user = User.query.filter_by(email=(request.form.get("email") or "").strip().lower()).first()
    if survey is None or user is None:
        flash(i18n.t("admin.no_such_account"), "error")
        return redirect(url_for("admin.surveys"))
    survey.owner_id = user.id
    db.session.commit()
    flash(i18n.t("admin.done"), "ok")
    return redirect(url_for("admin.surveys"))
