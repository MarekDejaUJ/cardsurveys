"""Public pages, demonstrations and the respondent's path through a survey."""
from __future__ import annotations

import json
import uuid as uuidlib

from flask import (Blueprint, abort, current_app, flash, make_response, redirect, render_template, request, url_for)

from .. import i18n
from ..engine import blocks as B
from ..engine import structures as S
from ..extensions import db
from ..models import Response, Survey
from ..security import rate_limited
from ..seeds import demos
from ..survey import runtime
from ..survey.runtime import FlowError

bp = Blueprint("public", __name__)

COOKIE_DAYS = 30


@bp.route("/")
def index():
    return render_template("public/index.html")


@bp.route("/privacy")
def privacy():
    return render_template("public/privacy.html")


@bp.route("/health")
def health():
    db.session.execute(db.text("SELECT 1"))
    return {"status": "ok"}


# ---------------------------------------------------------------- demonstrations (nothing is stored)

DEMO_KINDS = ("tier", "tier_aside", "arrow", "pile", "plane", "pairs")


def _demo_cards(lang: str):
    return [{"code": c, "label": i18n.text_for(lab, lang)} for c, lab in demos.PROJECT_CARDS]


@bp.route("/demo")
def demo_index():
    return render_template("demo/index.html", kinds=DEMO_KINDS)


@bp.route("/demo/board/<kind>")
def demo_board(kind: str):
    if kind not in DEMO_KINDS:
        abort(404)
    lang = i18n.interface_language()
    cards = _demo_cards(lang)
    n = len(cards)
    recordable = S.recordable(kind, n, 3)
    count = len(recordable) if recordable is not None else None
    return render_template("demo/board.html", kind=kind, cards=cards, k=3, lang=lang, kinds=DEMO_KINDS,
                           relation=i18n.text_for(demos.PROJECT_RELATION if kind != "pile" else {"pl": "oba należą do tej samej części pracy", "en": "both belong to the same part of the work"}, lang),
                           recordable_count=count, poset_count=len(S.posets(n)) if n <= S.MAX_ENUMERATION else None)


@bp.route("/demo/sob")
def demo_sob():
    lang = i18n.interface_language()
    items = [{"code": c, "label": i18n.text_for(lab, lang)} for c, lab in demos.REVIEW_STEPS]
    block = [items[i] for i in (0, 2, 4, 6)]
    return render_template("demo/sob.html", items=block, lang=lang, kinds=DEMO_KINDS,
                           relation=i18n.text_for({"pl": "jedno musi być gotowe, zanim drugie ma sens", "en": "one has to be in place before the other makes sense"}, lang))


@bp.route("/demo/tap")
def demo_tap():
    lang = i18n.interface_language()
    items = [{"code": c, "label": i18n.text_for(lab, lang)} for c, lab in demos.SOURCES]
    block = [items[i] for i in (0, 2, 4)] + [{"code": "ANCHOR", "label": i18n.text_for({"pl": "nic / nikt", "en": "nothing / no one"}, lang), "anchor": True}]
    designs = [d for d in B.design_library().values() if d["v"] <= 13]
    return render_template("demo/tap.html", cards=block, lang=lang, kinds=DEMO_KINDS, designs=designs,
                           criterion=i18n.text_for({"pl": "Ułóż źródła według tego, ile każde z nich mogłoby Ci teraz dać do pracy nad tekstem.",
                                                   "en": "Order the sources by how much each could give you for your text right now."}, lang))


# ---------------------------------------------------------------- starting a response


def _cookie_name(survey: Survey) -> str:
    return f"cs_{survey.id}"


def _choose_language(survey: Survey) -> str:
    langs = survey.languages
    asked = request.args.get("lang")
    if asked in langs:
        return asked
    if survey.settings.get("detect_browser_language", True) and request.accept_languages:
        best = request.accept_languages.best_match(langs)
        if best:
            return best
    return survey.default_language


def _new_response(survey: Survey, preview: bool = False) -> Response:
    r = Response(survey_id=survey.id, uuid=str(uuidlib.uuid4()), language=_choose_language(survey), status="started",
                 preview=preview, revision=survey.revision)
    r.state = {"occasion": 1, "index": 0, "step": 0}
    r.assignments = {}
    db.session.add(r)
    db.session.flush()
    return r


@bp.route("/s/<slug>")
def start(slug: str):
    survey = Survey.query.filter_by(slug=slug).first_or_404()
    lang = _choose_language(survey)
    if survey.status != "open":
        return render_template("public/closed.html", survey=survey, lang=lang), 410 if survey.status == "closed" else 404
    existing = request.cookies.get(_cookie_name(survey))
    if existing:
        r = Response.query.filter_by(uuid=existing, survey_id=survey.id).first()
        if r is not None and r.status == "started":
            return redirect(url_for("public.respond", uuid=r.uuid))
    if rate_limited("respondent_start", f"survey:{survey.id}"):
        abort(429)
    r = _new_response(survey)
    db.session.commit()
    resp = make_response(redirect(url_for("public.respond", uuid=r.uuid)))
    resp.set_cookie(_cookie_name(survey), r.uuid, max_age=COOKIE_DAYS * 86400, httponly=True, samesite="Lax",
                    secure=current_app.config["SESSION_COOKIE_SECURE"], path=current_app.config["URL_PREFIX"] or "/")
    return resp


# ---------------------------------------------------------------- the respondent's screens


def _load(uuid: str) -> tuple[Response, Survey]:
    r = Response.query.filter_by(uuid=uuid).first_or_404()
    survey = db.session.get(Survey, r.survey_id)
    if survey is None:
        abort(404)
    return r, survey


def _apply_language(r: Response, survey: Survey) -> str:
    asked = request.args.get("lang")
    if asked and asked in survey.languages and survey.settings.get("allow_language_switch", True):
        r.language = asked
    return r.language if r.language in survey.languages else survey.default_language


def _render_screen(survey: Survey, r: Response, screen: runtime.Screen, lang: str, errors=None, form_values=None):
    module = screen.module
    t = module["type"]
    ctx = dict(survey=survey, response=r, screen=screen, module=module, lang=lang, fallback=survey.default_language,
               progress=runtime.progress(survey, r), errors=errors or {}, values=form_values or {})
    answers = runtime.answers_of(r)
    if t == "form":
        from ..survey import conditions
        ctx["questions"] = [q for q in module["questions"]
                            if conditions.holds(q.get("condition"), answers, r.assignments) or _refers_same_form(q, module)]
        return render_template("blocks/form.html", **ctx)
    if t == "board":
        codes = [e["code"] for e in module["elements"]]
        elements = [{"code": e["code"], "label": i18n.text_for(e["label"], lang, survey.default_language)} for e in module["elements"]]
        order = runtime.board_order(r, module, screen.occasion)
        if screen.step == 1:
            pairs = runtime.confirmation_pairs(r, module, screen.occasion)
            ctx["pairs"] = [{"i": i, "j": j, "a": elements[i]["label"], "b": elements[j]["label"]} for i, j in pairs]
            return render_template("blocks/confirm.html", **ctx)
        from ..models import Arrangement
        row = Arrangement.query.filter_by(response_id=r.id, module_key=module["key"], occasion=screen.occasion).first()
        ctx.update(elements=elements, order=order, codes=codes, initial=(json.loads(row.placements_json) if row else None))
        return render_template("blocks/board.html", **ctx)
    if t in ("sob_blocks", "tap_blocks"):
        entry = runtime.schedule_for(r, module, screen.occasion, answers)[screen.step]
        name, variant = runtime.variant_of(module, answers)
        items = (variant or module).get("items", [])
        labels = {c["code"]: i18n.text_for(c["label"], lang, survey.default_language) for c in items}
        if module.get("anchor"):
            labels[module["anchor"]["code"]] = i18n.text_for(module["anchor"]["label"], lang, survey.default_language)
        attention_key = "tap.attention_first_default" if module.get("attention_position") == "first" else "tap.attention_default"
        labels["ATTN"] = i18n.text_for(module.get("attention_label") or {}, lang, survey.default_language) or i18n.t(attention_key, lang)
        cards = [{"code": c, "label": labels.get(c, c), "anchor": bool(module.get("anchor")) and c == module["anchor"]["code"],
                  "attention": c == "ATTN"} for c in entry["cards"]]
        criterion = (variant or {}).get("criterion") or module.get("criterion") or module.get("relation")
        panel = []
        by_key = {m["key"]: m for m in survey.modules}
        for name in module.get("panel_from", []):
            source = by_key.get(name)
            text = runtime.content_for(source, r, answers) if source else None
            if text:
                panel.append(text)
        ctx.update(cards=cards, entry=entry, criterion=criterion, panel=panel,
                   panel_label=module.get("panel_label"), anchor_note=module.get("anchor_note") if module.get("anchor") else None,
                   anchor_closes=bool(module.get("anchor") and module.get("anchor_closes")),
                   attention_position=module.get("attention_position", "last"))
        return render_template("blocks/sob.html" if t == "sob_blocks" else "blocks/tap.html", **ctx)
    if t == "stimulus":
        ctx["content"] = runtime.content_for(module, r, answers)
        return render_template("blocks/stimulus.html", **ctx)
    if t == "choice":
        if screen.step == 1:
            ctx["content"] = runtime.content_for(module, r, answers)
            return render_template("blocks/stimulus.html", **ctx)
        return render_template("blocks/choice.html", **ctx)
    if t == "debrief":
        ctx["content"] = runtime.content_for(module, r, answers)
        return render_template("blocks/debrief.html", **ctx)
    return render_template(f"blocks/{t}.html", **ctx)


def _refers_same_form(q, module) -> bool:
    """A question whose condition names another question of the same form is shown and toggled in the browser."""
    names = {x["name"] for x in module["questions"]}

    def walk(c):
        if not c:
            return False
        if "all" in c or "any" in c:
            return any(walk(x) for x in c.get("all", c.get("any", [])))
        if "not" in c:
            return walk(c["not"])
        return c.get("answer") in names

    return walk(q.get("condition"))


@bp.route("/r/<uuid>", methods=("GET", "POST"))
def respond(uuid: str):
    r, survey = _load(uuid)
    if r.status in ("withdrawn", "declined"):
        return render_template("public/withdrawn.html", survey=survey, lang=r.language, declined=(r.status == "declined"))
    if survey.status != "open" and not r.preview:
        return render_template("public/closed.html", survey=survey, lang=r.language), 410
    lang = _apply_language(r, survey)
    occasion = int(r.state.get("occasion", 1))
    if r.status == "submitted" and (occasion == 1 or r.retest_submitted_at is not None):
        return redirect(url_for("public.finished", uuid=uuid))
    screen = runtime.current_screen(survey, r)
    if screen is None or screen.module["type"] == "thanks":
        runtime.finish(r)
        if screen is not None:
            runtime.mark_shown(r, screen)
        db.session.commit()
        return redirect(url_for("public.finished", uuid=uuid))
    if request.method == "GET":
        runtime.mark_shown(r, screen)
        db.session.commit()
        return _render_screen(survey, r, screen, lang)

    if request.form.get("screen") != screen.key:
        db.session.commit()
        flash(i18n.t("flow.page_changed", lang), "error")
        return redirect(url_for("public.respond", uuid=uuid))
    module = screen.module
    t = module["type"]
    try:
        if t == "consent":
            if request.form.get("decision") != "agree":
                r.status = "declined"
                r.state = {}
                db.session.commit()
                return render_template("public/withdrawn.html", survey=survey, lang=lang, declined=True)
            r.consented = True
            runtime.advance(r)
        elif t in ("info", "stimulus", "debrief"):
            runtime.advance(r)
        elif t == "form":
            errors = runtime.submit_form(r, module, request.form)
            if errors:
                db.session.rollback()
                values = {q["name"]: (request.form.getlist(q["name"]) if q["type"] == "checkbox" else request.form.get(q["name"], ""))
                          for q in module["questions"]}
                return _render_screen(survey, r, screen, lang, errors=errors, form_values=values), 400
            runtime.advance(r)
        elif t == "board" and screen.step == 0:
            needs_confirm = runtime.submit_board(r, module, screen.occasion, request.form.get("placements_json", ""), request.form.get("display_order", ""))
            runtime.advance(r, to_step=1) if needs_confirm else runtime.advance(r)
        elif t == "board" and screen.step == 1:
            related = runtime.submit_confirm(r, module, screen.occasion, request.form)
            if related:
                labels = [i18n.text_for(e["label"], lang, survey.default_language) for e in module["elements"]]
                flash(i18n.t("board.draw_missing", lang, pairs="; ".join(f"{labels[i]} / {labels[j]}" for i, j in related)), "error")
                runtime.advance(r, to_step=0)
            else:
                runtime.advance(r)
        elif t in ("sob_blocks", "tap_blocks"):
            runtime.submit_block(r, module, screen.occasion, screen.step, request.form.get("result_json", ""),
                                 request.form.get("events_json", ""), request.form.get("gate"), request.form.get("block_ms"))
            if screen.step + 1 < screen.total_steps:
                runtime.advance(r, next_step=True)
            else:
                runtime.advance(r)
        elif t == "choice" and screen.step == 0:
            runtime.submit_choice(r, module, request.form.get("choice"))
            runtime.advance(r, next_step=True)
        elif t == "choice":
            runtime.advance(r)
        else:
            runtime.advance(r)
    except FlowError as exc:
        db.session.rollback()
        flash(i18n.t("flow." + exc.key, lang, **exc.kw), "error")
        return redirect(url_for("public.respond", uuid=uuid))
    runtime.mark_submitted(r, screen, request.form.get("client_ms"))
    following = runtime.current_screen(survey, r)
    if following is None or following.module["type"] == "thanks":
        runtime.finish(r)
    db.session.commit()
    return redirect(url_for("public.respond", uuid=uuid))


@bp.route("/r/<uuid>/done")
def finished(uuid: str):
    r, survey = _load(uuid)
    lang = _apply_language(r, survey)
    if r.status != "submitted":
        return redirect(url_for("public.respond", uuid=uuid))
    thanks = next((m for m in survey.modules if m["type"] == "thanks"), None)
    retest_url = None
    if survey.settings.get("retest") and (thanks or {}).get("show_retest_link", True) and r.retest_submitted_at is None:
        retest_url = url_for("public.retest", uuid=uuid)
    return render_template("public/finished.html", survey=survey, response=r, lang=lang, thanks=thanks, retest_url=retest_url,
                           retest_done=r.retest_submitted_at is not None)


@bp.route("/r/<uuid>/retest", methods=("GET", "POST"))
def retest(uuid: str):
    r, survey = _load(uuid)
    if not runtime.start_retest(survey, r):
        abort(404)
    db.session.commit()
    if r.retest_submitted_at is not None:
        return redirect(url_for("public.finished", uuid=uuid))
    return redirect(url_for("public.respond", uuid=uuid))


@bp.route("/r/<uuid>/withdraw", methods=("POST",))
def withdraw(uuid: str):
    r, survey = _load(uuid)
    lang = r.language
    if r.status != "withdrawn":
        runtime.withdraw(r)
        db.session.commit()
    resp = make_response(render_template("public/withdrawn.html", survey=survey, lang=lang, declined=False))
    resp.delete_cookie(_cookie_name(survey), path=current_app.config["URL_PREFIX"] or "/")
    return resp
