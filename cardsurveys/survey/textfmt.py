"""Light markup for survey texts.

Researchers write plain text: a blank line starts a new paragraph, a line that
starts with "- " is a list item, **double asterisks** mark bold text, *single
asterisks* mark italics, and web addresses become links. Everything else is
escaped, so survey texts cannot inject markup into a page.
"""
from __future__ import annotations

import re

from markupsafe import Markup, escape

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITAL = re.compile(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])")
_URL = re.compile(r"(https?://[^\s<>\"']+[^\s<>\"'.,;:)\]])")


def _inline(text: str) -> str:
    s = str(escape(text))
    s = _URL.sub(lambda m: '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (m.group(1), m.group(1)), s)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _ITAL.sub(r"<em>\1</em>", s)
    return s


def render(text: str | None) -> Markup:
    if not text:
        return Markup("")
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    out = []
    for block in blocks:
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if lines and all(ln.lstrip().startswith("- ") for ln in lines):
            items = "".join("<li>%s</li>" % _inline(ln.lstrip()[2:]) for ln in lines)
            out.append("<ul>%s</ul>" % items)
        else:
            out.append("<p>%s</p>" % "<br>".join(_inline(ln) for ln in lines))
    return Markup("\n".join(out))
