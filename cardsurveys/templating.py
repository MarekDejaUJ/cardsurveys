"""Template helpers shared by every page."""
from __future__ import annotations

import json
from typing import Any

from flask import current_app, request, url_for

from . import i18n
from .security import current_user
from .survey import textfmt


def message_text(m: dict[str, Any], lang: str | None = None) -> str:
    """A validation or engine message in the interface language."""
    args = {k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in m.items() if k != "code"}
    text = i18n.t("msg." + m["code"], lang, **args)
    if text == "msg." + m["code"]:
        text = m["code"] + " " + json.dumps(args, ensure_ascii=False)
    where = args.get("where")
    if where and "{where}" not in i18n.t("msg." + m["code"], lang):
        text = f"{where}: {text}"
    return text


def lang_url(code: str) -> str:
    args = dict(request.view_args or {})
    args.update(request.args.to_dict())
    args["lang"] = code
    return url_for(request.endpoint, **args) if request.endpoint else "?lang=" + code


def public_url(path: str) -> str:
    base = current_app.config["PUBLIC_BASE_URL"]
    return (base + path) if base else (request.host_url.rstrip("/") + path)


def init_app(app):
    from . import __version__

    @app.context_processor
    def inject() -> dict[str, Any]:
        return {
            "app_version": __version__,
            "t": i18n.t,
            "ui_lang": i18n.interface_language(),
            "ui_languages": i18n.registry(),
            "current_user": current_user(),
            "lang_url": lang_url,
            "md": textfmt.render,
            "inline": textfmt.inline,
            "msg": message_text,
            "public_url": public_url,
            "app_prefix": app.config["URL_PREFIX"],
            "ui_strings": ui_strings,
        }

    @app.template_filter("tx")
    def tx(value: Any, lang: str, fallback: str | None = None) -> str:
        return i18n.text_for(value, lang, fallback)


def ui_strings(prefix: str, lang: str) -> dict[str, str]:
    """Interface strings under a key prefix, for the browser widgets."""
    keys = set(i18n._catalog("en")) | set(i18n._catalog(lang))
    return {k[len(prefix):]: i18n.t(k, lang) for k in sorted(keys) if k.startswith(prefix)}
