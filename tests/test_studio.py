import json
import re

from cardsurveys.extensions import db
from cardsurveys.models import Response, Survey

from .conftest import login, make_user, run_to_end, start


def setup_researcher(app, client, email="r1@uj.edu.pl"):
    make_user(app, email)
    login(client, email)


def new_blank(app, client, langs=("pl", "en")):
    resp = client.post("/cards/studio/new", data={"template": "blank", "languages": list(langs)})
    assert resp.status_code == 302
    return int(re.search(r"/surveys/(\d+)", resp.headers["Location"]).group(1))


def test_dashboard_and_templates(app, client):
    setup_researcher(app, client)
    assert client.get("/cards/studio/").status_code == 200
    resp = client.post("/cards/studio/new", data={"template": "experiment", "languages": ["pl", "en"]})
    sid = int(re.search(r"/surveys/(\d+)", resp.headers["Location"]).group(1))
    page = client.get(f"/cards/studio/surveys/{sid}").get_data(as_text=True)
    assert "aid_choice" in page and "judge" in page
    for key in ("consent", "context", "arm", "aid", "aid_choice", "judge", "debrief", "thanks"):
        assert client.get(f"/cards/studio/surveys/{sid}/modules/{key}").status_code == 200
    assert client.get(f"/cards/studio/surveys/{sid}/monitor").status_code == 200
    assert client.get(f"/cards/studio/surveys/{sid}/settings").status_code == 200
    assert client.get(f"/cards/studio/surveys/{sid}/bundle").status_code == 200


def test_build_a_survey_in_the_editor(app, client):
    setup_researcher(app, client)
    sid = new_blank(app, client)
    resp = client.post(f"/cards/studio/surveys/{sid}/modules/add", data={"type": "tap_blocks"})
    assert resp.status_code == 302
    form = {
        "mode": "form", "new_key": "value",
        "title__pl": "Wartość", "title__en": "Value",
        "criterion__pl": "Ułóż według wartości.", "criterion__en": "Order by value.",
        "items": "\n".join(f"S{i} | źródło {i} | source {i}" for i in range(1, 9)),
        "design": "v8_k4_lambda3",
        "anchor": "ANCHOR | nic / nikt | nothing / no one",
        "gate_question__pl": "Czy masz pewność?", "gate_question__en": "Were you sure?",
        "gate_options": "yes | tak | yes\nno | nie | no",
        "duplicates": "1", "attention": "1",
        "attention_label__pl": "Połóż na końcu", "attention_label__en": "Place last",
        "shuffle_blocks": "on", "shuffle_cards": "on",
    }
    resp = client.post(f"/cards/studio/surveys/{sid}/modules/tap_blocks", data=form)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/modules/value")
    with app.app_context():
        s = db.session.get(Survey, sid)
        m = next(x for x in s.modules if x["key"] == "value")
        assert m["design"] == "v8_k4_lambda3" and len(m["items"]) == 8 and m["anchor"]["label"]["en"] == "nothing / no one"
        assert m["gate"]["options"][1] == {"value": "no", "label": {"pl": "nie", "en": "no"}}
    resp = client.post(f"/cards/studio/surveys/{sid}/modules/add", data={"type": "form", "position": "1"})
    with app.app_context():
        key = next(x["key"] for x in db.session.get(Survey, sid).modules if x["type"] == "form")
    q = {"action": "save", "index": "", "name": "level", "qtype": "radio", "required": "on",
         "label__pl": "Poziom", "label__en": "Level", "options": "ma | magisterskie | master's\nphd | doktoranckie | doctoral"}
    assert client.post(f"/cards/studio/surveys/{sid}/modules/{key}/question", data=q).status_code == 302
    with app.app_context():
        form_mod = next(x for x in db.session.get(Survey, sid).modules if x["type"] == "form")
        assert [qq["name"] for qq in form_mod["questions"]] == [f"{key}_q1", "level"]
    # titles are still placeholders in both languages: the survey can be published
    resp = client.post(f"/cards/studio/surveys/{sid}/status", data={"action": "publish"})
    with app.app_context():
        s = db.session.get(Survey, sid)
        assert s.status == "open", client.get(f"/cards/studio/surveys/{sid}").get_data(as_text=True)[:3000]
        slug = s.slug
    uuid = start(app.test_client(), slug)
    respondent = app.test_client()
    uuid = start(respondent, slug)
    keys = run_to_end(respondent, uuid)
    assert sum(1 for k in keys if k.startswith("value:")) == 14 + 2


def test_missing_translation_blocks_publishing(app, client):
    setup_researcher(app, client)
    sid = new_blank(app, client)
    client.post(f"/cards/studio/surveys/{sid}/modules/add", data={"type": "info"})
    with app.app_context():
        key = next(x["key"] for x in db.session.get(Survey, sid).modules if x["type"] == "info")
    client.post(f"/cards/studio/surveys/{sid}/modules/{key}", data={"mode": "form", "title__pl": "Info", "text__pl": "Tylko po polsku."})
    client.post(f"/cards/studio/surveys/{sid}/status", data={"action": "publish"})
    with app.app_context():
        assert db.session.get(Survey, sid).status == "draft"
    page = client.get(f"/cards/studio/surveys/{sid}").get_data(as_text=True)
    assert "en" in page and ("has no text" in page or "brak tekstu" in page)


def test_invalid_module_edit_is_refused(app, client):
    setup_researcher(app, client)
    sid = new_blank(app, client)
    client.post(f"/cards/studio/surveys/{sid}/modules/add", data={"type": "tap_blocks"})
    with app.app_context():
        before = db.session.get(Survey, sid).definition
    resp = client.post(f"/cards/studio/surveys/{sid}/modules/tap_blocks", data={"mode": "json", "module_json": json.dumps({"key": "tap_blocks", "type": "tap_blocks", "criterion": {"pl": "x", "en": "x"}, "items": [{"code": "A", "label": {"pl": "a", "en": "a"}}, {"code": "B", "label": {"pl": "b", "en": "b"}}], "blocks": [["A", "C"]]})})
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(Survey, sid).definition == before


def test_contents_editor(app, client):
    setup_researcher(app, client)
    resp = client.post("/cards/studio/new", data={"template": "experiment", "languages": ["pl", "en"]})
    sid = int(re.search(r"/surveys/(\d+)", resp.headers["Location"]).group(1))
    data = {"rows": "2",
            "r0_outer": "A", "r0_stratum": "*", "r0_text__pl": "Treść A", "r0_text__en": "Text A",
            "r1_outer": "B", "r1_stratum": "*", "r1_text__pl": "Treść B", "r1_text__en": "Text B",
            "r2_outer": "B", "r2_stratum": "hum", "r2_text__pl": "Treść B dla hum", "r2_text__en": "Text B for hum"}
    assert client.post(f"/cards/studio/surveys/{sid}/modules/aid/contents", data=data).status_code == 302
    with app.app_context():
        aid = next(m for m in db.session.get(Survey, sid).modules if m["key"] == "aid")
        assert aid["contents"]["B"]["hum"]["en"] == "Text B for hum" and aid["contents"]["A"]["*"]["pl"] == "Treść A"


def test_owners_only(app, client):
    setup_researcher(app, client, "owner@uj.edu.pl")
    sid = new_blank(app, client)
    other = app.test_client()
    make_user(app, "other@uj.edu.pl")
    login(other, "other@uj.edu.pl")
    for url in (f"/cards/studio/surveys/{sid}", f"/cards/studio/surveys/{sid}/monitor", f"/cards/studio/surveys/{sid}/export.zip"):
        assert other.get(url).status_code == 403
    assert app.test_client().get(f"/cards/studio/surveys/{sid}").status_code == 302


def test_duplicate_close_and_delete(app, client):
    setup_researcher(app, client)
    sid = new_blank(app, client)
    client.post(f"/cards/studio/surveys/{sid}/duplicate")
    with app.app_context():
        assert Survey.query.count() == 2
        slug = db.session.get(Survey, sid).slug
    client.post(f"/cards/studio/surveys/{sid}/status", data={"action": "close"})
    client.post(f"/cards/studio/surveys/{sid}/delete", data={"confirm": "wrong"})
    with app.app_context():
        assert db.session.get(Survey, sid) is not None and db.session.get(Survey, sid).status == "closed"
    client.post(f"/cards/studio/surveys/{sid}/delete", data={"confirm": slug})
    with app.app_context():
        assert db.session.get(Survey, sid) is None and Survey.query.count() == 1


def test_monitor_counts_and_cleanup(app, client):
    setup_researcher(app, client)
    resp = client.post("/cards/studio/new", data={"template": "tap", "languages": ["pl", "en"]})
    sid = int(re.search(r"/surveys/(\d+)", resp.headers["Location"]).group(1))
    client.post(f"/cards/studio/surveys/{sid}/status", data={"action": "publish"})
    with app.app_context():
        slug = db.session.get(Survey, sid).slug
    for _ in range(2):
        c = app.test_client()
        run_to_end(c, start(c, slug))
    page = client.get(f"/cards/studio/surveys/{sid}/monitor").get_data(as_text=True)
    assert "2 / 2" in page or "2</dd>" in page
    client.post(f"/cards/studio/surveys/{sid}/responses/delete", data={"which": "all", "confirm": slug})
    with app.app_context():
        assert Response.query.filter_by(survey_id=sid).count() == 0


def test_footer_shows_the_version(client):
    from cardsurveys import __version__
    html = client.get("/cards/").get_data(as_text=True)
    assert f"{__version__}</span>" in html
