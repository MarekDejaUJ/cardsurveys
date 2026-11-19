"""Form screens with the respondent's material, questions in random order, links in the
question labels and paradata of the screen (opened links, time away from the page)."""
import csv
import io
import json
import re

from cardsurveys.extensions import db
from cardsurveys.models import Answer, Response, ScreenTime, Survey
from cardsurveys.survey import editor
from cardsurveys.survey.export import export_files
from cardsurveys.survey.runtime import read_paradata
from cardsurveys.survey.schema import validate_bundle

from .conftest import SCREEN, answer_current, start
from .test_flow import create


def L(pl, en):
    return {"pl": pl, "en": en}


OPTIONS = [{"value": "ok", "label": L("poprawna", "correct")}, {"value": "err", "label": L("z błędem", "with an error")},
           {"value": "none", "label": L("nie istnieje", "does not exist")}]
REFS = ["K1", "K2", "K3", "K4", "K5"]


def checking_bundle(paradata=True):
    questions = [{"name": k, "type": "radio", "required": True, "options": OPTIONS,
                  "label": L(f"Pozycja {k}. https://doi.org/10.0000/{k.lower()}", f"Reference {k}. https://doi.org/10.0000/{k.lower()}")}
                 for k in REFS]
    questions.append({"name": "checked", "type": "yesno", "required": True,
                      "label": L("Czy zdarzyło Ci się sprawdzać pozycje poza ankietą?", "Did you check the references outside the survey?")})
    return {"format": "cardsurveys-bundle", "version": 1,
            "survey": {"title": L("Sprawdzanie", "Checking"), "languages": ["pl", "en"], "default_language": "pl"},
            "modules": [
                {"key": "consent", "type": "consent", "text": L("Zgoda.", "Consent.")},
                {"key": "arm", "type": "randomizer", "arms": [{"code": "A"}, {"code": "B"}]},
                {"key": "aid", "type": "stimulus", "arm_of": "arm", "prompt": L("Przeczytaj.", "Read."),
                 "contents": {"A": {"*": L("Poradnik A.", "Guide A.")}, "B": {"*": L("Odpowiedź B.", "Answer B.")}}},
                {"key": "judge", "type": "form", "title": L("Ocena", "Judgment"), "questions": questions,
                 "panel_from": ["aid"], "panel_label": L("Twój materiał", "Your material"),
                 "shuffle_questions": REFS, "paradata": paradata},
                {"key": "thanks", "type": "thanks", "text": L("Dziękuję.", "Thank you.")},
            ]}


def to_judgment(client, uuid):
    for _ in range(5):
        html = client.get(f"/cards/r/{uuid}").get_data(as_text=True)
        if 'name="checked"' in html:
            return html
        answer_current(client, uuid)
    raise AssertionError("judgment screen not reached")


def test_form_shows_the_material_links_and_a_random_order_with_the_fixed_question_last(app, client):
    sid, slug = create(app, checking_bundle())
    orders = set()
    for _ in range(8):
        client = app.test_client()  # a new browser for every respondent
        uuid = start(client, slug, lang="en")
        html = to_judgment(client, uuid)
        assert 'class="aid-panel"' in html and ("Guide A." in html or "Answer B." in html)
        assert '<a href="https://doi.org/10.0000/k1" target="_blank"' in html
        assert 'data-paradata="1"' in html and 'name="paradata_json"' in html
        shown = re.findall(r'name="(K\d|checked)" value="(?:ok|yes)"', html)
        assert sorted(shown[:-1]) == REFS and shown[-1] == "checked"
        assert shown == re.findall(r'name="(K\d|checked)" value="(?:ok|yes)"', client.get(f"/cards/r/{uuid}").get_data(as_text=True))
        orders.add(tuple(shown))
    assert len(orders) > 1


def test_paradata_and_question_order_are_stored_and_exported(app, client):
    sid, slug = create(app, checking_bundle())
    uuid = start(client, slug, lang="en")
    html = to_judgment(client, uuid)
    key = SCREEN.search(html).group(1)
    first = json.dumps({"leaves": 1, "away_ms": 4000, "links": [["https://doi.org/10.0000/k1", 1500]]})
    resp = client.post(f"/cards/r/{uuid}", data={"screen": key, "K1": "ok", "paradata_json": first})
    assert resp.status_code == 400
    assert "away_ms" in resp.get_data(as_text=True)  # the browser continues from the counts of the refused attempt
    data = {k: "none" for k in REFS}
    data.update(screen=key, checked="yes",
                paradata_json=json.dumps({"leaves": 2, "away_ms": 9000, "links": [["https://doi.org/10.0000/k1", 1500],
                                                                                  ["https://doi.org/10.0000/k3", 6000]]}))
    assert client.post(f"/cards/r/{uuid}", data=data).status_code == 302
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid).first()
        row = ScreenTime.query.filter_by(response_id=r.id, module_key="judge").one()
        assert row.leaves == 2 and row.away_ms == 9000 and len(json.loads(row.links_json)) == 2
        order = json.loads(row.question_order_json)
        assert sorted(order[:-1]) == REFS and order[-1] == "checked"
        assert {a.name: json.loads(a.value) for a in Answer.query.filter_by(response_id=r.id).all()}["checked"] == "yes"
        files = export_files(db.session.get(Survey, sid))
    screens = list(csv.DictReader(io.StringIO(files["screens.csv"])))
    judge = [s for s in screens if s["module_key"] == "judge"][0]
    assert judge["leaves"] == "2" and judge["away_ms"] == "9000" and "k3" in judge["links"]
    assert judge["question_order"].split("|")[-1] == "checked"
    other = [s for s in screens if s["module_key"] == "consent"][0]
    assert other["leaves"] == "" and other["links"] == "" and other["question_order"] == ""


def test_a_form_without_paradata_stores_none(app, client):
    sid, slug = create(app, checking_bundle(paradata=False))
    uuid = start(client, slug, lang="en")
    html = to_judgment(client, uuid)
    assert 'data-paradata="1"' not in html and 'name="paradata_json"' not in html
    data = {k: "ok" for k in REFS}
    data.update(screen=SCREEN.search(html).group(1), checked="no", paradata_json=json.dumps({"leaves": 5}))
    assert client.post(f"/cards/r/{uuid}", data=data).status_code == 302
    with app.app_context():
        row = ScreenTime.query.filter_by(module_key="judge").one()
        assert row.leaves is None and row.links_json is None and row.question_order_json is not None


def test_malformed_paradata_counts_as_nothing():
    assert read_paradata("not json") == (0, 0, [])
    assert read_paradata(json.dumps({"leaves": -3, "away_ms": "x", "links": [["a", 5], [1, 2], "b"]})) == (0, 0, [["a", 5]])
    assert read_paradata(json.dumps({"leaves": 3, "away_ms": 120, "links": [["u" * 900, 10]] * 300}))[2][0][0] == "u" * 500
    assert len(read_paradata(json.dumps({"links": [["u", 1]] * 300}))[2]) == 200


def test_schema_checks_the_material_and_the_shuffled_questions():
    b = checking_bundle()
    judge = b["modules"][3]
    judge["panel_from"] = ["nowhere"]
    judge["shuffle_questions"] = ["K1", "K9"]
    codes = [m["code"] for m in validate_bundle(b, ["pl", "en"])["errors"]]
    assert "panel_unknown_module" in codes and "shuffle_unknown_question" in codes


def browser_form(values):
    """The editor form as a browser sends it: a ticked box as 'on', an unticked box left out."""
    return {k: ("on" if v is True else str(v)) for k, v in values.items() if v is not False}


def test_the_editor_keeps_every_field_of_a_form_and_a_tap_task():
    langs = ["pl", "en"]
    judge = checking_bundle()["modules"][3]
    again = editor.from_form(judge, browser_form(editor.to_form(judge, langs)), langs)
    for field in ("panel_from", "panel_label", "shuffle_questions", "paradata", "questions"):
        assert again[field] == judge[field], field
    tap = {"key": "value", "type": "tap_blocks", "criterion": L("Kryterium.", "Criterion."),
           "items": [{"code": c, "label": L(c, c)} for c in ("A", "B", "C")], "blocks": [["A", "B", "C"]],
           "anchor": {"code": "ANC", "label": L("Nic", "Nothing")}, "anchor_closes": True,
           "anchor_note": L("Opis.", "Note."), "attention": 1, "attention_position": "first",
           "attention_label": L("Pierwsza", "First"), "panel_from": ["aid"], "panel_label": L("Materiał", "Material")}
    again = editor.from_form(tap, browser_form(editor.to_form(tap, langs)), langs)
    for field in ("anchor_closes", "anchor_note", "attention_position", "panel_from", "panel_label", "anchor"):
        assert again[field] == tap[field], field
