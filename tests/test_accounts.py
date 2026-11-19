import pytest

from cardsurveys.extensions import db
from cardsurveys.models import User
from cardsurveys.security import email_domain_allowed

from .conftest import link_in, login, mails, make_user


@pytest.mark.parametrize("email,ok", [
    ("jan.kowalski@uj.edu.pl", True),
    ("Jan.Kowalski@UJ.EDU.PL", True),
    ("anna@student.uj.edu.pl", True),
    ("piotr@doctoral.uj.edu.pl", True),
    ("x@cm.uj.edu.pl", False),
    ("x@uj.edu.pl.evil.com", False),
    ("x@fakeuj.edu.pl", False),
    ("x@gmail.com", False),
    ("x@@uj.edu.pl", False),
    ("@uj.edu.pl", False),
    ("x y@uj.edu.pl", False),
])
def test_domain_rule(app, email, ok):
    with app.app_context():
        assert email_domain_allowed(email) is ok


def test_registration_verification_and_login(app, client):
    resp = client.post("/cards/account/register", data={"email": "New.Person@uj.edu.pl", "password": "Long-enough-1", "password2": "Long-enough-1"})
    assert resp.status_code == 200
    sent = mails(app)
    assert len(sent) == 1 and "new.person@uj.edu.pl" in sent[0]
    assert login(client, "new.person@uj.edu.pl", "Long-enough-1").status_code == 200  # not verified yet
    link = link_in(sent[0])
    path = link.split("localhost")[1]
    assert client.get(path).status_code == 200
    assert client.get(path).status_code == 200  # a used link is harmless
    resp = login(client, "new.person@uj.edu.pl", "Long-enough-1")
    assert resp.status_code == 302 and "/cards/studio" in resp.headers["Location"]
    assert client.get("/cards/studio/").status_code == 200


def test_registration_refuses_other_domains_and_weak_passwords(app, client):
    client.post("/cards/account/register", data={"email": "someone@gmail.com", "password": "Long-enough-1", "password2": "Long-enough-1"})
    client.post("/cards/account/register", data={"email": "a@uj.edu.pl", "password": "short1", "password2": "short1"})
    client.post("/cards/account/register", data={"email": "b@uj.edu.pl", "password": "onlyletterslong", "password2": "onlyletterslong"})
    client.post("/cards/account/register", data={"email": "c@uj.edu.pl", "password": "Long-enough-1", "password2": "Long-enough-2"})
    with app.app_context():
        assert User.query.count() == 0
    assert mails(app) == []


def test_existing_address_gets_the_same_answer(app, client):
    make_user(app, "taken@uj.edu.pl")
    resp = client.post("/cards/account/register", data={"email": "taken@uj.edu.pl", "password": "Long-enough-1", "password2": "Long-enough-1"})
    assert resp.status_code == 200 and mails(app) == []


def test_password_reset_is_single_use(app, client):
    make_user(app, "reset@uj.edu.pl", "Old-password-1")
    client.post("/cards/account/forgot", data={"email": "reset@uj.edu.pl"})
    link = link_in(mails(app)[-1])
    path = link.split("localhost")[1]
    assert client.post(path, data={"password": "New-password-2", "password2": "New-password-2"}).status_code == 302
    assert client.post(path, data={"password": "Third-password-3", "password2": "Third-password-3"}).status_code == 400
    assert login(client, "reset@uj.edu.pl", "Old-password-1").status_code == 200
    assert login(client, "reset@uj.edu.pl", "New-password-2").status_code == 302


def test_tampered_token(app, client):
    assert client.get("/cards/account/verify/not-a-token").status_code == 400
    assert client.get("/cards/account/reset/not-a-token").status_code == 400


def test_rate_limit(app, client):
    app.config["RATE_LIMITS"]["login"] = (3, 60)
    for _ in range(3):
        login(client, "nobody@uj.edu.pl", "x")
    assert login(client, "nobody@uj.edu.pl", "x").status_code == 429


def test_roles_and_deactivation(app, client):
    make_user(app, "admin@uj.edu.pl", role="admin")
    uid = make_user(app, "res@uj.edu.pl")
    login(client, "res@uj.edu.pl")
    assert client.get("/cards/admin/").status_code == 403
    other = app.test_client()
    login(other, "admin@uj.edu.pl")
    assert other.get("/cards/admin/").status_code == 200
    assert other.post(f"/cards/admin/users/{uid}", data={"action": "deactivate"}).status_code == 302
    assert client.get("/cards/studio/").status_code == 302  # session ended
    with app.app_context():
        assert not db.session.get(User, uid).active
    assert other.post(f"/cards/admin/users/{uid}", data={"action": "admin"}).status_code == 302
    with app.app_context():
        assert db.session.get(User, uid).is_admin


def test_session_ends_after_password_change(app, client):
    make_user(app, "pw@uj.edu.pl", "First-password-1")
    login(client, "pw@uj.edu.pl", "First-password-1")
    second = app.test_client()
    login(second, "pw@uj.edu.pl", "First-password-1")
    client.post("/cards/account/settings", data={"action": "password", "current": "First-password-1", "password": "Second-password-2", "password2": "Second-password-2"})
    assert client.get("/cards/studio/").status_code == 200
    assert second.get("/cards/studio/").status_code == 302


def test_csrf_is_enforced(app):
    app.config["WTF_CSRF_ENABLED"] = True
    c = app.test_client()
    assert c.post("/cards/account/login", data={"email": "a@uj.edu.pl", "password": "x"}).status_code == 400


def test_create_admin_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-admin", "--email", "boss@uj.edu.pl", "--password", "Admin-pass-2026"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        u = User.query.filter_by(email="boss@uj.edu.pl").one()
        assert u.is_admin and u.verified and u.active
    result = runner.invoke(args=["create-admin", "--email", "boss@uj.edu.pl", "--password", "short"])
    assert result.exit_code != 0


def test_forms_work_over_https_with_csrf_and_the_referrer_policy(tmp_path):
    """Over HTTPS the CSRF check needs a same-origin Referer; the referrer policy lets
    browsers send one within the site and none to other sites."""
    import re as _re

    from cardsurveys import create_app
    from cardsurveys.extensions import db as _db
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "WTF_CSRF_ENABLED": True,
                      "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "csrf.sqlite3").as_posix(),
                      "MAIL_BACKEND": "file", "MAIL_DIR": str(tmp_path / "mail"), "URL_PREFIX": "/cards"})
    with app.app_context():
        _db.create_all()
    client = app.test_client()
    base = "https://ankiety.example.org"
    page = client.get("/cards/account/login", base_url=base)
    assert page.headers["Referrer-Policy"] == "same-origin"
    html = page.get_data(as_text=True)
    assert '<meta name="referrer" content="same-origin">' in html
    token = _re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    data = {"csrf_token": token, "email": "nobody@uj.edu.pl", "password": "x"}
    ok = client.post("/cards/account/login", data=data, base_url=base,
                     headers={"Referer": base + "/cards/account/login"})
    assert ok.status_code == 200  # the form is processed (wrong password, page shown again)
    refused = client.post("/cards/account/login", data=data, base_url=base)
    assert refused.status_code == 400


def _texts(key: str) -> list[str]:
    import json
    from pathlib import Path
    folder = Path(__file__).resolve().parent.parent / "cardsurveys" / "catalogs"
    return [json.loads((folder / f"{lang}.json").read_text(encoding="utf-8"))[key] for lang in ("pl", "en")]


def _has(html: str, key: str, **values) -> bool:
    return any(text.format(**values) in html for text in _texts(key))


def test_registration_without_email_confirmation(app, client):
    app.config["EMAIL_CONFIRMATION"] = False
    page = client.get("/cards/account/register").get_data(as_text=True)
    domains = "uj.edu.pl, @student.uj.edu.pl, @doctoral.uj.edu.pl"
    assert _has(page, "auth.register_lead_direct", domains=domains) and not _has(page, "auth.register_lead", domains=domains)
    assert "/account/resend" not in page
    resp = client.post("/cards/account/register", data={"email": "Quick@uj.edu.pl", "password": "Long-enough-1", "password2": "Long-enough-1"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/cards/account/login")
    assert mails(app) == []
    resp = login(client, "quick@uj.edu.pl", "Long-enough-1")
    assert resp.status_code == 302 and "/cards/studio" in resp.headers["Location"]
    assert client.get("/cards/studio/").status_code == 200
    with app.app_context():
        assert not User.query.filter_by(email="quick@uj.edu.pl").one().verified  # the address stays unconfirmed
    again = app.test_client().post("/cards/account/register", data={"email": "quick@uj.edu.pl", "password": "Other-pass-2", "password2": "Other-pass-2"})
    assert again.status_code == 200 and _has(again.get_data(as_text=True), "auth.account_exists")
    client.post("/cards/account/register", data={"email": "someone@gmail.com", "password": "Long-enough-1", "password2": "Long-enough-1"})
    with app.app_context():
        assert User.query.count() == 1


def test_without_email_confirmation_no_account_mail_is_sent(app, client):
    app.config["EMAIL_CONFIRMATION"] = False
    make_user(app, "known@uj.edu.pl", verified=False)
    forgot = client.get("/cards/account/forgot").get_data(as_text=True)
    assert _has(forgot, "auth.forgot_by_admin") and 'name="email"' not in forgot
    assert client.post("/cards/account/forgot", data={"email": "known@uj.edu.pl"}).status_code == 200
    assert client.get("/cards/account/resend").status_code == 302
    assert mails(app) == []
    assert login(client, "known@uj.edu.pl").status_code == 302  # an unconfirmed address logs in
    assert client.get("/cards/studio/").status_code == 200
    app.config["EMAIL_CONFIRMATION"] = True
    assert client.get("/cards/studio/").status_code == 302  # the open session ends
    assert login(app.test_client(), "known@uj.edu.pl").status_code == 200  # confirmation required again


def test_administrator_sets_a_new_password(app, client):
    admin_id = make_user(app, "admin@uj.edu.pl", role="admin")
    uid = make_user(app, "forgetful@uj.edu.pl", "Old-password-1")
    holder = app.test_client()
    login(holder, "forgetful@uj.edu.pl", "Old-password-1")
    login(client, "admin@uj.edu.pl")
    page = client.post(f"/cards/admin/users/{uid}", data={"action": "password"}).get_data(as_text=True)
    new = page.split("<code>")[1].split("</code>")[0]
    assert len(new) >= 12
    assert holder.get("/cards/studio/").status_code == 302  # the earlier session ends
    assert login(app.test_client(), "forgetful@uj.edu.pl", "Old-password-1").status_code == 200
    assert login(app.test_client(), "forgetful@uj.edu.pl", new).status_code == 302
    assert client.post(f"/cards/admin/users/{admin_id}", data={"action": "password"}).status_code == 302  # refused on oneself
    assert login(app.test_client(), "admin@uj.edu.pl").status_code == 302


def test_bare_address_redirects_to_the_application(client):
    resp = client.get("/")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/cards/")
