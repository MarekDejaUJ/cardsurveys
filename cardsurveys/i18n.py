"""Languages of the interface and of survey content.

The interface reads its strings from one catalog per language
(``catalogs/<code>.json``). Survey content stores every translatable text as a
map from language code to text, so a survey can declare any set of languages
from the registry. Adding a language means adding a catalog and listing the
language in ``CARDS_LANGUAGES``.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import current_app, g, has_request_context, request, session

CATALOG_DIR = Path(__file__).resolve().parent / "catalogs"

# Native names of languages the registry may list.
NATIVE_NAMES = {
    "pl": "Polski",
    "en": "English",
    "de": "Deutsch",
    "uk": "Українська",
    "fr": "Français",
    "es": "Español",
    "cs": "Čeština",
    "sk": "Slovenčina",
}


def registry() -> list[dict[str, Any]]:
    """Languages enabled in this installation, in configured order."""
    codes = current_app.config["LANGUAGES"]
    return [{"code": c, "name": NATIVE_NAMES.get(c, c), "interface": (CATALOG_DIR / f"{c}.json").exists()} for c in codes]


def language_codes() -> list[str]:
    return list(current_app.config["LANGUAGES"])


def interface_languages() -> list[str]:
    return [lang["code"] for lang in registry() if lang["interface"]]


@lru_cache(maxsize=None)
def _catalog(code: str) -> dict[str, str]:
    path = CATALOG_DIR / f"{code}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def reload_catalogs() -> None:
    _catalog.cache_clear()


def interface_language() -> str:
    """Language of the interface for the current request."""
    if not has_request_context():
        return current_app.config["DEFAULT_LANGUAGE"]
    if getattr(g, "ui_lang", None):
        return g.ui_lang
    langs = interface_languages()
    asked = request.args.get("lang")
    if asked in langs:
        session["ui_lang"] = asked
        return asked
    stored = session.get("ui_lang")
    if stored in langs:
        return stored
    best = request.accept_languages.best_match(langs) if request.accept_languages else None
    return best or current_app.config["DEFAULT_LANGUAGE"]


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Interface string for a key, in the given or current language, with fallbacks."""
    lang = lang or interface_language()
    text = _catalog(lang).get(key)
    if text is None:
        text = _catalog(current_app.config["DEFAULT_LANGUAGE"]).get(key)
    if text is None:
        text = _catalog("en").get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def text_for(value: Any, lang: str, fallback: str | None = None) -> str:
    """Text of a translatable value in a language, falling back to the default and then to any text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return str(value)
    for code in (lang, fallback):
        if code and value.get(code):
            return value[code]
    for text in value.values():
        if text:
            return text
    return ""


def missing_languages(value: Any, languages: list[str]) -> list[str]:
    if value is None:
        return list(languages)
    if isinstance(value, str):
        return [] if value else list(languages)
    return [code for code in languages if not (isinstance(value, dict) and value.get(code))]


def all_catalog_keys() -> dict[str, set[str]]:
    return {path.stem: set(json.loads(path.read_text(encoding="utf-8"))) for path in CATALOG_DIR.glob("*.json")}
