"""Display conditions of modules and questions."""
from __future__ import annotations

from typing import Any


def _values(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def holds(cond: dict[str, Any] | None, answers: dict[str, Any], arms: dict[str, Any]) -> bool:
    """Evaluate a condition against stored answers and arm assignments.

    A condition is {"all": [...]}, {"any": [...]}, {"not": {...}} or a test
    {"answer"|"arm": name, "op": eq|ne|in|not_in|answered|empty, "value": ...}.
    A test on an answer that does not exist yet is false (and its "not" is true).
    """
    if not cond:
        return True
    if "all" in cond:
        return all(holds(c, answers, arms) for c in cond["all"])
    if "any" in cond:
        return any(holds(c, answers, arms) for c in cond["any"])
    if "not" in cond:
        return not holds(cond["not"], answers, arms)
    op = cond.get("op", "eq")
    if "answer" in cond:
        current = answers.get(cond["answer"])
    else:
        assigned = arms.get(cond.get("arm"))
        current = assigned.get("arm") if isinstance(assigned, dict) else assigned
    have = [x for x in _values(current) if x != ""]
    if op == "answered":
        return bool(have)
    if op == "empty":
        return not have
    want = _values(cond.get("value"))
    target = want[0] if want else ""
    if op == "eq":
        return target in have
    if op == "ne":
        return target not in have
    if op == "in":
        return any(x in want for x in have)
    if op == "not_in":
        return bool(have) and not any(x in want for x in have)
    return False
