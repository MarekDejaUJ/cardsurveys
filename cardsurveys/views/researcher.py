"""The researcher's studio: surveys, the module editor, preview, monitor and exports."""
from __future__ import annotations

import copy
import json

from flask import Blueprint, Response as FlaskResponse, abort, current_app, flash, redirect, render_template, request, url_for

from .. import i18n
from ..engine import blocks as B
from ..extensions import db
from ..models import Allocation, Response, Survey, utcnow
from ..security import current_user, login_required
from ..seeds import demos
from ..survey import bundle as bundles
from ..survey import editor as ED
from ..survey.export import export_files, export_zip, monitor
from ..survey.schema import MODULE_TYPES, blocking_for_publish, new_bundle, validate_bundle
from ..survey.skeletons import skeleton

bp = Blueprint("researcher", __name__)


def _survey(survey_id: int) -> Survey:
    survey = db.session.get(Survey, survey_id)
    if survey is None:
        abort(404)
    user = current_user()
    if survey.owner_id != user.id and not user.is_admin:
        abort(403)
    return survey


def _registry() -> list[str]:
    return current_app.config["LANGUAGES"]


def _store(survey: Survey, definition: dict) -> bool:
    try:
        bundles.replace_definition(survey, definition, _registry())
    except bundles.BundleError as exc:
        for m in exc.messages[:12]:
            flash(_msg(m), "error")
        db.session.rollback()
        return False
    db.session.commit()
    return True


def _msg(m: dict) -> str:
    from ..templating import message_text
    return message_text(m)


@bp.route("/")
@login_required
def dashboard():
    user = current_user()
    surveys = Survey.query.filter_by(owner_id=user.id).order_by(Survey.updated_at.desc()).all()
    counts = {s.id: Response.query.filter_by(survey_id=s.id, preview=False).count() for s in surveys}
    return render_template("researcher/dashboard.html", surveys=surveys, counts=counts, templates=demos.all_demos())


@bp.route("/new", methods=("POST",))
@login_required
def new_survey():
    user = current_user()
    template = request.form.get("template", "blank")
    languages = [c for c in request.form.getlist("languages") if c in _registry()] or list(_registry())
    if template == "blank":
        default = languages[0]
        title = {code: i18n.t("studio.untitled", code) for code in languages}
        bundle = new_bundle(title, languages, default)
        bundle["modules"] = [skeleton("consent", "consent", languages, [], []), skeleton("thanks", "thanks", languages, [], [])]
    else:
        found = dict(demos.all_demos()).get(template)
        if found is None:
            abort(404)
        bundle = copy.deepcopy(found)
    survey = bundles.create_from_bundle(user, bundle, _registry())
    db.session.commit()
    return redirect(url_for("researcher.survey_page", survey_id=survey.id))


@bp.route("/import", methods=("GET", "POST"))
@login_required
def import_bundle():
    if request.method == "POST":
        upload = request.files.get("bundle")
        text = upload.read().decode("utf-8", errors="replace") if upload and upload.filename else request.form.get("bundle_text", "")
        try:
            data = bundles.parse_bundle_text(text)
            survey = bundles.create_from_bundle(current_user(), data, _registry())
        except bundles.BundleError as exc:
            return render_template("researcher/import.html", messages=exc.messages, text=text[:20000]), 400
        db.session.commit()
        flash(i18n.t("studio.imported"), "ok")
        return redirect(url_for("researcher.survey_page", survey_id=survey.id))
    return render_template("researcher/import.html", messages=[], text="")


@bp.route("/surveys/<int:survey_id>")
@login_required
def survey_page(survey_id: int):
    survey = _survey(survey_id)
    result = validate_bundle(survey.definition, _registry())
    live = Response.query.filter_by(survey_id=survey.id, preview=False).count()
    return render_template("researcher/survey.html", survey=survey, result=result, blocking=blocking_for_publish(result),
                           live=live, module_types=MODULE_TYPES)


@bp.route("/surveys/<int:survey_id>/settings", methods=("GET", "POST"))
@login_required
def survey_settings(survey_id: int):
    survey = _survey(survey_id)
    definition = survey.definition
    if request.method == "POST":
        langs = [c for c in request.form.getlist("languages") if c in _registry()]
        if not langs:
            flash(i18n.t("studio.need_language"), "error")
            return redirect(request.url)
        s = definition["survey"]
        s["languages"] = langs
        default = request.form.get("default_language")
        s["default_language"] = default if default in langs else langs[0]
        s["title"] = ED.i18n_from(request.form, "title", langs)
        desc = ED.i18n_from(request.form, "description", langs)
        s["description"] = desc
        for flag in ("detect_browser_language", "allow_language_switch", "retest"):
            s[flag] = request.form.get(flag) == "on"
        if _store(survey, definition):
            flash(i18n.t("studio.saved"), "ok")
            return redirect(url_for("researcher.survey_page", survey_id=survey.id))
    return render_template("researcher/settings.html", survey=survey, s=definition["survey"])


@bp.route("/surveys/<int:survey_id>/modules/add", methods=("POST",))
@login_required
def add_module(survey_id: int):
    survey = _survey(survey_id)
    mtype = request.form.get("type")
    if mtype not in MODULE_TYPES:
        abort(400)
    definition = survey.definition
    key = bundles.unique_module_key(survey, mtype)
    answers = [q["name"] for m in survey.modules if m["type"] == "form" for q in m["questions"]]
    randomizers = [m["key"] for m in survey.modules if m["type"] == "randomizer"]
    module = skeleton(mtype, key, survey.languages, answers, randomizers)
    position = request.form.get("position", "")
    modules = definition["modules"]
    thanks_at = next((i for i, m in enumerate(modules) if m["type"] == "thanks"), len(modules))
    idx = int(position) if position.isdigit() and int(position) <= len(modules) else thanks_at
    modules.insert(idx, module)
    if _store(survey, definition):
        return redirect(url_for("researcher.edit_module", survey_id=survey.id, key=key))
    return redirect(url_for("researcher.survey_page", survey_id=survey.id))


@bp.route("/surveys/<int:survey_id>/modules/<key>", methods=("GET", "POST"))
@login_required
def edit_module(survey_id: int, key: str):
    survey = _survey(survey_id)
    definition = survey.definition
    try:
        idx = bundles.module_index(survey, key)
    except KeyError:
        abort(404)
    module = definition["modules"][idx]
    langs = survey.languages
    problem = None
    if request.method == "POST":
        try:
            if request.form.get("mode") == "json":
                new = json.loads(request.form.get("module_json", ""))
                if not isinstance(new, dict):
                    raise ValueError
            else:
                new = ED.from_form(module, request.form, langs)
            new_key = (request.form.get("new_key") or "").strip()
            if new_key and new_key != key:
                new["key"] = new_key
            definition["modules"][idx] = new
            if _store(survey, definition):
                flash(i18n.t("studio.saved"), "ok")
                return redirect(url_for("researcher.edit_module", survey_id=survey.id, key=new.get("key", key)))
        except ED.EditorError as exc:
            problem = exc
        except (ValueError, json.JSONDecodeError):
            flash(i18n.t("studio.json_invalid"), "error")
    values = ED.to_form(module, langs)
    result = validate_bundle(survey.definition, _registry())
    messages = [m for m in result["errors"] + result["warnings"] if m.get("where", "").startswith(f"module {key}")]
    return render_template("researcher/module.html", survey=survey, module=module, values=values, spec=ED.SPECS[module["type"]] + ED.COMMON,
                           langs=langs, problem=problem, messages=messages, module_json=json.dumps(module, ensure_ascii=False, indent=2),
                           designs=list(B.design_library().values()), content_rows=ED.contents_rows(module))


@bp.route("/surveys/<int:survey_id>/modules/<key>/move", methods=("POST",))
@login_required
def move_module(survey_id: int, key: str):
    survey = _survey(survey_id)
    definition = survey.definition
    idx = bundles.module_index(survey, key)
    direction = -1 if request.form.get("direction") == "up" else 1
    target = idx + direction
    mods = definition["modules"]
    if 0 <= target < len(mods):
        mods[idx], mods[target] = mods[target], mods[idx]
        _store(survey, definition)
    return redirect(url_for("researcher.survey_page", survey_id=survey.id))


@bp.route("/surveys/<int:survey_id>/modules/<key>/delete", methods=("POST",))
@login_required
def delete_module(survey_id: int, key: str):
    survey = _survey(survey_id)
    definition = survey.definition
    idx = bundles.module_index(survey, key)
    definition["modules"].pop(idx)
    if not _store(survey, definition):
        flash(i18n.t("studio.delete_blocked"), "error")
    return redirect(url_for("researcher.survey_page", survey_id=survey.id))


@bp.route("/surveys/<int:survey_id>/modules/<key>/question", methods=("POST",))
@login_required
def edit_question(survey_id: int, key: str):
    survey = _survey(survey_id)
    definition = survey.definition
    idx = bundles.module_index(survey, key)
    module = definition["modules"][idx]
    if module["type"] != "form":
        abort(400)
    action = request.form.get("action")
    pos = request.form.get("index", "")
    questions = module["questions"]
    try:
        if action == "delete" and pos.isdigit():
            questions.pop(int(pos))
        elif action == "up" and pos.isdigit() and int(pos) > 0:
            i = int(pos)
            questions[i - 1], questions[i] = questions[i], questions[i - 1]
        elif action == "save":
            q = ED.question_from_form(request.form, survey.languages)
            if pos.isdigit() and int(pos) < len(questions):
                questions[int(pos)] = q
            else:
                questions.append(q)
    except ED.EditorError as exc:
        flash(i18n.t("editor." + exc.problem) + f" ({exc.field})", "error")
        return redirect(url_for("researcher.edit_module", survey_id=survey.id, key=key))
    if not questions:
        flash(i18n.t("studio.form_needs_question"), "error")
        return redirect(url_for("researcher.edit_module", survey_id=survey.id, key=key))
    if _store(survey, definition):
        flash(i18n.t("studio.saved"), "ok")
    return redirect(url_for("researcher.edit_module", survey_id=survey.id, key=key))


@bp.route("/surveys/<int:survey_id>/modules/<key>/contents", methods=("POST",))
@login_required
def edit_contents(survey_id: int, key: str):
    survey = _survey(survey_id)
    definition = survey.definition
    idx = bundles.module_index(survey, key)
    module = definition["modules"][idx]
    if module["type"] not in ("stimulus", "choice", "debrief"):
        abort(400)
    definition["modules"][idx] = ED.contents_from_form(module, request.form, survey.languages)
    if _store(survey, definition):
        flash(i18n.t("studio.saved"), "ok")
    return redirect(url_for("researcher.edit_module", survey_id=survey.id, key=key))


@bp.route("/surveys/<int:survey_id>/bundle", methods=("GET", "POST"))
@login_required
def edit_bundle(survey_id: int):
    survey = _survey(survey_id)
    if request.method == "POST":
        try:
            data = bundles.parse_bundle_text(request.form.get("bundle_text", ""))
            bundles.replace_definition(survey, data, _registry())
            db.session.commit()
            flash(i18n.t("studio.saved"), "ok")
            return redirect(url_for("researcher.survey_page", survey_id=survey.id))
        except bundles.BundleError as exc:
            db.session.rollback()
            return render_template("researcher/bundle.html", survey=survey, text=request.form.get("bundle_text", ""), messages=exc.messages), 400
    return render_template("researcher/bundle.html", survey=survey, text=json.dumps(bundles.export_bundle(survey), ensure_ascii=False, indent=2), messages=[])


@bp.route("/surveys/<int:survey_id>/bundle.json")
@login_required
def download_bundle(survey_id: int):
    survey = _survey(survey_id)
    return FlaskResponse(json.dumps(bundles.export_bundle(survey), ensure_ascii=False, indent=2), mimetype="application/json",
                         headers={"Content-Disposition": f"attachment; filename=survey-{survey.slug}.json"})


@bp.route("/surveys/<int:survey_id>/status", methods=("POST",))
@login_required
def change_status(survey_id: int):
    survey = _survey(survey_id)
    action = request.form.get("action")
    if action == "publish":
        blocking = blocking_for_publish(validate_bundle(survey.definition, _registry()))
        if blocking:
            flash(i18n.t("studio.cannot_publish"), "error")
            return redirect(url_for("researcher.survey_page", survey_id=survey.id))
        survey.status = "open"
        survey.published_at = survey.published_at or utcnow()
        survey.closed_at = None
    elif action == "close":
        survey.status = "closed"
        survey.closed_at = utcnow()
    elif action == "draft":
        survey.status = "draft"
    db.session.commit()
    return redirect(url_for("researcher.survey_page", survey_id=survey.id))


@bp.route("/surveys/<int:survey_id>/duplicate", methods=("POST",))
@login_required
def duplicate(survey_id: int):
    survey = _survey(survey_id)
    copy_bundle = bundles.export_bundle(survey)
    copy_bundle["survey"].pop("slug", None)
    for code, text in list(copy_bundle["survey"]["title"].items()):
        copy_bundle["survey"]["title"][code] = text + " " + i18n.t("studio.copy_suffix", code)
    new = bundles.create_from_bundle(current_user(), copy_bundle, _registry())
    db.session.commit()
    return redirect(url_for("researcher.survey_page", survey_id=new.id))


@bp.route("/surveys/<int:survey_id>/delete", methods=("POST",))
@login_required
def delete_survey(survey_id: int):
    survey = _survey(survey_id)
    if request.form.get("confirm") != survey.slug:
        flash(i18n.t("studio.delete_confirm_mismatch"), "error")
        return redirect(url_for("researcher.survey_page", survey_id=survey.id))
    Allocation.query.filter_by(survey_id=survey.id).delete()
    db.session.delete(survey)
    db.session.commit()
    flash(i18n.t("studio.deleted"), "ok")
    return redirect(url_for("researcher.dashboard"))


@bp.route("/surveys/<int:survey_id>/preview", methods=("POST",))
@login_required
def preview(survey_id: int):
    survey = _survey(survey_id)
    from .public import _new_response
    r = _new_response(survey, preview=True)
    db.session.commit()
    return redirect(url_for("public.respond", uuid=r.uuid))


@bp.route("/surveys/<int:survey_id>/monitor")
@login_required
def monitor_page(survey_id: int):
    survey = _survey(survey_id)
    return render_template("researcher/monitor.html", survey=survey, data=monitor(survey))


@bp.route("/surveys/<int:survey_id>/export.zip")
@login_required
def download_zip(survey_id: int):
    survey = _survey(survey_id)
    return FlaskResponse(export_zip(survey), mimetype="application/zip",
                         headers={"Content-Disposition": f"attachment; filename=cardsurveys-{survey.slug}.zip"})


@bp.route("/surveys/<int:survey_id>/export/<path:name>")
@login_required
def download_file(survey_id: int, name: str):
    survey = _survey(survey_id)
    files = export_files(survey)
    if name not in files:
        abort(404)
    mimetype = "application/json" if name.endswith(".json") else "text/csv"
    return FlaskResponse(files[name], mimetype=mimetype + "; charset=utf-8",
                         headers={"Content-Disposition": f"attachment; filename={name.replace('/', '_')}"})


@bp.route("/surveys/<int:survey_id>/responses/delete", methods=("POST",))
@login_required
def delete_responses(survey_id: int):
    survey = _survey(survey_id)
    which = request.form.get("which")
    q = Response.query.filter_by(survey_id=survey.id)
    if which == "preview":
        q = q.filter_by(preview=True)
        Allocation.query.filter_by(survey_id=survey.id, preview=True).delete()
    elif which == "all" and request.form.get("confirm") == survey.slug:
        Allocation.query.filter_by(survey_id=survey.id).delete()
    else:
        flash(i18n.t("studio.delete_confirm_mismatch"), "error")
        return redirect(url_for("researcher.monitor_page", survey_id=survey.id))
    for r in q.all():
        db.session.delete(r)
    db.session.commit()
    flash(i18n.t("studio.responses_deleted"), "ok")
    return redirect(url_for("researcher.monitor_page", survey_id=survey.id))
