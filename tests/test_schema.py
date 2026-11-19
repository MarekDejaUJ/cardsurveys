import copy

from cardsurveys.seeds.demos import all_demos, experiment_demo, tap_demo
from cardsurveys.survey import conditions
from cardsurveys.survey.schema import blocking_for_publish, validate_bundle
from cardsurveys.survey.textfmt import render


def codes(result):
    return {m["code"] for m in result["errors"]}, {m["code"] for m in result["warnings"]}


def test_demo_bundles_are_clean():
    for name, bundle in all_demos():
        result = validate_bundle(bundle, ["pl", "en"])
        assert result["errors"] == [], (name, result["errors"])
        assert blocking_for_publish(result) == [], (name, result["warnings"])


def test_errors_are_reported():
    b = experiment_demo()
    b["modules"].append(copy.deepcopy(b["modules"][1]))
    errs, _ = codes(validate_bundle(b))
    assert "duplicate_module_key" in errs and "duplicate_answer_name" in errs
    b = experiment_demo()
    b["modules"][3]["arm_of"] = "missing"
    assert "stimulus_unknown_randomizer" in codes(validate_bundle(b))[0]
    b = experiment_demo()
    b["modules"][2]["strata_by"] = ["nothing"]
    assert "strata_unknown_answer" in codes(validate_bundle(b))[0]
    b = experiment_demo()
    b["modules"][5]["variants"]["hum"]["reference_order"] = [["R1"]]
    assert "reference_order_mismatch" in codes(validate_bundle(b))[0]
    b = experiment_demo()
    b["modules"][4]["condition"] = {"answer": "later", "op": "eq", "value": "x"}
    assert "condition_unknown_answer" in codes(validate_bundle(b))[0]
    b = tap_demo()
    b["modules"][2]["design"] = "v9_k3_lambda1"
    assert "design_unusable" in codes(validate_bundle(b))[0]
    b = tap_demo()
    b["modules"][2]["anchor"]["code"] = "SUP"
    assert "anchor_code_clash" in codes(validate_bundle(b))[0]
    b = tap_demo()
    b["modules"][1]["type"] = "nonsense"
    assert "unknown_module_type" in codes(validate_bundle(b))[0]
    assert validate_bundle([])["errors"][0]["code"] == "not_an_object"
    b = tap_demo()
    b["format"] = "other"
    assert codes(validate_bundle(b))[0] == {"schema"}


def test_missing_translations_block_publishing_only():
    b = tap_demo()
    del b["modules"][2]["items"][0]["label"]["en"]
    result = validate_bundle(b)
    assert result["errors"] == []
    blocking = blocking_for_publish(result)
    assert len(blocking) == 1 and blocking[0]["code"] == "missing_translation" and blocking[0]["language"] == "en"


def test_three_languages():
    b = tap_demo()
    b["survey"]["languages"] = ["pl", "en", "de"]
    result = validate_bundle(b, ["pl", "en"])
    assert {"language_not_enabled", "missing_translation"} <= codes(result)[1]


def test_conditions():
    answers = {"level": "phd", "fields": ["a", "b"]}
    arms = {"arm": {"arm": "C"}}
    assert conditions.holds({"answer": "level", "op": "eq", "value": "phd"}, answers, arms)
    assert not conditions.holds({"answer": "level", "op": "ne", "value": "phd"}, answers, arms)
    assert conditions.holds({"answer": "fields", "op": "in", "value": ["b", "z"]}, answers, arms)
    assert conditions.holds({"answer": "missing", "op": "empty"}, answers, arms)
    assert not conditions.holds({"answer": "missing", "op": "eq", "value": "x"}, answers, arms)
    assert conditions.holds({"arm": "arm", "op": "eq", "value": "C"}, answers, arms)
    assert conditions.holds({"all": [{"arm": "arm", "op": "in", "value": ["C"]}, {"not": {"answer": "level", "op": "eq", "value": "ma"}}]}, answers, arms)
    assert conditions.holds({"any": [{"answer": "level", "op": "eq", "value": "ma"}, {"answer": "level", "op": "answered"}]}, answers, arms)
    assert conditions.holds(None, answers, arms)


def test_text_markup_escapes():
    html = str(render("**Bold** and *it*\n\n- one\n- two https://doi.org/10.1000/x\n\n<script>alert(1)</script>"))
    assert "<strong>Bold</strong>" in html and "<em>it</em>" in html and "<ul><li>one</li>" in html
    assert 'href="https://doi.org/10.1000/x"' in html and "<script>" not in html and "&lt;script&gt;" in html
