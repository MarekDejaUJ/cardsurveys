"""The respondent's path through a survey.

A survey is a list of modules. The response keeps its position (module index,
step inside the module, occasion) and the per-respondent schedules (block
order, card order, board card order, chosen variants) in its state, so that a
respondent who reloads a page or returns later sees the same screen.
"""
from __future__ import annotations

import json
import random
import secrets
from dataclasses import dataclass
from typing import Any

from ..engine import blocks as B
from ..engine import structures as S
from ..extensions import db
from ..models import (Allocation, Answer, Arrangement, BlockResponse, Confirmation, Judgment, PairObservation,
                      Response, ScreenTime, utcnow)
from . import conditions, randomizer
from .schema import task_blocks

SCREEN_TYPES = ("consent", "info", "form", "board", "sob_blocks", "tap_blocks", "stimulus", "choice", "debrief", "thanks")


class FlowError(ValueError):
    """A submission that cannot be recorded; the message key is shown to the respondent."""

    def __init__(self, key: str, **kw: Any):
        super().__init__(key)
        self.key = key
        self.kw = kw


@dataclass
class Screen:
    module: dict[str, Any]
    index: int
    step: int
    occasion: int
    total_steps: int

    @property
    def key(self) -> str:
        return f"{self.module['key']}:{self.step}:{self.occasion}"


# ---------------------------------------------------------------- answers and assignments


def answers_of(response: Response, occasion: int = 1) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for a in Answer.query.filter_by(response_id=response.id, occasion=occasion).all():
        try:
            out[a.name] = json.loads(a.value)
        except (json.JSONDecodeError, TypeError):
            out[a.name] = a.value
    return out


def store_answer(response: Response, module_key: str, name: str, value: Any, occasion: int = 1) -> None:
    row = Answer.query.filter_by(response_id=response.id, module_key=module_key, name=name, occasion=occasion).first()
    text = json.dumps(value, ensure_ascii=False)
    if row is None:
        db.session.add(Answer(response_id=response.id, module_key=module_key, name=name, occasion=occasion, value=text))
    else:
        row.value = text


def _rng(response: Response, salt: str) -> random.Random:
    return random.Random(f"{response.uuid}|{salt}|{secrets.token_hex(8)}")


# ---------------------------------------------------------------- per-module schedules


def variant_of(module: dict[str, Any], answers: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """The variant of a block task chosen by an earlier answer ('' when the task has no variants)."""
    variants = module.get("variants")
    if not variants:
        return "", None
    value = answers.get(module.get("variants_by", ""), "")
    if isinstance(value, list):
        value = value[0] if value else ""
    if value in variants:
        return str(value), variants[value]
    if "*" in variants:
        return "*", variants["*"]
    return "", None


def schedule_for(response: Response, module: dict[str, Any], occasion: int, answers: dict[str, Any]) -> list[dict[str, Any]]:
    state = response.state
    sk = f"{module['key']}@{occasion}"
    sched = state.setdefault("schedules", {})
    if sk in sched:
        return sched[sk]
    name, variant = variant_of(module, answers)
    if module.get("variants") and variant is None:
        entries: list[dict[str, Any]] = []
    else:
        _, blocks = task_blocks(module, variant)
        anchor = module.get("anchor", {}).get("code") if module["type"] == "tap_blocks" and module.get("anchor") else None
        entries = B.build_schedule(
            blocks, _rng(response, sk),
            shuffle_blocks=module.get("shuffle_blocks", True), shuffle_cards=module.get("shuffle_cards", True),
            duplicates=int(module.get("duplicates", 0) or 0) if module["type"] == "tap_blocks" else 0,
            attention=int(module.get("attention", 0) or 0) if module["type"] == "tap_blocks" else 0,
            attention_code="ATTN", anchor_code=anchor)
    for e in entries:
        e["variant"] = name
    sched[sk] = entries
    state.setdefault("variants", {})[module["key"]] = name
    response.state = state
    return entries


def board_order(response: Response, module: dict[str, Any], occasion: int) -> list[int]:
    state = response.state
    key = f"{module['key']}@{occasion}"
    orders = state.setdefault("board_orders", {})
    if key not in orders:
        order = list(range(len(module["elements"])))
        if module.get("randomize_order", True):
            _rng(response, key).shuffle(order)
        orders[key] = order
        response.state = state
    return orders[key]


def steps_of(response: Response, module: dict[str, Any], occasion: int, answers: dict[str, Any]) -> int:
    t = module["type"]
    if t in ("sob_blocks", "tap_blocks"):
        return len(schedule_for(response, module, occasion, answers))
    if t == "board":
        return 2
    if t == "choice":
        return 2
    if t == "randomizer":
        return 0
    return 1


# ---------------------------------------------------------------- navigation


def _applies(module: dict[str, Any], occasion: int) -> bool:
    if occasion == 1:
        return True
    return bool(module.get("retest")) or module["type"] == "thanks"


def content_for(module: dict[str, Any], response: Response, answers: dict[str, Any]) -> Any:
    """The text a stimulus, choice or debrief module shows to this respondent (None when nothing applies)."""
    t = module["type"]
    stratum = answers.get(module.get("stratum_by", ""), "*") if module.get("stratum_by") else "*"
    if isinstance(stratum, list):
        stratum = stratum[0] if stratum else "*"
    if t == "stimulus":
        arm = "*"
        if module.get("arm_of"):
            assigned = response.assignments.get(module["arm_of"]) or {}
            arm = assigned.get("arm", "*")
        block = module["contents"].get(arm) or module["contents"].get("*")
        if not block:
            return None
        return block.get(str(stratum)) or block.get("*")
    if t == "choice":
        chosen = answers.get(module["key"])
        if not chosen:
            return None
        block = module["contents"].get(chosen) or {}
        return block.get(str(stratum)) or block.get("*")
    if t == "debrief":
        texts = module.get("texts") or {}
        return texts.get(str(stratum)) or module.get("text")
    return None


def current_screen(survey, response: Response) -> Screen | None:
    """Advance past modules that do not apply and return the screen to show (None at the end)."""
    modules = survey.modules
    state = response.state
    occasion = int(state.get("occasion", 1))
    index = int(state.get("index", 0))
    step = int(state.get("step", 0))
    answers = answers_of(response)
    changed = False
    while index < len(modules):
        module = modules[index]
        skip = not _applies(module, occasion) or not conditions.holds(module.get("condition"), answers, response.assignments)
        if not skip and module["type"] == "randomizer":
            if occasion == 1 and module["key"] not in response.assignments:
                assigned = randomizer.allocate(survey, module, response, answers)
                arms = response.assignments
                arms[module["key"]] = assigned
                response.assignments = arms
            skip = True
        if not skip and module["type"] in ("stimulus",) and content_for(module, response, answers) is None:
            skip = True
        if not skip:
            total = steps_of(response, module, occasion, answers)
            state = response.state
            if total == 0 or step >= total:
                skip = True
            else:
                if changed:
                    state["index"], state["step"] = index, step
                    response.state = state
                return Screen(module=module, index=index, step=step, occasion=occasion, total_steps=total)
        index += 1
        step = 0
        changed = True
        state = response.state
        state["index"], state["step"] = index, 0
        response.state = state
    return None


def advance(response: Response, *, next_step: bool = False, to_step: int | None = None) -> None:
    state = response.state
    if to_step is not None:
        state["step"] = to_step
    elif next_step:
        state["step"] = int(state.get("step", 0)) + 1
    else:
        state["index"] = int(state.get("index", 0)) + 1
        state["step"] = 0
    response.state = state


def progress(survey, response: Response) -> float:
    n = max(len(survey.modules), 1)
    state = response.state
    index = int(state.get("index", 0))
    step = int(state.get("step", 0))
    module = survey.modules[index] if index < len(survey.modules) else None
    frac = 0.0
    if module is not None and module["type"] in ("sob_blocks", "tap_blocks"):
        sk = f"{module['key']}@{state.get('occasion', 1)}"
        total = len(state.get("schedules", {}).get(sk, [])) or 1
        frac = step / total
    return min(1.0, (index + frac) / n)


def finish(response: Response) -> None:
    occasion = int(response.state.get("occasion", 1))
    if occasion == 1 and response.status == "started":
        response.status = "submitted"
        response.submitted_at = utcnow()
    elif occasion == 2 and response.retest_submitted_at is None:
        response.retest_submitted_at = utcnow()


def start_retest(survey, response: Response) -> bool:
    if not survey.settings.get("retest") or response.status != "submitted":
        return False
    state = response.state
    if int(state.get("occasion", 1)) == 2:
        return True
    state.update({"occasion": 2, "index": 0, "step": 0})
    response.state = state
    return True


# ---------------------------------------------------------------- paradata


def mark_shown(response: Response, screen: Screen) -> None:
    row = ScreenTime.query.filter_by(response_id=response.id, screen_key=screen.key).first()
    if row is None:
        db.session.add(ScreenTime(response_id=response.id, screen_key=screen.key, module_key=screen.module["key"], occasion=screen.occasion))
    else:
        row.visits += 1


def mark_submitted(response: Response, screen: Screen, client_ms: Any) -> None:
    row = ScreenTime.query.filter_by(response_id=response.id, screen_key=screen.key).first()
    if row is None:
        row = ScreenTime(response_id=response.id, screen_key=screen.key, module_key=screen.module["key"], occasion=screen.occasion)
        db.session.add(row)
    row.submitted_at = utcnow()
    try:
        ms = int(float(client_ms))
        if 0 <= ms < 24 * 3600 * 1000:
            row.client_ms = (row.client_ms or 0) + ms
    except (TypeError, ValueError):
        pass


# ---------------------------------------------------------------- submissions


def _visible_questions(module: dict[str, Any], answers: dict[str, Any], arms: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    merged = dict(answers)
    merged.update(current)
    return [q for q in module["questions"] if conditions.holds(q.get("condition"), merged, arms)]


def submit_form(response: Response, module: dict[str, Any], form: Any) -> dict[str, list[str]]:
    """Validate and store a form; returns field errors (empty when stored)."""
    answers = answers_of(response)
    current: dict[str, Any] = {}
    for q in module["questions"]:
        if q["type"] == "checkbox":
            current[q["name"]] = form.getlist(q["name"])
        else:
            current[q["name"]] = (form.get(q["name"]) or "").strip()
    errors: dict[str, list[str]] = {}
    for q in _visible_questions(module, answers, response.assignments, current):
        name, value = q["name"], current[q["name"]]
        empty = value == "" or value == []
        if q.get("required") and empty:
            errors.setdefault(name, []).append("required")
            continue
        if empty:
            continue
        if q["type"] in ("select", "radio"):
            if value not in [o["value"] for o in q.get("options", [])]:
                errors.setdefault(name, []).append("invalid_option")
        elif q["type"] == "checkbox":
            allowed = {o["value"] for o in q.get("options", [])}
            if any(v not in allowed for v in value):
                errors.setdefault(name, []).append("invalid_option")
        elif q["type"] == "yesno":
            if value not in ("yes", "no"):
                errors.setdefault(name, []).append("invalid_option")
        elif q["type"] == "number":
            try:
                num = float(value.replace(",", "."))
            except ValueError:
                errors.setdefault(name, []).append("not_a_number")
                continue
            if "min" in q and num < q["min"]:
                errors.setdefault(name, []).append("too_small")
            if "max" in q and num > q["max"]:
                errors.setdefault(name, []).append("too_large")
        elif len(str(value)) > 5000:
            errors.setdefault(name, []).append("too_long")
    if errors:
        return errors
    visible = {q["name"] for q in _visible_questions(module, answers, response.assignments, current)}
    for q in module["questions"]:
        if q["name"] in visible:
            store_answer(response, module["key"], q["name"], current[q["name"]])
    return {}


def submit_board(response: Response, module: dict[str, Any], occasion: int, placements_text: str, order_text: str) -> bool:
    """Record a board arrangement; returns True when confirmation questions follow."""
    n = len(module["elements"])
    kind = module["kind"]
    k = int(module.get("rows", 3) or 3)
    codes = [e["code"] for e in module["elements"]]
    try:
        placements = json.loads(placements_text or "")
    except json.JSONDecodeError:
        raise FlowError("board_incomplete")
    if not S.placements_complete(kind, n, placements):
        raise FlowError("board_incomplete")
    try:
        read = S.reading(kind, n, placements, k)
    except (ValueError, TypeError, KeyError, IndexError):
        raise FlowError("board_incomplete")
    if not read["coherent"] and kind != "pairs":
        raise FlowError("board_circle")
    row = Arrangement.query.filter_by(response_id=response.id, module_key=module["key"], occasion=occasion).first()
    para: dict[str, Any] = json.loads(row.paradata_json) if row else {}
    para.setdefault("display_order", [codes[i] for i in board_order(response, module, occasion)])
    para["submissions"] = int(para.get("submissions", 0)) + 1
    if read["judgments"] == "sim":
        reading_pairs = [[codes[i], codes[j]] for i, j in S.to_upairs(read["structure"], n)]
    else:
        reading_pairs = [[codes[i], codes[j]] for i, j in S.to_pairs(read["structure"], n)]
    if row is None:
        row = Arrangement(response_id=response.id, module_key=module["key"], occasion=occasion, board_kind=kind)
        db.session.add(row)
    row.board_kind = kind
    row.placements_json = json.dumps(placements, sort_keys=True)
    row.reading_json = json.dumps(reading_pairs)
    row.coherent = bool(read["coherent"])
    row.paradata_json = json.dumps(para, sort_keys=True)
    row.completed = False
    Judgment.query.filter_by(response_id=response.id, module_key=module["key"], occasion=occasion).delete()
    undecided = set(tuple(p) for p in read.get("undecided", []))
    for st in S.states(read["structure"], n, read["judgments"]):
        state = st["state"]
        if (st["a"], st["b"]) in undecided:
            state = "undecided"
        db.session.add(Judgment(response_id=response.id, module_key=module["key"], occasion=occasion,
                                element_a=codes[st["a"]], element_b=codes[st["b"]], state=state))
    if kind == "arrow" and module.get("confirm_critical") and S.critical_pairs(read["structure"], n):
        return True
    row.completed = True
    return False


def board_structure(response: Response, module: dict[str, Any], occasion: int) -> int:
    codes = [e["code"] for e in module["elements"]]
    index = {c: i for i, c in enumerate(codes)}
    row = Arrangement.query.filter_by(response_id=response.id, module_key=module["key"], occasion=occasion).first()
    if row is None:
        return 0
    return S.from_pairs([(index[a], index[b]) for a, b in json.loads(row.reading_json)])


def confirmation_pairs(response: Response, module: dict[str, Any], occasion: int) -> list[tuple[int, int]]:
    P = board_structure(response, module, occasion)
    return sorted(S.critical_pairs(P, len(module["elements"])))


def submit_confirm(response: Response, module: dict[str, Any], occasion: int, form: Any) -> list[tuple[int, int]]:
    """Record answers to the confirmation questions; returns the pairs the respondent says are related."""
    pairs = confirmation_pairs(response, module, occasion)
    codes = [e["code"] for e in module["elements"]]
    answers = {}
    for i, j in pairs:
        v = form.get(f"pair_{i}_{j}")
        if v not in ("unrelated", "related"):
            raise FlowError("answer_every_question")
        answers[(i, j)] = v
    related = []
    for (i, j), v in answers.items():
        db.session.add(Confirmation(response_id=response.id, module_key=module["key"], occasion=occasion,
                                    element_a=codes[i], element_b=codes[j], answer="unrelated" if v == "unrelated" else "refused"))
        if v == "related":
            related.append((i, j))
    if not related:
        row = Arrangement.query.filter_by(response_id=response.id, module_key=module["key"], occasion=occasion).first()
        if row is not None:
            row.completed = True
    return related


def submit_block(response: Response, module: dict[str, Any], occasion: int, step: int, result_text: str,
                 events_text: str, gate_value: str | None, duration: Any) -> None:
    answers = answers_of(response)
    entry = schedule_for(response, module, occasion, answers)[step]
    cards = entry["cards"]
    try:
        result = json.loads(result_text or "")
    except json.JSONDecodeError:
        raise FlowError("block_incomplete")
    technique = "sob" if module["type"] == "sob_blocks" else "tap"
    try:
        if technique == "sob":
            if not isinstance(result, dict):
                raise ValueError
            pairs = B.read_sob(cards, result, len(cards))
            stored_result: Any = {c: result[c] for c in cards}
            passed = None
        else:
            if not isinstance(result, list):
                raise ValueError
            anchor = (module.get("anchor") or {}).get("code")
            closes = bool(anchor and module.get("anchor_closes"))
            read = B.read_tap(cards, [str(x) for x in result], anchor=anchor, closes=closes)
            pairs = read["pairs"]
            stored_result = read["order"]
            passed = (B.attention_passed(read["order"], "ATTN", module.get("attention_position", "last"),
                                         anchor=anchor if closes else None)
                      if entry.get("attention") else None)
    except (ValueError, TypeError, KeyError):
        raise FlowError("block_incomplete")
    gate = module.get("gate") if technique == "tap" else None
    if gate:
        allowed = [o["value"] for o in gate["options"]]
        if gate_value not in allowed:
            raise FlowError("answer_gate")
    else:
        gate_value = None
    try:
        events = json.loads(events_text or "[]")
        if not isinstance(events, list):
            events = []
    except json.JSONDecodeError:
        events = []
    events = events[:400]
    try:
        dur = int(float(duration))
        if dur < 0 or dur > 24 * 3600 * 1000:
            dur = None
    except (TypeError, ValueError):
        dur = None
    row = BlockResponse.query.filter_by(response_id=response.id, module_key=module["key"], occasion=occasion, position=step).first()
    if row is None:
        row = BlockResponse(response_id=response.id, module_key=module["key"], occasion=occasion, position=step, technique=technique)
        db.session.add(row)
    row.variant = entry.get("variant", "")
    row.design_block = entry.get("design_block")
    row.repeat_of = entry.get("repeat_of")
    row.attention = bool(entry.get("attention"))
    row.attention_passed = passed
    row.cards_json = json.dumps(cards)
    row.result_json = json.dumps(stored_result)
    row.gate_value = gate_value
    row.events_json = json.dumps(events)
    row.duration_ms = dur
    PairObservation.query.filter_by(response_id=response.id, module_key=module["key"], occasion=occasion, position=step).delete()
    if not entry.get("attention"):
        for p in pairs:
            db.session.add(PairObservation(response_id=response.id, module_key=module["key"], occasion=occasion,
                                           position=step, item_a=p["item_a"], item_b=p["item_b"], relation=p["relation"]))


def submit_choice(response: Response, module: dict[str, Any], value: str | None) -> None:
    if value not in [o["value"] for o in module["options"]]:
        raise FlowError("choose_one")
    store_answer(response, module["key"], module["key"], value)


def withdraw(response: Response) -> None:
    """Delete everything the respondent gave; only the withdrawn status remains."""
    for model in (Answer, Arrangement, Judgment, Confirmation, BlockResponse, PairObservation, ScreenTime):
        model.query.filter_by(response_id=response.id).delete()
    Allocation.query.filter_by(response_id=response.id).update({"response_id": None})
    response.status = "withdrawn"
    response.state = {}
    response.assignments = {}
    response.consented = False
