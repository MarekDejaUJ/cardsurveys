from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cardsurveys import create_app
from cardsurveys.extensions import db
from cardsurveys.models import User, utcnow


@pytest.fixture()
def app(tmp_path: Path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.sqlite3").as_posix(),
        "WTF_CSRF_ENABLED": False,
        "MAIL_BACKEND": "file",
        "MAIL_DIR": str(tmp_path / "mail"),
        "URL_PREFIX": "/cards",
        "RATE_LIMITS": {"login": (1000, 60), "register": (1000, 60), "reset": (1000, 60), "verify_resend": (1000, 60), "respondent_start": (1000, 60)},
    })
    with app.app_context():
        db.create_all()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(app, email="researcher@uj.edu.pl", password="Secret-pass-1", role="researcher", verified=True):
    with app.app_context():
        u = User(email=email, role=role, active=True, verified_at=utcnow() if verified else None)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u.id


def login(client, email="researcher@uj.edu.pl", password="Secret-pass-1"):
    return client.post("/cards/account/login", data={"email": email, "password": password})


def mails(app) -> list[str]:
    folder = Path(app.config["MAIL_DIR"])
    if not folder.exists():
        return []
    return [p.read_text(encoding="utf-8", errors="replace") for p in sorted(folder.glob("*.eml"))]


def link_in(mail_text: str) -> str:
    m = re.search(r"https?://\S+", mail_text.replace("=\n", ""))
    assert m, mail_text
    return m.group(0)


SCREEN = re.compile(r'name="screen" value="([^"]+)"')
CARDS = re.compile(r"data-cards='([^']*)'")
ELEMENTS = re.compile(r"data-elements='([^']*)'")
KIND = re.compile(r'data-kind="([a-z_]+)"')
PAIR = re.compile(r'name="(pair_\d+_\d+)"')
QUESTION_INPUT = re.compile(r'name="([A-Za-z][A-Za-z0-9_]*)" value="([^"]*)"')


def unescape(s: str) -> str:
    return s.replace("&#34;", '"').replace("&#39;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def answer_current(client, uuid: str, choices: dict | None = None, board_mode: str = "chain") -> tuple[str, int]:
    """Answer whatever screen the respondent sees now; returns (screen key, status code)."""
    choices = choices or {}
    page = client.get(f"/cards/r/{uuid}")
    if page.status_code == 302:
        return "redirect:" + page.headers["Location"], 302
    html = page.get_data(as_text=True)
    m = SCREEN.search(html)
    assert m, html[:2000]
    key = m.group(1)
    module, step, occasion = key.split(":")
    data: dict = {"screen": key, "client_ms": "1234"}
    if 'name="decision"' in html:
        data["decision"] = choices.get("decision", "agree")
    elif 'id="board"' in html:
        kind = KIND.search(html).group(1)
        n = len(json.loads(unescape(ELEMENTS.search(html).group(1))))
        if kind in ("tier", "tier_aside"):
            placements = {str(i): min(i, 2) for i in range(n)}
        elif kind == "arrow":
            placements = {"arrows": [[0, 1], [1, 2]] if board_mode == "chain" else []}
        elif kind == "pile":
            placements = {str(i): "p%d" % (i % 2) for i in range(n)}
        elif kind == "plane":
            placements = {str(i): [10 * i + 10, 10 * i + 10] for i in range(n)}
        else:
            placements = {f"{i},{j}": ("a" if j == i + 1 else "apart") for i in range(n) for j in range(i + 1, n)}
        data["placements_json"] = json.dumps(placements)
    elif PAIR.search(html):
        for name in set(PAIR.findall(html)):
            data[name] = choices.get("confirm", "unrelated")
    elif 'id="sobTask"' in html:
        cards = json.loads(unescape(CARDS.search(html).group(1)))
        data["result_json"] = json.dumps({c["code"]: (i if i < len(cards) - 1 else "side") for i, c in enumerate(cards)})
        data["events_json"] = "[]"
        data["block_ms"] = "900"
    elif 'id="tapTask"' in html:
        cards = json.loads(unescape(CARDS.search(html).group(1)))
        order = [c["code"] for c in cards if not c.get("attention")] + [c["code"] for c in cards if c.get("attention")]
        data["result_json"] = json.dumps(order)
        data["events_json"] = json.dumps([[c, 100 * i] for i, c in enumerate(order)])
        data["block_ms"] = "1500"
        if 'name="gate"' in html:
            data["gate"] = choices.get("gate", "yes")
    elif 'name="choice"' in html:
        values = re.findall(r'name="choice" value="([^"]+)"', html)
        data["choice"] = choices.get("choice", values[0])
    else:
        for name in set(re.findall(r'name="([A-Za-z][A-Za-z0-9_]*)"', html)) - {"csrf_token", "screen", "client_ms", "decision"}:
            radio = re.findall(rf'name="{name}" value="([^"]+)"', html)
            select = re.search(rf'<select id="q_{name}" name="{name}">(.*?)</select>', html, re.S)
            if name in choices:
                data[name] = choices[name]
            elif select:
                opts = re.findall(r'<option value="([^"]+)"', select.group(1))
                data[name] = opts[0] if opts else ""
            elif radio:
                data[name] = radio[0]
            else:
                data[name] = "1"
    resp = client.post(f"/cards/r/{uuid}", data=data)
    return key, resp.status_code


def run_to_end(client, uuid: str, choices: dict | None = None, limit: int = 200) -> list[str]:
    keys = []
    for _ in range(limit):
        key, code = answer_current(client, uuid, choices)
        if key.startswith("redirect:"):
            return keys
        assert code in (302, 303), (key, code)
        keys.append(key)
    raise AssertionError("survey did not end")


def start(client, slug: str, lang: str | None = None) -> str:
    url = f"/cards/s/{slug}" + (f"?lang={lang}" if lang else "")
    resp = client.get(url)
    assert resp.status_code == 302, resp.status_code
    return resp.headers["Location"].rstrip("/").split("/r/")[1]
