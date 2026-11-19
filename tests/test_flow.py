import csv
import io
import json
import zipfile

import pytest

from cardsurveys.extensions import db
from cardsurveys.models import (Allocation, Answer, Arrangement, BlockResponse, Confirmation, PairObservation, Response,
                                ScreenTime, Survey, User)
from cardsurveys.seeds.demos import all_demos, board_demo, experiment_demo, sob_demo, tap_demo
from cardsurveys.survey import bundle as bundles
from cardsurveys.survey.export import export_files

from .conftest import answer_current, make_user, run_to_end, start


def create(app, bundle, owner_email="owner@uj.edu.pl", status="open"):
    with app.app_context():
        user = User.query.filter_by(email=owner_email).first()
        if user is None:
            make_user(app, owner_email)
            user = User.query.filter_by(email=owner_email).first()
        s = bundles.create_from_bundle(user, bundle, ["pl", "en"])
        s.status = status
        db.session.commit()
        return s.id, s.slug


def response(app, uuid):
    with app.app_context():
        return Response.query.filter_by(uuid=uuid).first()


@pytest.mark.parametrize("name", [n for n, _ in all_demos()])
def test_every_demo_runs_to_the_end(app, client, name):
    bundle = dict(all_demos())[name]
    sid, slug = create(app, bundle)
    uuid = start(client, slug)
    keys = run_to_end(client, uuid)
    assert keys and keys[0].startswith("consent:")
    r = response(app, uuid)
    assert r.status == "submitted" and r.submitted_at is not None
    page = client.get(f"/cards/r/{uuid}/done")
    assert page.status_code == 200
    with app.app_context():
        files = export_files(db.session.get(Survey, sid))
    rows = list(csv.DictReader(io.StringIO(files["responses.csv"])))
    assert len(rows) == 1 and rows[0]["status"] == "submitted"


def test_board_confirmation_refusal_returns_to_the_board(app, client):
    sid, slug = create(app, board_demo("arrow"))
    uuid = start(client, slug)
    answer_current(client, uuid)  # consent
    key, code = answer_current(client, uuid)  # board: chain 0 -> 1 -> 2, cards 3 and 4 apart
    assert key.startswith("board:0") and code == 302
    key, code = answer_current(client, uuid, {"confirm": "related"})
    assert key.startswith("board:1")
    page = client.get(f"/cards/r/{uuid}").get_data(as_text=True)
    assert 'id="board"' in page and "data-initial=" in page
    answer_current(client, uuid)
    answer_current(client, uuid, {"confirm": "unrelated"})
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid).first()
        answers = [c.answer for c in Confirmation.query.filter_by(response_id=r.id).all()]
        arr = Arrangement.query.filter_by(response_id=r.id).one()
        assert "refused" in answers and "unrelated" in answers and arr.completed and arr.coherent
    assert response(app, uuid).status == "submitted"


def test_board_rejects_a_circle(app, client):
    sid, slug = create(app, board_demo("arrow"))
    uuid = start(client, slug)
    answer_current(client, uuid)
    html = client.get(f"/cards/r/{uuid}").get_data(as_text=True)
    import re
    key = re.search(r'name="screen" value="([^"]+)"', html).group(1)
    resp = client.post(f"/cards/r/{uuid}", data={"screen": key, "placements_json": json.dumps({"arrows": [[0, 1], [1, 0]]})})
    assert resp.status_code == 302
    with app.app_context():
        assert Arrangement.query.count() == 0


def test_tap_blocks_store_orders_gates_attention_and_pairs(app, client):
    sid, slug = create(app, tap_demo())
    uuid = start(client, slug)
    run_to_end(client, uuid, {"gate": "no"})
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid).first()
        rows = BlockResponse.query.filter_by(response_id=r.id, module_key="value").order_by(BlockResponse.position).all()
        assert len(rows) == 7 + 1 + 1
        assert all(json.loads(b.result_json)[-1] in ("ANCHOR", "ATTN") for b in rows)
        assert sum(1 for b in rows if b.attention) == 1 and all(b.attention_passed for b in rows if b.attention)
        assert sum(1 for b in rows if b.repeat_of is not None) == 1
        assert {b.gate_value for b in rows} == {"no"}
        pairs = PairObservation.query.filter_by(response_id=r.id, module_key="value").count()
        assert pairs == 8 * 6  # attention block excluded; 3 items + anchor = 6 pairs per block
        practice = BlockResponse.query.filter_by(response_id=r.id, module_key="practice").count()
        assert practice == 1


def test_tap_block_refuses_incomplete_or_foreign_orders(app, client):
    sid, slug = create(app, tap_demo())
    uuid = start(client, slug)
    answer_current(client, uuid)
    import re
    html = client.get(f"/cards/r/{uuid}").get_data(as_text=True)
    key = re.search(r'name="screen" value="([^"]+)"', html).group(1)
    for bad in (["BAN", "LEM"], ["BAN", "LEM", "XXX"], "not json"):
        client.post(f"/cards/r/{uuid}", data={"screen": key, "result_json": json.dumps(bad) if bad != "not json" else bad})
    with app.app_context():
        assert BlockResponse.query.count() == 0


def test_sob_blocks_and_incomparability(app, client):
    sid, slug = create(app, sob_demo())
    uuid = start(client, slug)
    run_to_end(client, uuid)
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid).first()
        rels = [p.relation for p in PairObservation.query.filter_by(response_id=r.id).all()]
        assert len(rels) == 7 * 3 and "incomparable" in rels and "a_prec_b" in rels


def test_experiment_randomizer_stimulus_choice_and_variants(app, client):
    sid, slug = create(app, experiment_demo())
    arms = []
    for i in range(12):
        c = app.test_client()
        uuid = start(c, slug)
        run_to_end(c, uuid, {"level": "ma", "field": "sci" if i % 2 else "hum"})
        r = response(app, uuid)
        arms.append(r.assignments["arm"]["arm"])
        with app.app_context():
            names = {a.name for a in Answer.query.filter_by(response_id=r.id).all()}
            blocks = BlockResponse.query.filter_by(response_id=r.id, module_key="judge").all()
            assert {b.variant for b in blocks} == {"sci" if i % 2 else "hum"}
            assert ("aid_choice" in names) == (r.assignments["arm"]["arm"] == "C")
            assert "thesis_lang" not in names
            shown = {s.module_key for s in ScreenTime.query.filter_by(response_id=r.id).all()}
            assert ("aid" in shown) == (r.assignments["arm"]["arm"] in ("A", "B"))
    # permuted blocks of size 3 inside each stratum (6 respondents per stratum)
    with app.app_context():
        for stratum in ("level=ma|field=hum", "level=ma|field=sci"):
            seq = [a.arm for a in Allocation.query.filter_by(survey_id=sid, stratum=stratum).order_by(Allocation.seq_no)]
            assert len(seq) == 6 and sorted(seq[:3]) == ["A", "B", "C"] and sorted(seq[3:]) == ["A", "B", "C"]


def test_aid_panel_shows_the_respondents_material_during_tap_blocks(app, client):
    import re

    from .conftest import SCREEN
    sid, slug = create(app, experiment_demo())
    seen = set()
    for i in range(9):
        c = app.test_client()
        uuid = start(c, slug)
        html = ""
        for _ in range(20):
            html = c.get(f"/cards/r/{uuid}").get_data(as_text=True)
            key = SCREEN.search(html).group(1)
            if key.startswith("judge:"):
                break
            answer_current(c, uuid, {"level": "ma", "field": "hum", "aid_choice": "B" if i % 2 else "A"})
        arm = response(app, uuid).assignments["arm"]["arm"]
        assert 'class="aid-panel"' in html
        panel = re.search(r'<details class="aid-panel"[^>]*>(.*?)</details>', html, re.S).group(1)
        shown = "A" if "doi.org" in panel else "B"
        if arm in ("A", "B"):
            assert shown == arm
        seen.add(arm)
    assert seen == {"A", "B", "C"}


def test_panel_must_name_an_earlier_material_module():
    from cardsurveys.survey.schema import validate_bundle
    bundle = experiment_demo()
    judge = next(m for m in bundle["modules"] if m["key"] == "judge")
    judge["panel_from"] = ["debrief"]
    result = validate_bundle(bundle)
    assert any(e["code"] == "panel_unknown_module" for e in result["errors"])


def test_branching_question_inside_a_form(app, client):
    sid, slug = create(app, experiment_demo())
    uuid = start(client, slug)
    run_to_end(client, uuid, {"level": "phd", "field": "hum", "thesis_lang": "en"})
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid).first()
        names = {a.name: json.loads(a.value) for a in Answer.query.filter_by(response_id=r.id).all()}
        assert names["thesis_lang"] == "en" and names["level"] == "phd"


def test_required_question_is_enforced(app, client):
    sid, slug = create(app, experiment_demo())
    uuid = start(client, slug)
    answer_current(client, uuid)
    import re
    html = client.get(f"/cards/r/{uuid}").get_data(as_text=True)
    key = re.search(r'name="screen" value="([^"]+)"', html).group(1)
    resp = client.post(f"/cards/r/{uuid}", data={"screen": key, "level": "ma"})
    assert resp.status_code == 400 and "field" in resp.get_data(as_text=True)
    resp = client.post(f"/cards/r/{uuid}", data={"screen": key, "level": "ma", "field": "nope"})
    assert resp.status_code == 400


def test_decline_and_withdraw(app, client):
    sid, slug = create(app, tap_demo())
    uuid = start(client, slug)
    answer_current(client, uuid, {"decision": "decline"})
    assert response(app, uuid).status == "declined"
    c2 = app.test_client()
    uuid2 = start(c2, slug)
    answer_current(c2, uuid2)
    answer_current(c2, uuid2)
    resp = c2.post(f"/cards/r/{uuid2}/withdraw")
    assert resp.status_code == 200
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid2).first()
        assert r.status == "withdrawn" and r.state_json in ("{}",)
        for model in (Answer, BlockResponse, PairObservation, ScreenTime):
            assert model.query.filter_by(response_id=r.id).count() == 0


def test_resume_by_cookie_and_language_switch(app, client):
    sid, slug = create(app, tap_demo())
    uuid = start(client, slug, lang="en")
    again = client.get(f"/cards/s/{slug}")
    assert again.headers["Location"].endswith(f"/r/{uuid}")
    page = client.get(f"/cards/r/{uuid}").get_data(as_text=True)
    assert "I agree and want to take part" in page
    page = client.get(f"/cards/r/{uuid}?lang=pl").get_data(as_text=True)
    assert "Zgadzam się i chcę wziąć udział" in page and response(app, uuid).language == "pl"


def test_stale_screen_is_not_recorded(app, client):
    sid, slug = create(app, tap_demo())
    uuid = start(client, slug)
    resp = client.post(f"/cards/r/{uuid}", data={"screen": "value:3:1", "decision": "agree"})
    assert resp.status_code == 302 and not response(app, uuid).consented


def test_closed_and_draft_surveys(app, client):
    sid, slug = create(app, tap_demo(), status="draft")
    assert client.get(f"/cards/s/{slug}").status_code == 404
    with app.app_context():
        s = db.session.get(Survey, sid)
        s.status = "closed"
        db.session.commit()
    assert client.get(f"/cards/s/{slug}").status_code == 410


def test_retest_repeats_marked_modules(app, client):
    bundle = board_demo("tier")
    bundle["survey"]["retest"] = True
    bundle["modules"][1]["retest"] = True
    bundle["modules"][2]["show_retest_link"] = True
    sid, slug = create(app, bundle)
    uuid = start(client, slug)
    run_to_end(client, uuid)
    done = client.get(f"/cards/r/{uuid}/done").get_data(as_text=True)
    assert f"/r/{uuid}/retest" in done
    assert client.get(f"/cards/r/{uuid}/retest").status_code == 302
    run_to_end(client, uuid)
    with app.app_context():
        r = Response.query.filter_by(uuid=uuid).first()
        assert r.retest_submitted_at is not None
        assert sorted(a.occasion for a in Arrangement.query.filter_by(response_id=r.id)) == [1, 2]


def test_preview_is_excluded_from_exports(app, client):
    from .conftest import login
    sid, slug = create(app, tap_demo(), owner_email="owner@uj.edu.pl")
    login(client, "owner@uj.edu.pl")
    resp = client.post(f"/cards/studio/surveys/{sid}/preview")
    uuid = resp.headers["Location"].split("/r/")[1]
    page = client.get(f"/cards/r/{uuid}").get_data(as_text=True)
    assert "Preview" in page or "Podgląd" in page
    run_to_end(client, uuid)
    with app.app_context():
        files = export_files(db.session.get(Survey, sid))
    assert len(list(csv.DictReader(io.StringIO(files["responses.csv"])))) == 0
    assert files["pairs.csv"].count("\n") == 1


def test_export_zip_layout(app, client):
    from .conftest import login
    bundle = experiment_demo()
    bundle["modules"].insert(6, board_demo("arrow")["modules"][1])
    sid, slug = create(app, bundle, owner_email="owner@uj.edu.pl")
    uuid = start(client, slug)
    run_to_end(client, uuid, {"level": "ma", "field": "hum"})
    login(client, "owner@uj.edu.pl")
    data = client.get(f"/cards/studio/surveys/{sid}/export.zip").data
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = set(zf.namelist())
    assert {"survey.json", "description.json", "responses.csv", "answers.csv", "blocks.csv", "pairs.csv", "screens.csv",
            "allocations.csv", "boards/board/study.json", "boards/board/placements.csv", "boards/board/judgments.csv",
            "boards/board/confirmations.csv", "boards/board/responses.csv"} <= names
    study = json.loads(zf.read("boards/board/study.json"))
    assert study["format"] == "cardsurveys-export-1" and study["board"]["kind"] == "arrow" and study["class"] == "po"
    assert [e["code"] for e in study["elements"]] == ["RQ", "LIT", "METH", "DATA", "ANAL"]
    placements = list(csv.DictReader(io.StringIO(zf.read("boards/board/placements.csv").decode())))
    assert placements[0]["placements_json"].startswith("{") and placements[0]["coherent"] == "1"
    judgments = list(csv.DictReader(io.StringIO(zf.read("boards/board/judgments.csv").decode())))
    assert len(judgments) == 10 and {j["state"] for j in judgments} <= {"a_prec_b", "b_prec_a", "apart"}
    desc = json.loads(zf.read("description.json"))
    from cardsurveys import __version__
    assert desc["software"] == {"name": "Card Surveys", "version": __version__}
    judge = next(m for m in desc["codebook"]["modules"] if m["key"] == "judge")
    assert judge["variants"]["hum"]["reference_order"][0] == ["R1", "R2"]
    responses = list(csv.DictReader(io.StringIO(zf.read("responses.csv").decode())))
    assert responses[0]["arm_arm"] in ("A", "B", "C") and responses[0]["level"] == "ma"
    for name in names:
        assert bytes([101, 105, 100, 101]) not in zf.read(name).lower()


def test_bundle_round_trip(app, client):
    from .conftest import login
    sid, slug = create(app, experiment_demo(), owner_email="owner@uj.edu.pl")
    login(client, "owner@uj.edu.pl")
    exported = client.get(f"/cards/studio/surveys/{sid}/bundle.json").get_data(as_text=True)
    resp = client.post("/cards/studio/import", data={"bundle_text": exported})
    assert resp.status_code == 302
    with app.app_context():
        surveys = Survey.query.order_by(Survey.id).all()
        assert len(surveys) == 2 and surveys[1].definition["modules"] == surveys[0].definition["modules"]
        assert surveys[1].slug != surveys[0].slug and surveys[1].status == "draft"
    bad = client.post("/cards/studio/import", data={"bundle_text": '{"format": "cardsurveys-bundle"}'})
    assert bad.status_code == 400


def _reach_study_shape():
    """A survey with the structure of the reach-practice-retention instrument (placeholder texts)."""
    from cardsurveys.seeds.demos import L
    src = [{"code": f"S{i}", "label": L(f"źródło {i}", f"source {i}")} for i in range(1, 9)]
    anchor = lambda pl, en: {"code": "ANCHOR", "label": L(pl, en)}  # noqa: E731
    gate = {"question": L("Czy masz pewność?", "Were you sure?"), "options": [{"value": "yes", "label": L("tak", "yes")}, {"value": "no", "label": L("nie", "no")}]}
    families = ["hum", "soc", "nat", "med"]
    refs = {f: {"items": [{"code": f"{f.upper()}{j}", "label": L(f"ref {f} {j}", f"ref {f} {j}")} for j in range(1, 8)],
                "design": "v7_k3_lambda1",
                "reference_order": [[f"{f.upper()}1", f"{f.upper()}2"], [f"{f.upper()}3", f"{f.upper()}4"], [f"{f.upper()}5", f"{f.upper()}6", f"{f.upper()}7"]]}
            for f in families}
    def task(key, crit, anc, attention=0, items=src, design="v8_k4_lambda3"):
        return {"key": key, "type": "tap_blocks", "criterion": L(crit, crit), "items": items, "design": design,
                "anchor": anchor(anc, anc), "attention": attention, "attention_label": L("Tej karty dotknij na końcu", "Tap this card last")}
    modules = [
        {"key": "consent", "type": "consent", "text": L("Zgoda.", "Consent.")},
        {"key": "context", "type": "form", "questions": [
            {"name": "level", "type": "radio", "required": True, "label": L("Poziom", "Level"), "options": [{"value": "ma", "label": L("mgr", "MA")}, {"value": "phd", "label": L("dr", "PhD")}]},
            {"name": "family", "type": "select", "required": True, "label": L("Dziedzina", "Field"), "options": [{"value": f, "label": L(f, f)} for f in families]}]},
        {"key": "practice", "type": "tap_blocks", "practice": True, "criterion": L("Próba", "Practice"), "items": src[:3], "blocks": [["S1", "S2", "S3"]]},
        task("O1", "wartość", "nic / nikt"), task("O2", "koszt", "nic mnie nie kosztuje", attention=1),
        task("O3", "epizod", "nie korzystałem"), task("O4", "zaufanie", "nigdy"),
        task("O5", "deklaracja", "nie wspomniałbym", items=src[1:], design="v7_k3_lambda1"),
        {"key": "arm", "type": "randomizer", "arms": [{"code": "L"}, {"code": "G"}, {"code": "C"}], "strata_by": ["level", "family"]},
        {"key": "aid", "type": "stimulus", "arm_of": "arm", "stratum_by": "family",
         "contents": {a: {f: L(f"pomoc {a} {f}", f"aid {a} {f}") for f in families} for a in ("L", "G")}},
        {"key": "aid_choice", "type": "choice", "condition": {"arm": "arm", "op": "eq", "value": "C"}, "stratum_by": "family",
         "prompt": L("Wybierz", "Choose"), "options": [{"value": "L", "label": L("lista", "list")}, {"value": "G", "label": L("czat", "chat")}],
         "contents": {a: {f: L(f"pomoc {a} {f}", f"aid {a} {f}") for f in families} for a in ("L", "G")}},
        {"key": "O7", "type": "tap_blocks", "criterion": L("Pewność", "Certainty"), "variants_by": "family", "variants": refs, "gate": gate},
        task("O6", "atrybucja", "nic", attention=1),
        {"key": "gates", "type": "form", "questions": [{"name": f"access_S{i}", "type": "yesno", "required": True, "label": L(f"dostęp S{i}", f"access S{i}")} for i in range(1, 9)]},
        {"key": "debrief", "type": "debrief", "text": L("Wyjaśnienie.", "Explanation."), "stratum_by": "family", "texts": {f: L(f"wyjaśnienie {f}", f"explanation {f}") for f in families}},
        {"key": "thanks", "type": "thanks", "text": L("Dziękujemy.", "Thank you.")},
    ]
    return {"format": "cardsurveys-bundle", "version": 1, "survey": {"title": L("Kształt badania", "Study shape"), "languages": ["pl", "en"], "default_language": "pl"}, "modules": modules}


def test_reach_study_shape_runs_end_to_end(app, client):
    from cardsurveys.survey.schema import blocking_for_publish, validate_bundle
    bundle = _reach_study_shape()
    result = validate_bundle(bundle, ["pl", "en"])
    assert result["errors"] == [] and blocking_for_publish(result) == []
    sid, slug = create(app, bundle)
    arms = {}
    for i, (level, family) in enumerate([(lv, f) for lv in ("ma", "phd") for f in ("hum", "soc", "nat", "med")] * 3):
        c = app.test_client()
        uuid = start(c, slug)
        keys = run_to_end(c, uuid, {"level": level, "family": family})
        counts = {m: sum(1 for k in keys if k.startswith(m + ":")) for m in ("O1", "O2", "O3", "O4", "O5", "O6", "O7", "practice")}
        assert counts == {"O1": 14, "O2": 15, "O3": 14, "O4": 14, "O5": 7, "O6": 15, "O7": 7, "practice": 1}
        r = response(app, uuid)
        arms.setdefault((level, family), []).append(r.assignments["arm"]["arm"])
        with app.app_context():
            o7 = BlockResponse.query.filter_by(response_id=r.id, module_key="O7").all()
            assert {b.variant for b in o7} == {family} and all(b.gate_value in ("yes", "no") for b in o7)
            o1 = BlockResponse.query.filter_by(response_id=r.id, module_key="O1").all()
            assert all(json.loads(b.cards_json)[-1] == "ANCHOR" and len(json.loads(b.cards_json)) == 5 for b in o1)
            pairs = PairObservation.query.filter_by(response_id=r.id, module_key="O1").count()
            assert pairs == 14 * 10  # 4 sources + anchor = 10 pairs per block
    for stratum, seq in arms.items():
        assert sorted(seq) == ["C", "G", "L"], (stratum, seq)
