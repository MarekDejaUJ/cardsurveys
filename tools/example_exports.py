"""Example exports of the demonstration surveys, answered by simulated respondents.

Each demonstration survey (Subjective Order Blocks, tap-order blocks with an anchor,
the arrow board) is imported into a fresh installation with a temporary database.
Simulated respondents hold one of a few declared views and answer every screen
through the respondent interface with some noise; the export of every survey is then
written as a folder. The folders serve as examples of the data format and as test
data for the readers of the analysis packages.

    python tools/example_exports.py --out docs/examples --respondents 40 --seed 20261117
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cardsurveys import create_app  # noqa: E402
from cardsurveys.extensions import db  # noqa: E402
from cardsurveys.models import Survey, User  # noqa: E402
from cardsurveys.seeds import demos  # noqa: E402
from cardsurveys.survey import bundle as bundles  # noqa: E402
from cardsurveys.survey.export import export_files  # noqa: E402

SCREEN = re.compile(r'name="screen" value="([^"]+)"')
CARDS = re.compile(r"data-cards='([^']*)'")
PAIR = re.compile(r'name="(pair_\d+_\d+)"')


def unescape(s: str) -> str:
    return s.replace("&#34;", '"').replace("&#39;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def closure(pairs: set[tuple[str, str]]) -> set[tuple[str, str]]:
    rel = set(pairs)
    changed = True
    while changed:
        changed = False
        for (a, b), (c, d) in itertools.product(list(rel), list(rel)):
            if b == c and (a, d) not in rel:
                rel.add((a, d))
                changed = True
    return rel


def covering(rel: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return {(a, b) for a, b in rel if not any((a, c) in rel and (c, b) in rel for c in {x for p in rel for x in p})}


# ---------------------------------------------------------------- declared views

REVIEW_VIEWS = {
    "sequential": (0.4, closure({("TOPIC", "DB"), ("DB", "QUERY"), ("QUERY", "SCREEN"), ("SCREEN", "READ"),
                                 ("READ", "NOTES"), ("NOTES", "SYNTH")})),
    "parallel": (0.4, closure({("TOPIC", "DB"), ("TOPIC", "QUERY"), ("DB", "SCREEN"), ("QUERY", "SCREEN"),
                               ("SCREEN", "READ"), ("READ", "NOTES"), ("READ", "SYNTH")})),
    "two_tracks": (0.2, closure({("TOPIC", "DB"), ("DB", "QUERY"), ("QUERY", "SCREEN"),
                                 ("TOPIC", "READ"), ("READ", "NOTES"), ("NOTES", "SYNTH")})),
}

SOURCE_PROFILES = {
    "people": (0.5, {"SUP": 2.0, "PEER": 1.2, "LIBN": 1.0, "DBS": 0.8, "BOOK": 0.5, "CHAT": -0.5, "FORUM": -1.0}),
    "digital": (0.5, {"CHAT": 2.0, "DBS": 1.2, "SUP": 0.8, "FORUM": 0.5, "BOOK": 0.3, "PEER": 0.2, "LIBN": -0.8}),
}

PROJECT_VIEWS = {
    "linear": (0.4, closure({("RQ", "LIT"), ("LIT", "METH"), ("METH", "DATA"), ("DATA", "ANAL")})),
    "literature_first": (0.3, closure({("LIT", "RQ"), ("RQ", "METH"), ("METH", "DATA"), ("DATA", "ANAL")})),
    "joint_start": (0.3, closure({("RQ", "METH"), ("LIT", "METH"), ("METH", "DATA"), ("DATA", "ANAL")})),
}


def draw(rng: random.Random, views: dict) -> tuple[str, object]:
    names = list(views)
    name = rng.choices(names, weights=[views[n][0] for n in names])[0]
    return name, views[name][1]


# ---------------------------------------------------------------- respondents


class Respondent:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.review = draw(rng, REVIEW_VIEWS)[1]
        name, profile = draw(rng, SOURCE_PROFILES)
        self.utility = {k: v + rng.gauss(0, 0.5) for k, v in profile.items()}
        self.utility["ANCHOR"] = 0.0
        self.project = draw(rng, PROJECT_VIEWS)[1]
        self.omit_arrow = rng.random() < 0.1

    def sob(self, cards: list[str]) -> dict[str, object]:
        """Levels by the longest chain below each card within the block; cards unrelated to
        every other card of the block go to the side bin; sometimes one card is misplaced."""
        rel = self.review
        out: dict[str, object] = {}
        for c in cards:
            others = [d for d in cards if d != c]
            if not any((c, d) in rel or (d, c) in rel for d in others):
                out[c] = "side"
                continue
            below = [d for d in others if (d, c) in rel]
            depth = 0
            for d in below:
                depth = max(depth, 1 + sum(1 for e in cards if (e, d) in rel))
            out[c] = min(depth, len(cards) - 1)
        if self.rng.random() < 0.1:
            c = self.rng.choice(cards)
            out[c] = self.rng.choice([v for v in [*range(len(cards)), "side"] if v != out[c]])
        return out

    def tap(self, cards: list[str], attention: str | None) -> tuple[list[str], str]:
        """Thurstone-type order: the cards by perceived value (value plus noise in every block)."""
        perceived = {c: self.utility.get(c, self.rng.gauss(0, 1)) + self.rng.gauss(0, 0.6) for c in cards if c != attention}
        order = sorted(perceived, key=perceived.get, reverse=True)
        if attention is not None:
            if self.rng.random() < 0.9:
                order.append(attention)
            else:
                order.insert(self.rng.randrange(len(order)), attention)
        vals = sorted(perceived.values(), reverse=True)
        sure = "yes" if min(a - b for a, b in zip(vals, vals[1:])) > 0.4 else "no"
        return order, sure

    def arrows(self, codes: list[str]) -> list[list[int]]:
        cover = sorted(covering(self.project))
        if self.omit_arrow and cover:
            cover.pop(self.rng.randrange(len(cover)))
        return [[codes.index(a), codes.index(b)] for a, b in cover]


def answer(client, uuid: str, person: Respondent, codes: list[str]) -> str:
    page = client.get(f"/cards/r/{uuid}")
    if page.status_code == 302:
        return "end"
    html = page.get_data(as_text=True)
    key = SCREEN.search(html).group(1)
    data: dict = {"screen": key, "client_ms": str(person.rng.randint(3000, 30000))}
    if 'name="decision"' in html:
        data["decision"] = "agree"
    elif 'id="board"' in html:
        data["placements_json"] = json.dumps({"arrows": person.arrows(codes)})
        data["display_order"] = json.dumps(codes)
    elif PAIR.search(html):
        for name in set(PAIR.findall(html)):
            data[name] = "unrelated"
    elif 'id="sobTask"' in html:
        cards = [c["code"] for c in json.loads(unescape(CARDS.search(html).group(1)))]
        data["result_json"] = json.dumps(person.sob(cards))
        data["events_json"] = "[]"
        data["block_ms"] = str(person.rng.randint(4000, 20000))
    elif 'id="tapTask"' in html:
        cards = json.loads(unescape(CARDS.search(html).group(1)))
        att = next((c["code"] for c in cards if c.get("attention")), None)
        order, sure = person.tap([c["code"] for c in cards], att)
        data["result_json"] = json.dumps(order)
        data["events_json"] = json.dumps([[c, 700 * (i + 1)] for i, c in enumerate(order)])
        data["block_ms"] = str(700 * (len(order) + 1))
        if 'name="gate"' in html:
            data["gate"] = sure
    resp = client.post(f"/cards/r/{uuid}", data=data)
    if resp.status_code not in (302, 303):
        raise RuntimeError(f"screen {key} returned {resp.status_code}")
    return key


def make_app(tmp: Path):
    return create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp / "examples.sqlite3").as_posix(),
                       "TESTING": True, "WTF_CSRF_ENABLED": False, "SECRET_KEY": "examples",
                       "MAIL_BACKEND": "file", "MAIL_DIR": str(tmp / "mail"), "URL_PREFIX": "/cards",
                       "RATE_LIMITS": {k: (100000, 60) for k in ("login", "register", "reset",
                                                                  "verify_resend", "respondent_start")}})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "examples"))
    ap.add_argument("--respondents", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261117)
    args = ap.parse_args()
    surveys = {"sob": demos.sob_demo(), "tap": demos.tap_demo(), "arrow": demos.board_demo("arrow")}
    tmp = Path(tempfile.mkdtemp())
    app = make_app(tmp)
    with app.app_context():
        db.create_all()
        user = User(email="examples@uj.edu.pl", role="admin", verified_at=datetime.now(timezone.utc))
        user.set_password("Examples-pass-1")
        db.session.add(user)
        db.session.commit()
        made = {}
        for name, bundle in surveys.items():
            s = bundles.create_from_bundle(user, bundle, ["pl", "en"])
            s.status = "open"
            db.session.commit()
            board = next((m for m in bundle["modules"] if m["type"] == "board"), None)
            made[name] = (s.slug, s.id, [e["code"] for e in board["elements"]] if board else [])
    rng = random.Random(args.seed)
    for name, (slug, sid, codes) in made.items():
        for _ in range(args.respondents):
            client = app.test_client()
            lang = rng.choice(["pl", "en"])
            start = client.get(f"/cards/s/{slug}?lang={lang}")
            uuid = start.headers["Location"].rstrip("/").split("/r/")[1]
            person = Respondent(rng)
            for _ in range(200):
                if answer(client, uuid, person, codes) == "end":
                    break
        out = Path(args.out) / name
        with app.app_context():
            files = export_files(db.session.get(Survey, sid))
        for fname, content in files.items():
            target = out / fname
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="")
        print(f"{name}: {args.respondents} respondents, {len(files)} files in {out}")


if __name__ == "__main__":
    main()
