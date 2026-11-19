"""Catalog completeness, hidden vocabulary, and the migration matching the models."""
import json
import re
import string
from pathlib import Path

from sqlalchemy import inspect

from cardsurveys.extensions import db

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "cardsurveys"


def catalogs():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (PKG / "catalogs").glob("*.json")}


def test_catalogs_have_the_same_keys_and_placeholders():
    cats = catalogs()
    assert set(cats) >= {"en", "pl"}
    base = cats["en"]
    fmt = string.Formatter()
    for code, cat in cats.items():
        assert set(cat) == set(base), (code, set(base) ^ set(cat))
        for key, text in cat.items():
            assert text.strip(), (code, key)
            names = {f for _, f, _, _ in fmt.parse(text) if f}
            base_names = {f for _, f, _, _ in fmt.parse(base[key]) if f}
            assert names == base_names, (code, key, names, base_names)


def test_every_used_key_exists():
    base = catalogs()["en"]
    used = set()
    pattern = re.compile(r"""\bt\(\s*['"]([a-z_]+\.[A-Za-z0-9_.]+)['"]""")
    for path in list(PKG.rglob("*.html")) + list(PKG.rglob("*.py")):
        used |= set(pattern.findall(path.read_text(encoding="utf-8")))
    used = {k for k in used if not k.endswith((".", "_"))}
    missing = sorted(k for k in used if k not in base)
    assert missing == []


def test_dynamic_keys_exist():
    base = catalogs()["en"]
    from cardsurveys.survey.editor import COMMON, SPECS
    from cardsurveys.survey.schema import MODULE_TYPES, QUESTION_TYPES
    for t in MODULE_TYPES:
        assert f"module.{t}" in base and f"module_help.{t}" in base
    for q in QUESTION_TYPES:
        assert f"qtype.{q}" in base
    for spec in list(SPECS.values()) + [COMMON]:
        for name, kind, _ in spec:
            assert f"field_label.{name}" in base, name
            if kind in ("cards", "blocks", "tiers", "arms", "options_preview", "card", "names"):
                assert f"field_hint.{kind}" in base
    for code in (400, 403, 404, 413, 429, 500):
        assert f"error.{code}.title" in base and f"error.{code}.text" in base
    for s in ("draft", "open", "closed"):
        assert f"status.{s}" in base
    for s in ("started", "submitted", "withdrawn", "declined"):
        assert f"rstatus.{s}" in base
    js = (PKG / "static" / "boards.js").read_text(encoding="utf-8") + (PKG / "static" / "sob.js").read_text(encoding="utf-8") + (PKG / "static" / "tap.js").read_text(encoding="utf-8")
    for key in set(re.findall(r'tr\("([a-z_]+)"', js)):
        assert any(f"{p}.{key}" in base for p in ("board", "sob", "tap")), key


def test_validation_messages_have_texts():
    base = catalogs()["en"]
    src = (PKG / "survey" / "schema.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'_msg\("([a-z_]+)"', src))
    codes |= {"block_" + c for c in re.findall(r'\{"code": "([a-z_]+)"', (PKG / "engine" / "blocks.py").read_text(encoding="utf-8"))}
    for c in codes - {"block_"}:
        assert f"msg.{c}" in base, c


def test_hidden_vocabulary():
    forbidden = [bytes(x).decode() for x in ([101, 105, 100, 101],)]
    for path in PKG.rglob("*"):
        if path.is_file() and path.suffix in (".py", ".html", ".js", ".css", ".json", ".md", ".txt"):
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for word in forbidden:
                assert word not in text, path
    for path in [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), *(ROOT / "deploy").glob("*")]:
        if path.is_file():
            assert forbidden[0] not in path.read_text(encoding="utf-8", errors="replace").lower(), path


def test_polish_interface_uses_diacritics():
    pl = catalogs()["pl"]
    joined = " ".join(pl.values())
    for ch in "ąęłńóśźż":
        assert ch in joined


def test_migration_matches_models(app, tmp_path):
    from flask_migrate import upgrade
    from sqlalchemy import create_engine
    path = tmp_path / "migrated.sqlite3"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + path.as_posix()
    with app.app_context():
        db.engine.dispose()
    from cardsurveys import create_app
    other = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///" + path.as_posix(), "TESTING": True})
    with other.app_context():
        upgrade(directory=other.extensions["migrate"].directory)
    engine = create_engine("sqlite:///" + path.as_posix())
    insp = inspect(engine)
    for table in db.metadata.sorted_tables:
        cols = {c["name"] for c in insp.get_columns(table.name)}
        assert cols == {c.name for c in table.columns}, table.name
    engine.dispose()
