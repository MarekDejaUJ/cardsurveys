"""The survey bundle: a versioned JSON document holding a whole survey.

``validate_bundle`` returns errors (the bundle cannot be stored) and warnings
(the bundle can be stored as a draft but cannot be published, for example a
missing translation). Every message is a code with arguments, so the interface
can phrase it in any language.
"""
from __future__ import annotations

import copy
from typing import Any

from jsonschema import Draft202012Validator

from ..engine import blocks as B
from ..engine.structures import BOARD_KINDS, MAX_CARDS

BUNDLE_FORMAT = "cardsurveys-bundle"
BUNDLE_VERSION = 1

MODULE_TYPES = ("consent", "info", "form", "board", "sob_blocks", "tap_blocks", "randomizer",
                "stimulus", "choice", "debrief", "thanks")
QUESTION_TYPES = ("text", "textarea", "number", "select", "radio", "checkbox", "yesno")
CONDITION_OPS = ("eq", "ne", "in", "not_in", "answered", "empty")

_I18N = {"type": "object", "patternProperties": {"^[a-z]{2,3}(-[A-Za-z0-9]+)?$": {"type": "string"}}, "additionalProperties": False}
_CODE = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"}
_KEY = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"}
_CARD = {"type": "object", "required": ["code", "label"], "properties": {"code": _CODE, "label": _I18N, "note": {"type": "string"}}, "additionalProperties": False}
_OPTION = {"type": "object", "required": ["value", "label"], "properties": {"value": {"type": "string", "minLength": 1, "maxLength": 64}, "label": _I18N, "preview": _I18N}, "additionalProperties": False}
_BLOCKS = {"type": "array", "items": {"type": "array", "items": _CODE, "minItems": 2}}
_CONDITION: dict[str, Any] = {"type": "object"}  # checked structurally in _check_condition

_COMMON = {"key": _KEY, "type": {"enum": list(MODULE_TYPES)}, "title": _I18N, "condition": _CONDITION, "retest": {"type": "boolean"}}


def _module(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    p = dict(_COMMON)
    p.update(props)
    return {"type": "object", "required": ["key", "type"] + required, "properties": p, "additionalProperties": False}


_QUESTION = {
    "type": "object",
    "required": ["name", "type", "label"],
    "properties": {
        "name": _KEY, "type": {"enum": list(QUESTION_TYPES)}, "required": {"type": "boolean"},
        "label": _I18N, "help": _I18N, "options": {"type": "array", "items": _OPTION},
        "min": {"type": "number"}, "max": {"type": "number"}, "condition": _CONDITION,
    },
    "additionalProperties": False,
}

_BLOCK_SOURCE = {"design": {"type": "string"}, "blocks": _BLOCKS}

_VARIANT = {
    "type": "object", "required": ["items"],
    "properties": {"items": {"type": "array", "items": _CARD, "minItems": 2}, "design": {"type": "string"}, "blocks": _BLOCKS,
                   "reference_order": {"type": "array", "items": {"type": "array", "items": _CODE}}, "criterion": _I18N},
    "additionalProperties": False,
}

MODULE_SCHEMAS = {
    "consent": _module({"text": _I18N, "agree_label": _I18N, "decline_label": _I18N}, ["text"]),
    "info": _module({"text": _I18N}, ["text"]),
    "form": _module({"intro": _I18N, "questions": {"type": "array", "items": _QUESTION, "minItems": 1}}, ["questions"]),
    "board": _module({
        "instructions": _I18N, "relation": _I18N, "kind": {"enum": list(BOARD_KINDS)},
        "rows": {"type": "integer", "minimum": 2, "maximum": 8},
        "elements": {"type": "array", "items": _CARD, "minItems": 2, "maxItems": MAX_CARDS},
        "confirm_critical": {"type": "boolean"}, "randomize_order": {"type": "boolean"},
    }, ["relation", "kind", "elements"]),
    "sob_blocks": _module({
        "instructions": _I18N, "relation": _I18N, "items": {"type": "array", "items": _CARD, "minItems": 3},
        **_BLOCK_SOURCE, "side_label": _I18N, "shuffle_blocks": {"type": "boolean"}, "shuffle_cards": {"type": "boolean"},
    }, ["relation", "items"]),
    "tap_blocks": _module({
        "instructions": _I18N, "criterion": _I18N, "items": {"type": "array", "items": _CARD},
        **_BLOCK_SOURCE,
        "anchor": _CARD,
        "gate": {"type": "object", "required": ["question", "options"], "properties": {"question": _I18N, "options": {"type": "array", "items": _OPTION, "minItems": 2}}, "additionalProperties": False},
        "duplicates": {"type": "integer", "minimum": 0, "maximum": 6},
        "attention": {"type": "integer", "minimum": 0, "maximum": 4},
        "attention_label": _I18N,
        "shuffle_blocks": {"type": "boolean"}, "shuffle_cards": {"type": "boolean"},
        "practice": {"type": "boolean"},
        "reference_order": {"type": "array", "items": {"type": "array", "items": _CODE}},
        "panel_from": {"type": "array", "items": _KEY, "maxItems": 4},
        "panel_label": _I18N,
        "variants_by": _KEY,
        "variants": {"type": "object", "patternProperties": {"^.{1,64}$": _VARIANT}, "additionalProperties": False},
    }, ["criterion"]),
    "randomizer": _module({
        "arms": {"type": "array", "minItems": 2, "items": {"type": "object", "required": ["code"], "properties": {"code": _CODE, "weight": {"type": "integer", "minimum": 1, "maximum": 10}, "label": _I18N}, "additionalProperties": False}},
        "strata_by": {"type": "array", "items": _KEY},
        "block_multiplier": {"type": "integer", "minimum": 1, "maximum": 10},
    }, ["arms"]),
    "stimulus": _module({
        "arm_of": _KEY, "stratum_by": _KEY, "prompt": _I18N,
        "contents": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": _I18N}},
    }, ["contents"]),
    "choice": _module({
        "prompt": _I18N, "options": {"type": "array", "items": _OPTION, "minItems": 2}, "stratum_by": _KEY,
        "contents": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": _I18N}},
    }, ["prompt", "options", "contents"]),
    "debrief": _module({"text": _I18N, "stratum_by": _KEY, "texts": {"type": "object", "additionalProperties": _I18N}, "offer_withdrawal": {"type": "boolean"}}, ["text"]),
    "thanks": _module({"text": _I18N, "show_retest_link": {"type": "boolean"}}, ["text"]),
}

BUNDLE_SCHEMA = {
    "type": "object",
    "required": ["format", "version", "survey", "modules"],
    "properties": {
        "format": {"const": BUNDLE_FORMAT},
        "version": {"const": BUNDLE_VERSION},
        "survey": {
            "type": "object",
            "required": ["title", "languages", "default_language"],
            "properties": {
                "title": _I18N, "description": _I18N,
                "languages": {"type": "array", "items": {"type": "string", "pattern": "^[a-z]{2,3}(-[A-Za-z0-9]+)?$"}, "minItems": 1, "uniqueItems": True},
                "default_language": {"type": "string"},
                "detect_browser_language": {"type": "boolean"},
                "allow_language_switch": {"type": "boolean"},
                "retest": {"type": "boolean"},
                "slug": {"type": "string", "pattern": "^[A-Za-z0-9_-]{4,32}$"},
            },
            "additionalProperties": False,
        },
        "modules": {"type": "array", "items": {"type": "object", "required": ["key", "type"]}},
    },
    "additionalProperties": False,
}


def _msg(code: str, **kw: Any) -> dict[str, Any]:
    out = {"code": code}
    out.update(kw)
    return out


def _schema_errors(instance: Any, schema: dict[str, Any], where: str) -> list[dict[str, Any]]:
    out = []
    for err in sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path)
        out.append(_msg("schema", where=where, path=path, detail=err.message[:300]))
    return out


def _texts(module: dict[str, Any]) -> list[tuple[str, Any]]:
    """Every translatable text of a module with a readable location."""
    out: list[tuple[str, Any]] = []
    t = module.get("type")
    for field in ("title", "text", "agree_label", "decline_label", "intro", "instructions", "relation",
                  "criterion", "side_label", "attention_label", "prompt"):
        if field in module and module[field]:
            out.append((field, module[field]))
    for i, q in enumerate(module.get("questions", []) or []):
        out.append((f"questions.{i}.label", q.get("label")))
        if q.get("help"):
            out.append((f"questions.{i}.help", q.get("help")))
        for j, o in enumerate(q.get("options", []) or []):
            out.append((f"questions.{i}.options.{j}", o.get("label")))
    for field in ("elements", "items"):
        for i, c in enumerate(module.get(field, []) or []):
            out.append((f"{field}.{i}", c.get("label")))
    if module.get("anchor"):
        out.append(("anchor", module["anchor"].get("label")))
    if module.get("gate"):
        out.append(("gate.question", module["gate"].get("question")))
        for j, o in enumerate(module["gate"].get("options", [])):
            out.append((f"gate.options.{j}", o.get("label")))
    for name, variant in (module.get("variants") or {}).items():
        for i, c in enumerate(variant.get("items", [])):
            out.append((f"variants.{name}.items.{i}", c.get("label")))
        if variant.get("criterion"):
            out.append((f"variants.{name}.criterion", variant["criterion"]))
    if t == "choice":
        for j, o in enumerate(module.get("options", [])):
            out.append((f"options.{j}.label", o.get("label")))
            if o.get("preview"):
                out.append((f"options.{j}.preview", o.get("preview")))
    for outer, inner in (module.get("contents") or {}).items():
        for stratum, text in inner.items():
            out.append((f"contents.{outer}.{stratum}", text))
    for stratum, text in (module.get("texts") or {}).items():
        out.append((f"texts.{stratum}", text))
    if t == "randomizer":
        for j, arm in enumerate(module.get("arms", [])):
            if arm.get("label"):
                out.append((f"arms.{j}.label", arm["label"]))
    return out


def task_blocks(module: dict[str, Any], variant: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[list[str]]]:
    """Items and block schedule of a block task (or of one variant of it)."""
    src = variant if variant is not None else module
    items = src.get("items") or []
    codes = [c["code"] for c in items]
    if src.get("blocks"):
        blocks = [list(b) for b in src["blocks"]]
    elif src.get("design"):
        blocks = B.blocks_from_design(src["design"], codes)
    else:
        blocks = []
    return items, blocks


def _check_condition(cond: Any, known_answers: set[str], known_arms: set[str], where: str, errors: list) -> None:
    if not isinstance(cond, dict) or not cond:
        errors.append(_msg("condition_invalid", where=where))
        return
    if "all" in cond or "any" in cond:
        parts = cond.get("all", cond.get("any"))
        if not isinstance(parts, list) or not parts:
            errors.append(_msg("condition_invalid", where=where))
            return
        for p in parts:
            _check_condition(p, known_answers, known_arms, where, errors)
        return
    if "not" in cond:
        _check_condition(cond["not"], known_answers, known_arms, where, errors)
        return
    op = cond.get("op", "eq")
    if op not in CONDITION_OPS:
        errors.append(_msg("condition_op", where=where, op=op))
    if "answer" in cond:
        if cond["answer"] not in known_answers:
            errors.append(_msg("condition_unknown_answer", where=where, name=cond["answer"]))
    elif "arm" in cond:
        if cond["arm"] not in known_arms:
            errors.append(_msg("condition_unknown_randomizer", where=where, name=cond["arm"]))
    else:
        errors.append(_msg("condition_invalid", where=where))


def validate_bundle(bundle: Any, registry_languages: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(bundle, dict):
        return {"errors": [_msg("not_an_object")], "warnings": []}
    errors += _schema_errors(bundle, BUNDLE_SCHEMA, "bundle")
    if errors:
        return {"errors": errors, "warnings": warnings}
    survey = bundle["survey"]
    languages = survey["languages"]
    if survey["default_language"] not in languages:
        errors.append(_msg("default_language_not_listed", language=survey["default_language"]))
    if registry_languages is not None:
        for code in languages:
            if code not in registry_languages:
                warnings.append(_msg("language_not_enabled", language=code))
    for code in languages:
        if not survey["title"].get(code):
            warnings.append(_msg("missing_translation", where="survey", path="title", language=code))

    keys: set[str] = set()
    answers: set[str] = set()
    answer_types: dict[str, str] = {}
    randomizers: dict[str, list[str]] = {}
    content_modules: set[str] = set()
    has_consent = False
    for idx, module in enumerate(bundle["modules"]):
        mtype = module.get("type")
        key = module.get("key", f"#{idx}")
        where = f"module {key}"
        if mtype not in MODULE_SCHEMAS:
            errors.append(_msg("unknown_module_type", where=where, type=mtype))
            continue
        errs = _schema_errors(module, MODULE_SCHEMAS[mtype], where)
        if errs:
            errors += errs
            continue
        if key in keys:
            errors.append(_msg("duplicate_module_key", where=where))
        keys.add(key)
        if mtype == "consent":
            has_consent = True
            if idx != 0:
                warnings.append(_msg("consent_not_first", where=where))
        if "condition" in module:
            _check_condition(module["condition"], answers, set(randomizers), where, errors)

        if mtype == "form":
            for q in module["questions"]:
                if q["name"] in answers:
                    errors.append(_msg("duplicate_answer_name", where=where, name=q["name"]))
                if q["type"] in ("select", "radio", "checkbox") and not q.get("options"):
                    errors.append(_msg("question_without_options", where=where, name=q["name"]))
                if "condition" in q:
                    _check_condition(q["condition"], answers, set(randomizers), where + "." + q["name"], errors)
                answers.add(q["name"])
                answer_types[q["name"]] = q["type"]
        elif mtype == "board":
            codes = [e["code"] for e in module["elements"]]
            if len(set(codes)) != len(codes):
                errors.append(_msg("duplicate_codes", where=where))
            if module["kind"] in ("tier", "tier_aside") and not module.get("rows"):
                errors.append(_msg("tier_rows_missing", where=where))
            if module.get("confirm_critical") and module["kind"] != "arrow":
                warnings.append(_msg("confirm_only_arrow", where=where))
        elif mtype in ("sob_blocks", "tap_blocks"):
            for name in module.get("panel_from", []):
                if name not in content_modules:
                    errors.append(_msg("panel_unknown_module", where=where, name=name))
            technique = "sob" if mtype == "sob_blocks" else "tap"
            sources = []
            if module.get("variants"):
                if not module.get("variants_by"):
                    errors.append(_msg("variants_without_selector", where=where))
                elif module["variants_by"] not in answers:
                    errors.append(_msg("variants_unknown_answer", where=where, name=module["variants_by"]))
                for name, variant in module["variants"].items():
                    sources.append((f"{where} variant {name}", variant))
            else:
                if not module.get("items"):
                    errors.append(_msg("items_missing", where=where))
                sources.append((where, None))
            for label, variant in sources:
                src = variant if variant is not None else module
                codes = [c["code"] for c in src.get("items", [])]
                if len(set(codes)) != len(codes):
                    errors.append(_msg("duplicate_codes", where=label))
                    continue
                if module.get("anchor") and module["anchor"]["code"] in codes:
                    errors.append(_msg("anchor_code_clash", where=label))
                if not src.get("design") and not src.get("blocks"):
                    errors.append(_msg("blocks_missing", where=label))
                    continue
                try:
                    _, blocks = task_blocks(module, variant)
                except (KeyError, ValueError) as exc:
                    errors.append(_msg("design_unusable", where=label, detail=str(exc)))
                    continue
                check = B.verify_blocks(blocks, codes, technique)
                for m in check["messages"]:
                    if m["code"] in ("unknown_items", "repeated_item", "unequal_blocks", "no_blocks"):
                        errors.append(_msg("block_" + m["code"], where=label, **{k: v for k, v in m.items() if k != "code"}))
                    else:
                        warnings.append(_msg("block_" + m["code"], where=label, **{k: v for k, v in m.items() if k != "code"}))
                ref = src.get("reference_order")
                if ref:
                    flat = [c for tier in ref for c in tier]
                    if sorted(flat) != sorted(codes):
                        errors.append(_msg("reference_order_mismatch", where=label))
        elif mtype == "randomizer":
            codes = [a["code"] for a in module["arms"]]
            if len(set(codes)) != len(codes):
                errors.append(_msg("duplicate_codes", where=where))
            for name in module.get("strata_by", []):
                if name not in answers:
                    errors.append(_msg("strata_unknown_answer", where=where, name=name))
                elif answer_types.get(name) not in ("select", "radio", "yesno"):
                    warnings.append(_msg("strata_free_answer", where=where, name=name))
            randomizers[key] = codes
        elif mtype == "stimulus":
            content_modules.add(key)
            arm_of = module.get("arm_of")
            if arm_of:
                if arm_of not in randomizers:
                    errors.append(_msg("stimulus_unknown_randomizer", where=where, name=arm_of))
                else:
                    extra = set(module["contents"]) - set(randomizers[arm_of]) - {"*"}
                    if extra:
                        errors.append(_msg("stimulus_unknown_arms", where=where, arms=sorted(extra)))
            if module.get("stratum_by") and module["stratum_by"] not in answers:
                errors.append(_msg("stratum_unknown_answer", where=where, name=module["stratum_by"]))
        elif mtype == "choice":
            content_modules.add(key)
            values = [o["value"] for o in module["options"]]
            missing = [v for v in values if v not in module["contents"]]
            if missing:
                errors.append(_msg("choice_without_content", where=where, options=missing))
            if module.get("stratum_by") and module["stratum_by"] not in answers:
                errors.append(_msg("stratum_unknown_answer", where=where, name=module["stratum_by"]))
            if key in answers:
                errors.append(_msg("duplicate_answer_name", where=where, name=key))
            answers.add(key)
            answer_types[key] = "radio"
        elif mtype == "debrief":
            if module.get("stratum_by") and module["stratum_by"] not in answers:
                errors.append(_msg("stratum_unknown_answer", where=where, name=module["stratum_by"]))

        for path, value in _texts(module):
            for code in languages:
                if not (isinstance(value, dict) and value.get(code)):
                    warnings.append(_msg("missing_translation", where=where, path=path, language=code))
    if not bundle["modules"]:
        errors.append(_msg("no_modules"))
    if not has_consent:
        warnings.append(_msg("no_consent"))
    return {"errors": errors, "warnings": warnings}


def blocking_for_publish(result: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Messages that prevent publishing: every error and every missing translation."""
    return result["errors"] + [w for w in result["warnings"] if w["code"] == "missing_translation"]


def new_bundle(title: dict[str, str], languages: list[str], default_language: str) -> dict[str, Any]:
    return {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "survey": {"title": dict(title), "description": {}, "languages": list(languages), "default_language": default_language,
                   "detect_browser_language": True, "allow_language_switch": True, "retest": False},
        "modules": [],
    }


def strip_slug(bundle: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(bundle)
    out.get("survey", {}).pop("slug", None)
    return out
