"""Arm assignment by permuted blocks within strata.

Every stratum (the combination of the answers named in ``strata_by``) has its
own sequence of assignments. The sequence is cut into blocks that hold every arm
as often as its weight times the block multiplier; inside a block the order is a
permutation derived from the survey's secret seed, so the next arm cannot be
guessed from the outside. Each assignment takes the next sequence number of its
stratum; a unique constraint on (survey, randomizer, stratum, number) makes
concurrent respondents take different numbers.
"""
from __future__ import annotations

import hashlib
import hmac
import random
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Allocation


def stratum_key(module: dict[str, Any], answers: dict[str, Any]) -> str:
    names = module.get("strata_by") or []
    if not names:
        return "*"
    parts = []
    for name in names:
        value = answers.get(name, "")
        if isinstance(value, list):
            value = ",".join(sorted(str(v) for v in value))
        parts.append(f"{name}={value}")
    return "|".join(parts)


def block_arms(module: dict[str, Any]) -> list[str]:
    mult = int(module.get("block_multiplier", 1) or 1)
    out = []
    for arm in module["arms"]:
        out += [arm["code"]] * int(arm.get("weight", 1) or 1) * mult
    return out


def arm_at(seed: str, module: dict[str, Any], stratum: str, seq_no: int) -> str:
    arms = block_arms(module)
    size = len(arms)
    block_no, pos = divmod(seq_no, size)
    digest = hmac.new(seed.encode(), f"{module['key']}|{stratum}|{block_no}".encode(), hashlib.sha256).hexdigest()
    rng = random.Random(int(digest, 16))
    perm = list(arms)
    rng.shuffle(perm)
    return perm[pos]


def allocate(survey, module: dict[str, Any], response, answers: dict[str, Any]) -> dict[str, Any]:
    """Assign the next arm of the respondent's stratum and record the allocation."""
    stratum = stratum_key(module, answers)
    store_stratum = ("preview:" + stratum) if response.preview else stratum
    for _ in range(50):
        current = db.session.query(func.max(Allocation.seq_no)).filter_by(
            survey_id=survey.id, randomizer_key=module["key"], stratum=store_stratum).scalar()
        seq_no = 0 if current is None else current + 1
        arm = arm_at(survey.allocation_seed, module, stratum, seq_no)
        row = Allocation(survey_id=survey.id, randomizer_key=module["key"], stratum=store_stratum, seq_no=seq_no,
                         arm=arm, response_id=response.id, preview=bool(response.preview))
        try:
            with db.session.begin_nested():
                db.session.add(row)
            db.session.flush()
            return {"arm": arm, "stratum": stratum, "seq_no": seq_no}
        except IntegrityError:
            continue
    raise RuntimeError("could not allocate an arm")
