"""The Back button (returns to earlier screens with the answers given, closed by a consent, a
random assignment, a material and a module marked as closing the way back), criteria spread over
the blocks of a tap-order task, and the progress shown as a percentage."""
import csv
import io
import json
import re
from collections import Counter

from cardsurveys.models import BlockResponse, Response, ScreenTime
from cardsurveys.survey import editor
from cardsurveys.survey.export import export_files
from cardsurveys.survey.schema import validate_bundle

from .conftest import CARDS, SCREEN, answer_current, start, tap_order, unescape
from .test_flow import create
from .test_forms_paradata import browser_form

INITIAL = re.compile(r"data-initial='([^']*)'")
CRITERION = re.compile(r'<p class="criterion">(.*?)</p>', re.S)


def L(pl, en):
    return {"pl": pl, "en": en}


def back_bundle(allow_back=True):
    items = [{"code": f"S{i}", "label": L(f"Źródło {i}", f"Source {i}")} for i in range(1, 5)]
    return {"format": "cardsurveys-bundle", "version": 1,
            "survey": {"title": L("Powrót", "Back"), "languages": ["pl", "en"], "default_language": "pl", "allow_back": allow_back},
            "modules": [
                {"key": "consent", "type": "consent", "text": L("Zgoda.", "Consent.")},
                {"key": "intro", "type": "info", "text": L("Wstęp.", "Intro.")},
                {"key": "about", "type": "form", "questions": [
                    {"name": "level", "type": "radio", "required": True, "label": L("Poziom", "Level"),
                     "options": [{"value": "ma", "label": L("magisterskie", "master's")}, {"value": "phd", "label": L("doktorskie", "doctoral")}]}]},
                {"key": "order", "type": "tap_blocks", "criterion": L("Kryterium.", "Criterion."), "items": items,
                 "blocks": [["S1", "S2", "S3"], ["S2", "S3", "S4"]], "shuffle_blocks": False,
                 "anchor": {"code": "A0", "label": L("Nic", "Nothing")}, "anchor_closes": True},
                {"key": "arm", "type": "randomizer", "arms": [{"code": "A"}, {"code": "B"}]},
                {"key": "after", "type": "info", "text": L("Po losowaniu.", "After the draw.")},
                {"key": "judge", "type": "form", "lock": True, "questions": [
                    {"name": "verdict", "type": "yesno", "required": True, "label": L("Werdykt?", "Verdict?")}]},
                {"key": "last", "type": "form", "questions": [{"name": "note", "type": "text", "label": L("Uwagi", "Notes")}]},
                {"key": "thanks", "type": "thanks", "text": L("Dziękuję.", "Thank you.")},
            ]}


def shown(client, uuid):
    resp = client.get(f"/cards/r/{uuid}")
    if resp.status_code == 302:
        return "end", ""
    html = resp.get_data(as_text=True)
    return SCREEN.search(html).group(1), html


def press_back(client, uuid, key):
    return client.post(f"/cards/r/{uuid}/back", data={"screen": key})


def test_back_returns_to_earlier_screens_with_the_answers_given(app, client):
    sid, slug = create(app, back_bundle())
    uuid = start(client, slug)
    answer_current(client, uuid)
    key, html = shown(client, uuid)
    assert key == "intro:0:1" and 'form="backForm"' not in html  # the consent closes the way back
    answer_current(client, uuid)
    key, html = shown(client, uuid)
    assert key == "about:0:1" and 'form="backForm"' in html and "Postęp: " in html
    press_back(client, uuid, key)
    assert shown(client, uuid)[0] == "intro:0:1"
    answer_current(client, uuid)
    answer_current(client, uuid, {"level": "phd"})
    key, html = shown(client, uuid)
    assert key == "order:0:1"
    cards = json.loads(unescape(CARDS.search(html).group(1)))
    full = tap_order(cards, closes=True)
    answer_current(client, uuid)
    key, html = shown(client, uuid)
    assert key == "order:1:1"
    press_back(client, uuid, key)
    key, html = shown(client, uuid)
    assert key == "order:0:1"
    assert json.loads(unescape(INITIAL.search(html).group(1))) == full
    shorter = tap_order(cards, closes=True, keep=1)
    client.post(f"/cards/r/{uuid}", data={"screen": key, "client_ms": "500", "result_json": json.dumps(shorter),
                                          "events_json": "[]", "block_ms": "800"})
    key, _ = shown(client, uuid)
    assert key == "order:1:1"
    press_back(client, uuid, key)
    key, _ = shown(client, uuid)
    press_back(client, uuid, key)
    key, html = shown(client, uuid)
    assert key == "about:0:1" and 'value="phd" checked' in html
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid).first()
        row = BlockResponse.query.filter_by(response_id=r.id, module_key="order", position=0).first()
        assert json.loads(row.result_json) == shorter
        assert ScreenTime.query.filter_by(response_id=r.id, screen_key="order:0:1").first().revisions == 1
        assert ScreenTime.query.filter_by(response_id=r.id, screen_key="order:1:1").first().revisions == 0
    for _ in range(4):
        if shown(client, uuid)[0] == "after:0:1":
            break
        answer_current(client, uuid)
    key, html = shown(client, uuid)
    assert key == "after:0:1" and 'form="backForm"' not in html  # no return past the random assignment
    press_back(client, uuid, key)
    assert shown(client, uuid)[0] == "after:0:1"
    answer_current(client, uuid)
    key, html = shown(client, uuid)
    assert key == "judge:0:1" and 'form="backForm"' in html
    answer_current(client, uuid)
    key, html = shown(client, uuid)
    assert key == "last:0:1" and 'form="backForm"' not in html  # the judgment closes the way back
    with app.app_context():
        files = export_files(_survey(sid))
    screens = list(csv.DictReader(io.StringIO(files["screens.csv"])))
    assert {r["screen_key"]: r["revisions"] for r in screens}["order:0:1"] == "2"


def _survey(sid):
    from cardsurveys.extensions import db
    from cardsurveys.models import Survey
    return db.session.get(Survey, sid)


def test_without_the_setting_there_is_no_back_button(app, client):
    sid, slug = create(app, back_bundle(allow_back=False))
    uuid = start(client, slug)
    answer_current(client, uuid)
    answer_current(client, uuid)
    key, html = shown(client, uuid)
    assert key == "about:0:1" and 'form="backForm"' not in html and "Postęp: " in html
    press_back(client, uuid, key)
    assert shown(client, uuid)[0] == "about:0:1"


def criteria_bundle():
    items = [{"code": f"S{i}", "label": L(f"Źródło {i}", f"Source {i}")} for i in range(1, 9)]
    criteria = [L(f"Kryterium {i}.", f"Criterion {i}.") for i in range(1, 8)]
    return {"format": "cardsurveys-bundle", "version": 1,
            "survey": {"title": L("Kryteria", "Criteria"), "languages": ["pl", "en"], "default_language": "pl"},
            "modules": [
                {"key": "consent", "type": "consent", "text": L("Zgoda.", "Consent.")},
                {"key": "value", "type": "tap_blocks", "criterion": L("Kryterium ogólne.", "General criterion."),
                 "criteria": criteria, "items": items, "design": "v8_k4_lambda3", "duplicates": 1, "attention": 1,
                 "anchor": {"code": "A0", "label": L("Nic", "Nothing")}, "anchor_closes": True},
                {"key": "thanks", "type": "thanks", "text": L("Dziękuję.", "Thank you.")},
            ]}


def test_criteria_are_spread_evenly_over_the_blocks_and_recorded(app, client):
    sid, slug = create(app, criteria_bundle())
    uuid = start(client, slug)
    answer_current(client, uuid)
    seen = []
    for _ in range(20):
        key, html = shown(client, uuid)
        if not key.startswith("value:"):
            break
        text = CRITERION.search(html).group(1).strip()
        assert shown(client, uuid)[1].count(text) >= 1 and CRITERION.search(shown(client, uuid)[1]).group(1).strip() == text
        seen.append(text)
        answer_current(client, uuid)
    assert len(seen) == 16  # 14 design blocks, one repeated block, one attention block
    with app.app_context():
        files = export_files(_survey(sid))
    rows = list(csv.DictReader(io.StringIO(files["blocks.csv"])))
    assert len(rows) == 16
    base = [r for r in rows if r["repeat_of"] == "" and r["attention"] == "0"]
    assert Counter(r["criterion"] for r in base) == Counter({str(i): 2 for i in range(7)})
    by_block = {r["design_block"]: r["criterion"] for r in base}
    repeat = [r for r in rows if r["repeat_of"] != ""][0]
    assert repeat["criterion"] == by_block[repeat["repeat_of"]]
    assert all(seen[int(r["position"])] == f"Kryterium {int(r['criterion']) + 1}." for r in rows)
    book = json.loads(files["description.json"])["codebook"]
    assert len([m for m in book["modules"] if m["key"] == "value"][0]["criteria"]) == 7


def test_criteria_and_the_lock_are_checked_and_kept_by_the_editor():
    b = criteria_bundle()
    b["survey"]["allow_back"] = True
    b["modules"][1]["lock"] = True
    assert not validate_bundle(b, ["pl", "en"])["errors"]
    b["modules"][1]["criteria"][3] = {"pl": "Kryterium 4."}
    warnings = validate_bundle(b, ["pl", "en"])["warnings"]
    assert any(w["code"] == "missing_translation" and w.get("path") == "criteria.3" for w in warnings)
    langs = ["pl", "en"]
    tap = criteria_bundle()["modules"][1]
    tap["lock"] = True
    again = editor.from_form(tap, browser_form(editor.to_form(tap, langs)), langs)
    assert again["criteria"] == tap["criteria"] and again["lock"] is True
