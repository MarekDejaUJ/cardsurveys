import itertools
import random
from collections import Counter

import pytest

from cardsurveys.engine import blocks as B


def test_library_designs_are_balanced():
    lib = B.design_library()
    assert lib, "the design library is empty"
    for key, d in lib.items():
        pc = Counter(p for b in d["blocks"] for p in itertools.combinations(sorted(b), 2))
        rc = Counter(i for b in d["blocks"] for i in b)
        assert set(pc.values()) == {d["lambda"]} and len(pc) == d["v"] * (d["v"] - 1) // 2, key
        assert set(rc.values()) == {d["r"]}, key
        assert d["v"] * d["r"] == d["b"] * d["k"] and d["lambda"] * (d["v"] - 1) == d["r"] * (d["k"] - 1), key


def test_designs_used_by_the_reach_study():
    d = B.design_library()["v8_k4_lambda3"]
    assert (d["v"], d["k"], d["lambda"], d["r"], d["b"]) == (8, 4, 3, 7, 14)
    f = B.design_library()["v7_k3_lambda1"]
    assert (f["v"], f["k"], f["lambda"], f["r"], f["b"]) == (7, 3, 1, 3, 7)
    assert {"v9_k3_lambda1", "v10_k4_lambda2"} <= set(B.design_library())


def test_verify_blocks_messages():
    codes = list("ABCDEFG")
    ok = B.verify_blocks(B.blocks_from_design("v7_k3_lambda1", codes), codes, "tap")
    assert ok["balanced"] and ok["lambda"] == 1 and ok["r"] == 3 and ok["messages"] == []
    bad = B.verify_blocks([["A", "B", "C"], ["A", "B", "Z"]], codes, "sob")
    found = {m["code"] for m in bad["messages"]}
    assert {"unknown_items", "absent_items", "unbalanced_pairs"} <= found
    even = B.verify_blocks(B.blocks_from_design("v10_k4_lambda2", list("ABCDEFGHIJ")), list("ABCDEFGHIJ"))
    assert any(m["code"] == "even_lambda" for m in even["messages"])
    with pytest.raises(ValueError):
        B.blocks_from_design("v7_k3_lambda1", list("ABCDEF"))


def test_schedule_with_anchor_repeats_and_attention():
    codes = [f"S{i}" for i in range(1, 9)]
    blocks = B.blocks_from_design("v8_k4_lambda3", codes)
    sched = B.build_schedule(blocks, random.Random(3), duplicates=2, attention=1, anchor_code="ANCHOR")
    assert len(sched) == 14 + 2 + 1
    assert all(e["cards"][-1] == "ANCHOR" for e in sched)
    repeats = [e for e in sched if e["repeat_of"] is not None]
    assert len(repeats) == 2
    for r in repeats:
        first = next(i for i, e in enumerate(sched) if e["design_block"] == r["repeat_of"] and e["repeat_of"] is None)
        assert r["position"] > first
    att = [e for e in sched if e["attention"]]
    assert len(att) == 1 and "ATTN" in att[0]["cards"] and len(att[0]["cards"]) == 6
    assert [e["position"] for e in sched] == list(range(len(sched)))
    shown = Counter(e["design_block"] for e in sched if e["repeat_of"] is None and not e["attention"])
    assert set(shown) == set(range(14)) and set(shown.values()) == {1}


def test_read_sob():
    obs = B.read_sob(["A", "B", "C", "D"], {"A": 0, "B": 1, "C": 1, "D": "side"}, 4)
    rel = {(o["item_a"], o["item_b"]): o["relation"] for o in obs}
    assert rel[("A", "B")] == "a_prec_b" and rel[("A", "C")] == "a_prec_b"
    assert rel[("B", "C")] == "incomparable" and rel[("A", "D")] == "incomparable"
    with pytest.raises(ValueError):
        B.read_sob(["A", "B"], {"A": 0}, 2)
    with pytest.raises(ValueError):
        B.read_sob(["A", "B"], {"A": 0, "B": 7}, 2)


def test_read_tap_anchor_and_attention():
    cards = ["S1", "S2", "S3", "ANCHOR"]
    r = B.read_tap(cards, ["S2", "ANCHOR", "S1", "S3"])
    rel = {(o["item_a"], o["item_b"]): o["relation"] for o in r["pairs"]}
    assert len(r["pairs"]) == 6 and rel[("S1", "S2")] == "b_prec_a" and rel[("S2", "S3")] == "a_prec_b"
    assert B.anchor_positions(r["order"], "ANCHOR") == {"S2": 1, "S1": -1, "S3": -1}
    with pytest.raises(ValueError):
        B.read_tap(cards, ["S1", "S1", "S2", "ANCHOR"])
    with pytest.raises(ValueError):
        B.read_tap(cards, ["S1", "S2"])
    assert B.attention_passed(["A", "B", "ATTN"], "ATTN") and not B.attention_passed(["ATTN", "A", "B"], "ATTN")


def test_pair_tallies_and_cyclic_triads():
    obs = [{"item_a": "A", "item_b": "B", "relation": "a_prec_b"}, {"item_a": "B", "item_b": "A", "relation": "a_prec_b"},
           {"item_a": "A", "item_b": "B", "relation": "incomparable"}]
    t = B.pair_tallies(obs)
    assert t == [{"item_a": "A", "item_b": "B", "observations": 3, "a_prec_b": 1 / 3, "b_prec_a": 1 / 3, "incomparable": 1 / 3}]
    cyc = {("A", "B"): 1, ("B", "C"): 1, ("C", "A"): 1}
    assert B.cyclic_triads(cyc, ["A", "B", "C"]) == 1
    assert B.cyclic_triads({("A", "B"): 1, ("B", "C"): 1, ("A", "C"): 1}, ["A", "B", "C"]) == 0
