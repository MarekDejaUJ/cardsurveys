"""Form fields of the module editor and their conversion to and from module JSON.

Multi-language lists use one line per entry with columns separated by "|": the
code (or value) first, then one column per survey language in the survey's
language order.
"""
from __future__ import annotations

import json
from typing import Any

from ..engine import blocks as B
from ..engine.structures import BOARD_KINDS
from .schema import QUESTION_TYPES

# (name, kind, extra)
SPECS: dict[str, list[tuple[str, str, Any]]] = {
    "consent": [("text", "i18n_area", None), ("agree_label", "i18n_line", None), ("decline_label", "i18n_line", None)],
    "info": [("title", "i18n_line", None), ("text", "i18n_area", None)],
    "form": [("title", "i18n_line", None), ("intro", "i18n_area", None), ("questions", "questions", None),
             ("panel_from", "names", None), ("panel_label", "i18n_line", None), ("shuffle_questions", "names", None),
             ("paradata", "bool", False)],
    "board": [("title", "i18n_line", None), ("instructions", "i18n_area", None), ("relation", "i18n_line", None),
              ("kind", "select", list(BOARD_KINDS)), ("rows", "int", None), ("elements", "cards", None),
              ("confirm_critical", "bool", None), ("randomize_order", "bool", True)],
    "sob_blocks": [("title", "i18n_line", None), ("instructions", "i18n_area", None), ("relation", "i18n_line", None),
                   ("items", "cards", None), ("design", "design", None), ("blocks", "blocks", None), ("side_label", "i18n_line", None),
                   ("shuffle_blocks", "bool", True), ("shuffle_cards", "bool", True)],
    "tap_blocks": [("title", "i18n_line", None), ("instructions", "i18n_area", None), ("criterion", "i18n_area", None),
                   ("items", "cards", None), ("design", "design", None), ("blocks", "blocks", None),
                   ("anchor", "card", None), ("anchor_closes", "bool", False), ("anchor_note", "i18n_area", None),
                   ("gate", "gate", None), ("duplicates", "int", None), ("attention", "int", None),
                   ("attention_label", "i18n_line", None), ("attention_position", "select", ["last", "first"]),
                   ("reference_order", "tiers", None), ("practice", "bool", False),
                   ("panel_from", "names", None), ("panel_label", "i18n_line", None),
                   ("shuffle_blocks", "bool", True), ("shuffle_cards", "bool", True), ("variants_by", "name", None)],
    "randomizer": [("arms", "arms", None), ("strata_by", "names", None), ("block_multiplier", "int", None)],
    "stimulus": [("title", "i18n_line", None), ("prompt", "i18n_area", None), ("arm_of", "name", None), ("stratum_by", "name", None),
                 ("contents", "contents", None)],
    "choice": [("title", "i18n_line", None), ("prompt", "i18n_area", None), ("options", "options_preview", None),
               ("stratum_by", "name", None), ("contents", "contents", None)],
    "debrief": [("title", "i18n_line", None), ("text", "i18n_area", None), ("stratum_by", "name", None),
                ("texts", "stratum_texts", None), ("offer_withdrawal", "bool", True)],
    "thanks": [("title", "i18n_line", None), ("text", "i18n_area", None), ("show_retest_link", "bool", True)],
}
COMMON = [("condition", "json", None), ("retest", "bool", False)]


class EditorError(ValueError):
    def __init__(self, field: str, problem: str, line: int | None = None):
        super().__init__(f"{field}: {problem}")
        self.field, self.problem, self.line = field, problem, line


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").replace("\r\n", "\n").split("\n") if ln.strip() and not ln.strip().startswith("#")]


def _cols(line: str) -> list[str]:
    return [c.strip() for c in line.split("|")]


def i18n_from(form: Any, field: str, languages: list[str]) -> dict[str, str]:
    out = {}
    for code in languages:
        v = (form.get(f"{field}__{code}") or "").strip()
        if v:
            out[code] = v
    return out


def cards_to_text(cards: list[dict[str, Any]], languages: list[str]) -> str:
    return "\n".join(" | ".join([c["code"]] + [c.get("label", {}).get(code, "") for code in languages]) for c in cards or [])


def cards_from_text(text: str, languages: list[str], field: str) -> list[dict[str, Any]]:
    out = []
    for n, line in enumerate(_lines(text), start=1):
        cols = _cols(line)
        if not cols[0]:
            raise EditorError(field, "code_missing", n)
        label = {code: cols[i + 1] for i, code in enumerate(languages) if i + 1 < len(cols) and cols[i + 1]}
        out.append({"code": cols[0], "label": label})
    return out


def options_to_text(options: list[dict[str, Any]], languages: list[str], preview: bool = False) -> str:
    rows = []
    for o in options or []:
        cols = [o["value"]] + [o.get("label", {}).get(code, "") for code in languages]
        if preview:
            cols += [o.get("preview", {}).get(code, "") for code in languages]
        rows.append(" | ".join(cols))
    return "\n".join(rows)


def options_from_text(text: str, languages: list[str], field: str, preview: bool = False) -> list[dict[str, Any]]:
    out = []
    n_lang = len(languages)
    for n, line in enumerate(_lines(text), start=1):
        cols = _cols(line)
        if not cols[0]:
            raise EditorError(field, "value_missing", n)
        opt: dict[str, Any] = {"value": cols[0], "label": {code: cols[i + 1] for i, code in enumerate(languages) if i + 1 < len(cols) and cols[i + 1]}}
        if preview:
            pv = {code: cols[1 + n_lang + i] for i, code in enumerate(languages) if 1 + n_lang + i < len(cols) and cols[1 + n_lang + i]}
            if pv:
                opt["preview"] = pv
        out.append(opt)
    return out


def blocks_to_text(blocks: list[list[str]] | None) -> str:
    return "\n".join(", ".join(b) for b in blocks or [])


def blocks_from_text(text: str) -> list[list[str]]:
    return [[c.strip() for c in line.replace("|", ",").split(",") if c.strip()] for line in _lines(text)]


def to_form(module: dict[str, Any], languages: list[str]) -> dict[str, Any]:
    """Values for the editor form of a module."""
    values: dict[str, Any] = {}
    for name, kind, default in SPECS[module["type"]] + COMMON:
        v = module.get(name, default)
        if kind in ("i18n_line", "i18n_area"):
            for code in languages:
                values[f"{name}__{code}"] = (v or {}).get(code, "")
        elif kind == "cards":
            values[name] = cards_to_text(v or [], languages)
        elif kind == "blocks":
            values[name] = blocks_to_text(v)
        elif kind == "tiers":
            values[name] = blocks_to_text(v)
        elif kind == "card":
            values[name] = cards_to_text([v], languages) if v else ""
        elif kind == "gate":
            g = v or {}
            for code in languages:
                values[f"{name}_question__{code}"] = (g.get("question") or {}).get(code, "")
            values[f"{name}_options"] = options_to_text(g.get("options", []), languages)
        elif kind == "arms":
            values[name] = "\n".join(f"{a['code']} | {a.get('weight', 1)}" for a in v or [])
        elif kind == "names":
            values[name] = ", ".join(v or [])
        elif kind == "options_preview":
            values[name] = options_to_text(v or [], languages, preview=True)
        elif kind == "json":
            values[name] = json.dumps(v, ensure_ascii=False, indent=1) if v else ""
        elif kind == "bool":
            values[name] = bool(v)
        else:
            values[name] = "" if v is None else v
    return values


def from_form(module: dict[str, Any], form: Any, languages: list[str]) -> dict[str, Any]:
    """Apply the editor form to a module (questions, contents and variants are edited separately)."""
    out = {"key": module["key"], "type": module["type"]}
    for extra in ("questions", "contents", "texts", "variants"):
        if extra in module:
            out[extra] = module[extra]
    for name, kind, default in SPECS[module["type"]] + COMMON:
        if kind in ("i18n_line", "i18n_area"):
            v = i18n_from(form, name, languages)
            if v:
                out[name] = v
        elif kind == "cards":
            v = cards_from_text(form.get(name, ""), languages, name)
            if v:
                out[name] = v
        elif kind == "blocks":
            v = blocks_from_text(form.get(name, ""))
            if v:
                out[name] = v
        elif kind == "tiers":
            v = blocks_from_text(form.get(name, ""))
            if v:
                out[name] = v
        elif kind == "design":
            v = (form.get(name) or "").strip()
            if v:
                if v not in B.design_library():
                    raise EditorError(name, "unknown_design")
                out[name] = v
        elif kind == "card":
            cards = cards_from_text(form.get(name, ""), languages, name)
            if cards:
                out[name] = cards[0]
        elif kind == "gate":
            q = i18n_from(form, f"{name}_question", languages)
            opts = options_from_text(form.get(f"{name}_options", ""), languages, name)
            if q or opts:
                out[name] = {"question": q, "options": opts}
        elif kind == "arms":
            arms = []
            for n, line in enumerate(_lines(form.get(name, "")), start=1):
                cols = _cols(line)
                try:
                    weight = int(cols[1]) if len(cols) > 1 and cols[1] else 1
                except ValueError:
                    raise EditorError(name, "weight_not_integer", n)
                arms.append({"code": cols[0], "weight": weight})
            out[name] = arms
        elif kind == "names":
            v = [x.strip() for x in (form.get(name) or "").split(",") if x.strip()]
            if v or module["type"] == "randomizer":
                out[name] = v
        elif kind == "name":
            v = (form.get(name) or "").strip()
            if v:
                out[name] = v
        elif kind == "options_preview":
            out[name] = options_from_text(form.get(name, ""), languages, name, preview=True)
        elif kind == "int":
            v = (form.get(name) or "").strip()
            if v:
                try:
                    out[name] = int(v)
                except ValueError:
                    raise EditorError(name, "not_integer")
        elif kind == "select":
            v = form.get(name)
            if v in default:
                out[name] = v
        elif kind == "bool":
            out[name] = form.get(name) == "on"
        elif kind == "json":
            text = (form.get(name) or "").strip()
            if text:
                try:
                    out[name] = json.loads(text)
                except json.JSONDecodeError:
                    raise EditorError(name, "not_json")
    if module["type"] in ("sob_blocks", "tap_blocks") and out.get("design") and out.get("blocks"):
        out.pop("blocks")
    return out


# ---------------------------------------------------------------- questions of a form module


def question_from_form(form: Any, languages: list[str], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    name = (form.get("name") or "").strip()
    qtype = form.get("qtype")
    if qtype not in QUESTION_TYPES:
        raise EditorError("qtype", "unknown_type")
    q: dict[str, Any] = {"name": name, "type": qtype, "required": form.get("required") == "on",
                         "label": i18n_from(form, "label", languages)}
    help_text = i18n_from(form, "help", languages)
    if help_text:
        q["help"] = help_text
    if qtype in ("select", "radio", "checkbox"):
        q["options"] = options_from_text(form.get("options", ""), languages, "options")
    for bound in ("min", "max"):
        v = (form.get(bound) or "").strip()
        if v and qtype == "number":
            try:
                q[bound] = float(v) if "." in v else int(v)
            except ValueError:
                raise EditorError(bound, "not_a_number")
    cond = (form.get("condition") or "").strip()
    if cond:
        try:
            q["condition"] = json.loads(cond)
        except json.JSONDecodeError:
            raise EditorError("condition", "not_json")
    return q


# ---------------------------------------------------------------- contents of stimulus, choice and debrief


def contents_rows(module: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    if module["type"] == "debrief":
        for stratum, text in (module.get("texts") or {}).items():
            rows.append({"outer": "", "stratum": stratum, "text": text})
        return rows
    for outer, inner in (module.get("contents") or {}).items():
        for stratum, text in inner.items():
            rows.append({"outer": outer, "stratum": stratum, "text": text})
    return rows


def contents_from_form(module: dict[str, Any], form: Any, languages: list[str]) -> dict[str, Any]:
    out = dict(module)
    count = int(form.get("rows", "0") or 0)
    collected: dict[str, dict[str, Any]] = {}
    texts: dict[str, Any] = {}
    for i in range(count + 1):
        if form.get(f"r{i}_delete") == "on":
            continue
        outer = (form.get(f"r{i}_outer") or "").strip() or "*"
        stratum = (form.get(f"r{i}_stratum") or "").strip() or "*"
        text = i18n_from(form, f"r{i}_text", languages)
        if not text:
            continue
        if module["type"] == "debrief":
            texts[stratum] = text
        else:
            collected.setdefault(outer, {})[stratum] = text
    if module["type"] == "debrief":
        if texts:
            out["texts"] = texts
        else:
            out.pop("texts", None)
    else:
        out["contents"] = collected
    return out
