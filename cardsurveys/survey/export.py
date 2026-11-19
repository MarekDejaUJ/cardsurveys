"""Data exports and monitor statistics.

The ZIP of a survey holds the survey bundle, a description with the codebook,
one CSV per table and, for every board task, a folder in the layout that the
board readers of the companion R package take as input (study.json,
responses.csv, placements.csv, judgments.csv, confirmations.csv). Preview
responses never leave the system.
"""
from __future__ import annotations

import csv
import io
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from ..engine import structures as S
from ..i18n import text_for
from ..models import (Allocation, Answer, Arrangement, BlockResponse, Confirmation, Judgment, PairObservation,
                      Response, ScreenTime)
from .schema import task_blocks

EXPORT_FORMAT = "cardsurveys-export-1"


def _csv(header: list[str], rows: list[list[Any]]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return out.getvalue()


def _iso(dt: datetime | None) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if dt else ""


def _responses(survey) -> list[Response]:
    return Response.query.filter_by(survey_id=survey.id, preview=False).order_by(Response.started_at, Response.id).all()


def answer_columns(survey) -> list[str]:
    names = []
    for m in survey.modules:
        if m["type"] == "form":
            names += [q["name"] for q in m["questions"]]
        elif m["type"] == "choice":
            names.append(m["key"])
    return names


def randomizer_keys(survey) -> list[str]:
    return [m["key"] for m in survey.modules if m["type"] == "randomizer"]


def _answers_by_response(ids: list[int]) -> dict[int, dict[tuple[int, str], Any]]:
    out: dict[int, dict[tuple[int, str], Any]] = defaultdict(dict)
    if not ids:
        return out
    for a in Answer.query.filter(Answer.response_id.in_(ids)).all():
        try:
            v = json.loads(a.value)
        except json.JSONDecodeError:
            v = a.value
        out[a.response_id][(a.occasion, a.name)] = v
    return out


def _flat(v: Any) -> str:
    if isinstance(v, list):
        return ";".join(str(x) for x in v)
    return "" if v is None else str(v)


def codebook(survey) -> dict[str, Any]:
    langs = survey.languages
    out: dict[str, Any] = {"languages": langs, "modules": []}
    for m in survey.modules:
        entry: dict[str, Any] = {"key": m["key"], "type": m["type"]}
        if m.get("title"):
            entry["title"] = m["title"]
        if m["type"] == "form":
            entry["questions"] = [{"name": q["name"], "type": q["type"], "label": q["label"],
                                   "options": [{"value": o["value"], "label": o["label"]} for o in q.get("options", [])]}
                                  for q in m["questions"]]
        elif m["type"] == "board":
            entry.update({"kind": m["kind"], "rows": m.get("rows"), "relation": m["relation"],
                          "elements": [{"code": e["code"], "label": e["label"]} for e in m["elements"]]})
        elif m["type"] in ("sob_blocks", "tap_blocks"):
            entry["criterion" if m["type"] == "tap_blocks" else "relation"] = m.get("criterion") or m.get("relation")
            if m.get("anchor"):
                entry["anchor"] = m["anchor"]
            if m.get("gate"):
                entry["gate"] = m["gate"]
            if m.get("variants"):
                entry["variants_by"] = m.get("variants_by")
                entry["variants"] = {}
                for name, var in m["variants"].items():
                    items, blocks = task_blocks(m, var)
                    entry["variants"][name] = {"items": items, "blocks": blocks, "reference_order": var.get("reference_order")}
            else:
                items, blocks = task_blocks(m)
                entry.update({"items": items, "blocks": blocks, "reference_order": m.get("reference_order")})
            entry["attention_card"] = "ATTN" if m.get("attention") else None
        elif m["type"] == "randomizer":
            entry.update({"arms": m["arms"], "strata_by": m.get("strata_by", []), "block_multiplier": m.get("block_multiplier", 1)})
        elif m["type"] == "choice":
            entry["options"] = [{"value": o["value"], "label": o["label"]} for o in m["options"]]
        out["modules"].append(entry)
    return out


FILE_NOTES = {
    "responses.csv": "One row per response: identifier, status (started, submitted, withdrawn, declined), language, times (UTC), survey revision, the arm and stratum of every randomizer, then one column per question and choice (several selected options joined by semicolons).",
    "answers.csv": "Every stored answer in long form: response, occasion, module, question name, value (JSON text).",
    "blocks.csv": "One row per block screen: technique (sob or tap), variant, screen position, design block index, repeated block index, attention block and whether it was passed, cards in display order, the response (tap: cards in tapped order; sob: stratum or 'side' per card), gate answer, time on the block in milliseconds, tap events [card or 'undo', milliseconds].",
    "pairs.csv": "Pair observations of block screens (attention blocks excluded): relation a_prec_b (item_a before item_b), b_prec_a or incomparable.",
    "screens.csv": "Paradata per screen: first shown and submitted (UTC), time on the page measured in the browser (milliseconds, summed over visits), number of visits.",
    "allocations.csv": "Every arm assignment: randomizer, stratum, sequence number in the stratum, arm, response (empty after a withdrawal).",
}


def description(survey) -> dict[str, Any]:
    from .. import __version__

    return {
        "format": EXPORT_FORMAT,
        "software": {"name": "Card Surveys", "version": __version__},
        "exported_at": _iso(datetime.now(timezone.utc).replace(tzinfo=None)),
        "survey": {"title": survey.settings.get("title", {}), "languages": survey.languages,
                   "default_language": survey.default_language, "revision": survey.revision, "status": survey.status},
        "files": FILE_NOTES,
        "codebook": codebook(survey),
    }


def board_study_json(survey, module: dict[str, Any]) -> dict[str, Any]:
    lang = "en" if "en" in survey.languages else survey.default_language
    return {
        "format": EXPORT_FORMAT,
        "elements": [{"code": e["code"], "label": text_for(e["label"], lang, survey.default_language) or e["code"]} for e in module["elements"]],
        "board": {"kind": module["kind"], "k": int(module.get("rows", 3) or 3)},
        "class": "eq" if module["kind"] == "pile" else "po",
        "judgments": "sim" if module["kind"] == "pile" else "prec",
        "relation": text_for(module["relation"], lang, survey.default_language),
        "confirm_critical": bool(module.get("confirm_critical")) and module["kind"] == "arrow",
        "retest": bool(survey.settings.get("retest")) and bool(module.get("retest")),
        "randomize_order": bool(module.get("randomize_order", True)),
    }


def export_files(survey) -> dict[str, str]:
    responses = _responses(survey)
    ids = [r.id for r in responses]
    uuid = {r.id: r.uuid for r in responses}
    answers = _answers_by_response(ids)
    names = answer_columns(survey)
    rkeys = randomizer_keys(survey)
    files: dict[str, str] = {}
    files["survey.json"] = json.dumps(survey.definition, ensure_ascii=False, indent=2)
    files["description.json"] = json.dumps(description(survey), ensure_ascii=False, indent=2)

    header = ["response_uuid", "status", "language", "started_at", "submitted_at", "retest_submitted_at", "revision"]
    for k in rkeys:
        header += [f"{k}_arm", f"{k}_stratum"]
    header += names
    rows = []
    for r in responses:
        a = r.assignments
        row = [r.uuid, r.status, r.language, _iso(r.started_at), _iso(r.submitted_at), _iso(r.retest_submitted_at), r.revision]
        for k in rkeys:
            row += [(a.get(k) or {}).get("arm", ""), (a.get(k) or {}).get("stratum", "")]
        row += [_flat(answers[r.id].get((1, n))) for n in names]
        rows.append(row)
    files["responses.csv"] = _csv(header, rows)

    rows = []
    if ids:
        for a in Answer.query.filter(Answer.response_id.in_(ids)).order_by(Answer.response_id, Answer.id).all():
            rows.append([uuid[a.response_id], a.occasion, a.module_key, a.name, a.value])
    files["answers.csv"] = _csv(["response_uuid", "occasion", "module_key", "name", "value"], rows)

    rows = []
    if ids:
        for b in BlockResponse.query.filter(BlockResponse.response_id.in_(ids)).order_by(BlockResponse.response_id, BlockResponse.module_key, BlockResponse.occasion, BlockResponse.position).all():
            rows.append([uuid[b.response_id], b.occasion, b.module_key, b.technique, b.variant, b.position, b.design_block,
                         b.repeat_of, int(b.attention), "" if b.attention_passed is None else int(b.attention_passed),
                         "|".join(json.loads(b.cards_json)), b.result_json, b.gate_value, b.duration_ms, b.events_json])
    files["blocks.csv"] = _csv(["response_uuid", "occasion", "module_key", "technique", "variant", "position", "design_block",
                                "repeat_of", "attention", "attention_passed", "cards", "result", "gate_value", "duration_ms", "events"], rows)

    rows = []
    variant_of = {}
    if ids:
        for b in BlockResponse.query.filter(BlockResponse.response_id.in_(ids)).all():
            variant_of[(b.response_id, b.module_key, b.occasion, b.position)] = b.variant
        for p in PairObservation.query.filter(PairObservation.response_id.in_(ids)).order_by(PairObservation.response_id, PairObservation.module_key, PairObservation.occasion, PairObservation.position, PairObservation.id).all():
            rows.append([uuid[p.response_id], p.occasion, p.module_key, variant_of.get((p.response_id, p.module_key, p.occasion, p.position), ""),
                         p.position, p.item_a, p.item_b, p.relation])
    files["pairs.csv"] = _csv(["response_uuid", "occasion", "module_key", "variant", "position", "item_a", "item_b", "relation"], rows)

    rows = []
    if ids:
        for s in ScreenTime.query.filter(ScreenTime.response_id.in_(ids)).order_by(ScreenTime.response_id, ScreenTime.id).all():
            rows.append([uuid[s.response_id], s.occasion, s.module_key, s.screen_key, _iso(s.first_shown_at), _iso(s.submitted_at), s.client_ms, s.visits])
    files["screens.csv"] = _csv(["response_uuid", "occasion", "module_key", "screen_key", "first_shown_at", "submitted_at", "client_ms", "visits"], rows)

    rows = []
    for al in Allocation.query.filter_by(survey_id=survey.id, preview=False).order_by(Allocation.randomizer_key, Allocation.stratum, Allocation.seq_no).all():
        rows.append([al.randomizer_key, al.stratum, al.seq_no, al.arm, uuid.get(al.response_id, ""), _iso(al.created_at)])
    files["allocations.csv"] = _csv(["randomizer_key", "stratum", "seq_no", "arm", "response_uuid", "created_at"], rows)

    for m in survey.modules:
        if m["type"] != "board":
            continue
        base = f"boards/{m['key']}/"
        files[base + "study.json"] = json.dumps(board_study_json(survey, m), ensure_ascii=False, indent=2)
        files[base + "responses.csv"] = _csv(["response_uuid", "status", "language", "started_at", "submitted_at"] + names,
                                             [[r.uuid, r.status, r.language, _iso(r.started_at), _iso(r.submitted_at)] + [_flat(answers[r.id].get((1, n))) for n in names] for r in responses])
        rows = []
        if ids:
            for a in Arrangement.query.filter(Arrangement.response_id.in_(ids), Arrangement.module_key == m["key"]).order_by(Arrangement.response_id, Arrangement.occasion).all():
                rows.append([uuid[a.response_id], a.occasion, a.board_kind, int(a.coherent), a.placements_json])
        files[base + "placements.csv"] = _csv(["response_uuid", "occasion", "board_kind", "coherent", "placements_json"], rows)
        rows = []
        if ids:
            for j in Judgment.query.filter(Judgment.response_id.in_(ids), Judgment.module_key == m["key"]).order_by(Judgment.response_id, Judgment.occasion, Judgment.element_a, Judgment.element_b).all():
                rows.append([uuid[j.response_id], j.occasion, j.element_a, j.element_b, j.state])
        files[base + "judgments.csv"] = _csv(["response_uuid", "occasion", "element_a", "element_b", "state"], rows)
        rows = []
        if ids:
            for c in Confirmation.query.filter(Confirmation.response_id.in_(ids), Confirmation.module_key == m["key"]).order_by(Confirmation.response_id, Confirmation.occasion, Confirmation.id).all():
                rows.append([uuid[c.response_id], c.occasion, c.element_a, c.element_b, c.answer])
        files[base + "confirmations.csv"] = _csv(["response_uuid", "occasion", "element_a", "element_b", "answer"], rows)
    return files


def export_zip(survey) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in export_files(survey).items():
            zf.writestr(name, text)
    return buf.getvalue()


# ---------------------------------------------------------------- monitor


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def monitor(survey) -> dict[str, Any]:
    responses = _responses(survey)
    ids = [r.id for r in responses]
    status = Counter(r.status for r in responses)
    durations = [(r.submitted_at - r.started_at).total_seconds() / 60 for r in responses if r.submitted_at]
    per_module: dict[str, list[int]] = defaultdict(list)
    per_resp_module: dict[tuple[int, str], int] = defaultdict(int)
    if ids:
        for s in ScreenTime.query.filter(ScreenTime.response_id.in_(ids)).all():
            if s.client_ms:
                per_resp_module[(s.response_id, s.module_key)] += s.client_ms
    for (rid, mk), ms in per_resp_module.items():
        per_module[mk].append(ms)
    modules = []
    for m in survey.modules:
        values = per_module.get(m["key"], [])
        modules.append({"key": m["key"], "type": m["type"], "n": len(values),
                        "median_seconds": (_median(values) / 1000 if values else None)})
    balance: dict[str, dict[str, Counter]] = {}
    for al in Allocation.query.filter_by(survey_id=survey.id, preview=False).all():
        balance.setdefault(al.randomizer_key, {}).setdefault(al.stratum, Counter())[al.arm] += 1
    attention = {"shown": 0, "passed": 0}
    gates: dict[str, Counter] = defaultdict(Counter)
    if ids:
        for b in BlockResponse.query.filter(BlockResponse.response_id.in_(ids)).all():
            if b.attention:
                attention["shown"] += 1
                attention["passed"] += 1 if b.attention_passed else 0
            if b.gate_value is not None:
                gates[b.module_key][b.gate_value] += 1
    days = Counter(r.started_at.date().isoformat() for r in responses)
    return {
        "total": len(responses),
        "status": dict(status),
        "median_minutes": _median(durations),
        "modules": modules,
        "balance": {k: {s: dict(c) for s, c in v.items()} for k, v in balance.items()},
        "attention": attention,
        "gates": {k: dict(v) for k, v in gates.items()},
        "days": sorted(days.items()),
        "board_summaries": board_summaries(survey, ids),
    }


def board_summaries(survey, ids: list[int]) -> dict[str, Any]:
    out = {}
    for m in survey.modules:
        if m["type"] != "board" or m["kind"] == "pile":
            continue
        n = len(m["elements"])
        codes = [e["code"] for e in m["elements"]]
        index = {c: i for i, c in enumerate(codes)}
        profile = []
        if ids:
            for a in Arrangement.query.filter(Arrangement.response_id.in_(ids), Arrangement.module_key == m["key"],
                                              Arrangement.occasion == 1, Arrangement.completed.is_(True), Arrangement.coherent.is_(True)).all():
                profile.append(S.from_pairs([(index[x], index[y]) for x, y in json.loads(a.reading_json)]))
        if not profile:
            out[m["key"]] = {"N": 0}
            continue
        summ = S.population_summary(profile, n)
        out[m["key"]] = {
            "N": summ["N"],
            "codes": codes,
            "pair_shares": summ["pair_shares"],
            "common_part": S.to_pairs(summ["common_part"], n),
            "majority": S.to_pairs(summ["majority"], n),
            "majority_coherent": summ["majority_coherent"],
            "agreement": summ["agreement"],
            "nearest": [S.to_pairs(C, n) for C in summ.get("nearest", [])] if summ.get("enumerated") else None,
            "mean_distance": summ.get("mean_distance"),
        }
    return out
