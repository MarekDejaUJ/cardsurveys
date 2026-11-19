"""The structure engine reproduces the published numbers of the five-manager example (four cards)."""
import math

from cardsurveys.engine import structures as S

# Five managers, four cards (0 strategy, 1 technology, 2 structural change, 3 new value).
VIEWS = [
    [(0, 1), (0, 3), (1, 3)],
    [(0, 2), (0, 3), (2, 3)],
    [(0, 1), (0, 2), (0, 3)],
    [(0, 3), (1, 3), (2, 3)],
    [(1, 0), (0, 3), (1, 3)],
]
SECOND = [
    [(0, 1), (0, 3), (1, 3)],
    [(0, 2), (0, 3), (2, 3)],
    [(0, 1), (0, 2), (0, 3)],
    [(0, 3), (1, 3), (2, 3), (0, 1)],
    [(1, 0), (0, 3), (1, 3)],
]
CONTRAST = [[(0, 1)], [(0, 2)], [(1, 2)], [(1, 3)], [(2, 3)]]
PATH = [[(0, 2), (0, 3), (2, 3)], [(0, 2), (0, 3)], [(0, 3)], [(0, 3), (1, 3)]]


def panel():
    return [S.from_pairs(v) for v in VIEWS]


def test_views_and_nearest_common_order():
    n, C = 4, panel()
    assert len(S.posets(n)) == 219 and len(S.linear_orders(n)) == 24
    assert all(S.is_spo(X, n) for X in C) and all(S.popcount(X) == 3 for X in C)
    near = S.nearest_common(C, n)
    Cs = S.from_pairs([(0, 3), (1, 3)])
    assert near["structures"] == [Cs] and near["total"] == 9 and abs(near["mean_distance"] - 1.8) < 1e-12
    assert [S.distance_to(X, [Cs])["distance"] for X in C] == [1, 3, 3, 1, 1]
    assert [S.popcount(X & ~Cs) for X in C] == [1, 2, 2, 1, 1]
    assert [S.popcount(Cs & ~X) for X in C] == [0, 1, 1, 0, 0]
    assert S.common_part(C) == S.from_pairs([(0, 3)])
    assert S.threshold_structure(C, n, 0.5) == Cs and S.threshold_structure(C, n, 0.75) == S.from_pairs([(0, 3)])
    assert S.threshold_structure(C, n, 0.3) == S.from_pairs([(0, 1), (0, 2), (0, 3), (1, 3), (2, 3)])
    assert abs(S.distance_floor(C, n) - 1.8) < 1e-12
    assert abs(S.agreement(C, n) - 7.52 / 12) < 1e-12
    pw = S.mean_pairwise(C)
    assert abs(pw["with_replacement"] - 2.24) < 1e-12 and abs(pw["distinct"] - 2.8) < 1e-12
    assert [S.related_share(X, n) for X in C] == [0.5] * 5 and abs(S.related_share(Cs, n) - 1 / 3) < 1e-12
    eff = S.single_change_effects(C, n)
    assert eff["one_change_suffices"] and len(eff["changes"]) == 9
    assert S.group_totals(C, n) == [9, 5, 3, 2, 0]


def test_pair_shares():
    n, C = 4, panel()
    s = {(x["a"], x["b"]): x for x in S.pair_shares(C, n)}
    assert s[(0, 3)]["kind"] == "shared relation" and s[(1, 2)]["kind"] == "shared non-relation"
    assert s[(0, 1)]["a_prec_b"] == 0.4 and s[(0, 1)]["b_prec_a"] == 0.2 and s[(0, 1)]["apart"] == 0.4
    assert s[(1, 3)]["a_prec_b"] == 0.6 and s[(1, 3)]["apart"] == 0.4
    assert sum(1 for x in s.values() if x["kind"] == "contested") == 4
    summ = S.population_summary(C, n)
    assert summ["nearest"] == [S.from_pairs([(0, 3), (1, 3)])] and summ["distances"] == [1, 3, 3, 1, 1]


def test_boards_and_certifying_pairs():
    n, C = 4, panel()
    Cs = S.from_pairs([(0, 3), (1, 3)])
    t3, t3p = S.recordable("tier", n, 3), S.recordable("tier_aside", n, 3)
    assert [X in t3 for X in C] == [False, False, True, True, False]
    assert all(X in t3p for X in C)
    assert S.from_pairs([(0, 1), (2, 3)]) not in S.recordable("tier_aside", n, 4)
    assert all(X in S.recordable("plane", n) for X in C)
    assert len(S.recordable("pile", n)) == 15
    assert len(S.recordable("tier", n, 3)) == 51 and len(S.recordable("tier_aside", n, 3)) == 111
    cert = [S.certifying_pairs(X, n) for X in C + [Cs]]
    assert [len(K) for K in cert] == [4, 4, 6, 6, 4, 6]
    assert sorted(S.critical_pairs(C[1], n)) == [(0, 1), (1, 3)]
    assert [len(S.covering_pairs(X, n)) for X in C] == [2, 2, 3, 3, 2]
    five = [q for q in S.upairs(n) if q != (1, 3)]
    assert len(S.compatible(C[0], five, n)) == 3 and not S.determined(C[1], five, n)
    assert all(S.determined(X, S.upairs(n), n) for X in C)
    assert S.determined(C[1], sorted(cert[1]), n)


def test_readings():
    n, C = 4, panel()
    assert S.reading("tier", n, {"0": 0, "1": 1, "2": 1, "3": 1}, k=3)["structure"] == C[2]
    assert S.reading("tier_aside", n, {"0": 0, "1": 1, "2": "aside", "3": 2}, k=3)["structure"] == C[0]
    r = S.reading("arrow", n, {"arrows": [[0, 1], [1, 3]]})
    assert r["structure"] == C[0] and r["coherent"]
    assert not S.reading("arrow", n, {"arrows": [[0, 1], [1, 2], [2, 0]]})["coherent"]
    assert S.reading("plane", n, {"0": [1, 2], "1": [2, 3], "3": [3, 4], "2": [4, 1]})["structure"] == C[0]
    r = S.reading("pile", n, {"0": "p1", "1": "p1", "2": "p2", "3": "p2"})
    assert r["judgments"] == "sim" and S.to_upairs(r["structure"], n) == [(0, 1), (2, 3)]
    r = S.reading("pairs", n, {"0,1": "a", "0,2": "apart", "0,3": "apart", "1,2": "a", "1,3": "apart", "2,3": "apart"})
    assert not r["coherent"]
    r = S.reading("pairs", n, {"0,1": "a", "0,2": "undecided", "0,3": "apart", "1,2": "apart", "1,3": "apart", "2,3": "apart"})
    assert r["undecided"] == [(0, 2)] and r["coherent"]
    assert 3 ** math.comb(n, 2) == 729


def test_reading_rejects_bad_input():
    import pytest
    with pytest.raises(ValueError):
        S.reading("tier", 3, {"0": 0, "1": 5, "2": 0}, k=3)
    with pytest.raises(ValueError):
        S.reading("tier", 3, {"0": 0, "1": "aside", "2": 0}, k=3)
    with pytest.raises(ValueError):
        S.reading("arrow", 3, {"arrows": [[0, 0]]})
    with pytest.raises(ValueError):
        S.reading("pairs", 3, {"0,1": "maybe", "0,2": "a", "1,2": "a"})


def test_second_session_and_contrast():
    n = 4
    C, C2 = panel(), [S.from_pairs(v) for v in SECOND]
    near2 = S.nearest_common(C2, n)["structures"]
    assert near2 == [C[0]] and [S.distance_to(X, near2)["distance"] for X in C2] == [0, 4, 2, 1, 2]
    assert [S.dist(x, y) for x, y in zip(C, C2)] == [0, 0, 0, 1, 0]
    contrast = [S.from_pairs(v) for v in CONTRAST]
    assert abs(S.agreement(contrast, n) - 0.7333333333333333) < 1e-12 and S.common_part(contrast) == 0
    for k, X in enumerate([S.from_pairs(v) for v in PATH]):
        new = list(C)
        new[1] = X
        near = S.nearest_common(new, n)
        assert near["structures"] == [S.from_pairs([(0, 3), (1, 3)])] and near["total"] == 9 - k
