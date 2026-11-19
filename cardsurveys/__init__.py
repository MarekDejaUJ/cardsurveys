"""Card Surveys: a web system for card-arrangement surveys.

Copyright (C) 2026 Marek Deja. Licensed under the GNU General Public License,
version 3 or later; see LICENSE.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, g, redirect, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import load_config
from .extensions import csrf, db, migrate

__version__ = "1.3.0"


def create_app(overrides: dict | None = None) -> Flask:
    cfg = load_config(overrides)
    prefix = cfg["URL_PREFIX"]
    app = Flask(__name__, static_url_path=prefix + "/static")
    app.config.update(cfg)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        Path(app.config["SQLALCHEMY_DATABASE_URI"][len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)
    if app.config["BEHIND_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)  # type: ignore[assignment]

    db.init_app(app)
    migrate.init_app(app, db, directory=str(Path(__file__).resolve().parent.parent / "migrations"))
    csrf.init_app(app)

    from . import cli, templating
    from .views import admin, auth, public, researcher

    app.register_blueprint(public.bp, url_prefix=prefix or None)
    app.register_blueprint(auth.bp, url_prefix=(prefix + "/account"))
    app.register_blueprint(researcher.bp, url_prefix=(prefix + "/studio"))
    app.register_blueprint(admin.bp, url_prefix=(prefix + "/admin"))
    templating.init_app(app)
    cli.init_app(app)
    if prefix:
        # the bare address leads to the application when Gunicorn serves it with no web server in front
        app.add_url_rule("/", "root", lambda: redirect(prefix + "/", code=302))

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'",
        )
        if request.path.startswith(prefix + "/studio") or request.path.startswith(prefix + "/admin") or request.path.startswith(prefix + "/r/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    for code in (400, 403, 404, 413, 429):
        app.register_error_handler(code, lambda e, code=code: (render_template("error.html", code=code), code))

    @app.errorhandler(500)
    def server_error(e):  # pragma: no cover - shown only on unexpected failures
        db.session.rollback()
        return render_template("error.html", code=500), 500

    @app.teardown_request
    def _clear(exc):
        g.pop("user", None)

    return app
