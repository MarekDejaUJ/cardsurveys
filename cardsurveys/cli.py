"""Command-line tools: ``flask --app cardsurveys <command>``."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_migrate import upgrade

from .extensions import db
from .models import Survey, User, utcnow
from .security import email_domain_allowed, normalize_email, password_problems
from .survey import bundle as bundles
from .survey.export import export_files


def init_app(app):
    app.cli.add_command(init_db)
    app.cli.add_command(create_admin)
    app.cli.add_command(seed_demos)
    app.cli.add_command(import_survey)
    app.cli.add_command(export_survey)
    app.cli.add_command(export_data)
    app.cli.add_command(list_surveys)
    app.cli.add_command(list_users)


@click.command("init-db")
@with_appcontext
def init_db():
    """Create or upgrade the database to the current schema."""
    upgrade(directory=current_app.extensions["migrate"].directory)
    click.echo("database ready")


@click.command("create-admin")
@with_appcontext
@click.option("--email", required=True)
@click.option("--password", default=None, help="Asked interactively when omitted.")
def create_admin(email, password):
    """Create an administrator account (or make an existing account an administrator)."""
    email = normalize_email(email)
    if not email_domain_allowed(email):
        click.echo("warning: the address is outside the allowed domains; the account is created anyway", err=True)
    user = User.query.filter_by(email=email).first()
    if password is None:
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    problems = password_problems(password)
    if problems:
        raise click.ClickException("password rejected: " + ", ".join(problems))
    if user is None:
        user = User(email=email, role="admin", active=True, verified_at=utcnow())
        user.set_password(password)
        db.session.add(user)
    else:
        user.role, user.active = "admin", True
        user.verified_at = user.verified_at or utcnow()
        user.set_password(password)
    db.session.commit()
    click.echo(f"administrator {email} ready")


def _owner(email: str | None) -> User:
    if email:
        user = User.query.filter_by(email=normalize_email(email)).first()
    else:
        user = User.query.filter_by(role="admin").order_by(User.id).first()
    if user is None:
        raise click.ClickException("no such account (create an administrator first)")
    return user


@click.command("seed-demos")
@with_appcontext
@click.option("--owner", default=None, help="E-mail of the owner; the first administrator by default.")
@click.option("--publish/--draft", default=True)
def seed_demos(owner, publish):
    """Create the demonstration surveys (one per technique and the experiment example)."""
    from .seeds.demos import all_demos

    user = _owner(owner)
    for name, bundle in all_demos():
        survey = bundles.create_from_bundle(user, bundle, current_app.config["LANGUAGES"], is_demo=True)
        if publish:
            survey.status, survey.published_at = "open", utcnow()
        click.echo(f"{name}: /s/{survey.slug}")
    db.session.commit()


@click.command("import-survey")
@with_appcontext
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--owner", default=None, help="E-mail of the owner; the first administrator by default.")
@click.option("--keep-slug", is_flag=True, help="Keep the link stored in the bundle when it is free.")
@click.option("--publish", is_flag=True)
def import_survey(path, owner, keep_slug, publish):
    """Import a survey bundle (JSON) as a new survey."""
    user = _owner(owner)
    data = bundles.parse_bundle_text(Path(path).read_text(encoding="utf-8"))
    try:
        survey = bundles.create_from_bundle(user, data, current_app.config["LANGUAGES"], keep_slug=keep_slug)
    except bundles.BundleError as exc:
        for m in exc.messages:
            click.echo(json.dumps(m, ensure_ascii=False), err=True)
        raise click.ClickException("bundle rejected")
    if publish:
        from .survey.schema import blocking_for_publish, validate_bundle

        blocking = blocking_for_publish(validate_bundle(survey.definition, current_app.config["LANGUAGES"]))
        if blocking:
            for m in blocking:
                click.echo(json.dumps(m, ensure_ascii=False), err=True)
            raise click.ClickException("imported as a draft: publishing needs the messages above resolved")
        survey.status, survey.published_at = "open", utcnow()
    db.session.commit()
    click.echo(f"survey {survey.id}: /s/{survey.slug} ({survey.status})")


@click.command("export-survey")
@with_appcontext
@click.argument("survey_id", type=int)
@click.argument("path", type=click.Path(dir_okay=False))
def export_survey(survey_id, path):
    """Write the bundle of a survey to a JSON file."""
    survey = db.session.get(Survey, survey_id) or sys.exit("no such survey")
    Path(path).write_text(json.dumps(bundles.export_bundle(survey), ensure_ascii=False, indent=2), encoding="utf-8")
    click.echo(path)


@click.command("export-data")
@with_appcontext
@click.argument("survey_id", type=int)
@click.argument("folder", type=click.Path(file_okay=False))
def export_data(survey_id, folder):
    """Write every data file of a survey into a folder."""
    survey = db.session.get(Survey, survey_id) or sys.exit("no such survey")
    for name, text in export_files(survey).items():
        target = Path(folder) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    click.echo(folder)


@click.command("list-surveys")
@with_appcontext
def list_surveys():
    for s in Survey.query.order_by(Survey.id).all():
        title = s.settings.get("title", {})
        click.echo(f"{s.id}\t{s.status}\t/s/{s.slug}\t{s.owner.email}\t{title.get('en') or next(iter(title.values()), '')}")


@click.command("list-users")
@with_appcontext
def list_users():
    for u in User.query.order_by(User.id).all():
        click.echo(f"{u.id}\t{u.email}\t{u.role}\t{'active' if u.active else 'inactive'}\t{'verified' if u.verified else 'unverified'}")
