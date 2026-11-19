"""Creating, storing and moving surveys as bundles."""
from __future__ import annotations

import copy
import json
import re
import secrets
from typing import Any

from ..extensions import db
from ..models import Response, Survey, User, utcnow
from .schema import validate_bundle


class BundleError(ValueError):
    def __init__(self, messages: list[dict[str, Any]]):
        super().__init__("bundle not valid")
        self.messages = messages


def make_slug() -> str:
    while True:
        slug = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:11]
        if len(slug) >= 8 and not Survey.query.filter_by(slug=slug).first():
            return slug


def parse_bundle_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BundleError([{"code": "not_json", "detail": str(exc)[:200]}])


def create_from_bundle(owner: User, bundle: dict[str, Any], registry: list[str] | None = None, *, is_demo: bool = False,
                       keep_slug: bool = False) -> Survey:
    result = validate_bundle(bundle, registry)
    if result["errors"]:
        raise BundleError(result["errors"])
    definition = copy.deepcopy(bundle)
    slug = definition["survey"].pop("slug", None)
    if not keep_slug or not slug or Survey.query.filter_by(slug=slug).first():
        slug = make_slug()
    survey = Survey(owner=owner, slug=slug, status="draft", allocation_seed=secrets.token_hex(32), is_demo=is_demo)
    survey.definition = definition
    db.session.add(survey)
    db.session.flush()
    return survey


def export_bundle(survey: Survey) -> dict[str, Any]:
    out = copy.deepcopy(survey.definition)
    out["survey"]["slug"] = survey.slug
    return out


def replace_definition(survey: Survey, bundle: dict[str, Any], registry: list[str] | None = None) -> dict[str, list]:
    """Store a new definition; refused when the bundle has errors or when the survey already has responses that the change would orphan."""
    result = validate_bundle(bundle, registry)
    if result["errors"]:
        raise BundleError(result["errors"])
    definition = copy.deepcopy(bundle)
    definition["survey"].pop("slug", None)
    survey.definition = definition
    survey.revision = (survey.revision or 1) + 1
    survey.updated_at = utcnow()
    return result


def has_live_responses(survey: Survey) -> bool:
    return Response.query.filter_by(survey_id=survey.id, preview=False).count() > 0


def module_index(survey: Survey, key: str) -> int:
    for i, m in enumerate(survey.modules):
        if m["key"] == key:
            return i
    raise KeyError(key)


def unique_module_key(survey: Survey, base: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", base) or "module"
    if not base[0].isalpha():
        base = "m_" + base
    existing = {m["key"] for m in survey.modules}
    if base not in existing:
        return base
    i = 2
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"
