"""Order structures recorded by card boards.

A structure is a set of pair statements stored as a Python int: the statement
(i, j) occupies bit i * W + j. On ordered pairs, bit (i, j) means that card i
comes before card j. On unordered pairs (pile board), the pair {i, j} with
i < j occupies bit (i, j) and means that the two cards belong together. Every
function states which kind of pair it assumes.
"""
from __future__ import annotations

import functools
import itertools
import math
from typing import Any

W = 8  # bit stride; supports up to eight cards on one board

BOARD_KINDS = ("tier", "tier_aside", "arrow", "pile", "plane", "pairs")
ORDER_BOARDS = ("tier", "tier_aside", "arrow", "plane", "pairs")  # read on ordered pairs
MAX_ENUMERATION = 6  # strict partial orders are enumerated up to this many cards
MAX_CARDS = 8


# ---------------------------------------------------------------- bit helpers


def bit(i: int, j: int) -> int:
    return 1 << (i * W + j)


def has(P: int, i: int, j: int) -> int:
    return (P >> (i * W + j)) & 1


def pairs(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(n) if i != j]


def upairs(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def popcount(x: int) -> int:
    return bin(x).count("1")


def dist(P: int, R: int) -> int:
    """The number of statements held by one structure and not by the other."""
    return popcount(P ^ R)


def from_pairs(statements: Any) -> int:
    P = 0
    for i, j in statements:
        P |= bit(int(i), int(j))
    return P


def to_pairs(P: int, n: int) -> list[tuple[int, int]]:
    return [(i, j) for i, j in pairs(n) if has(P, i, j)]


def to_upairs(P: int, n: int) -> list[tuple[int, int]]:
    return [(i, j) for i, j in upairs(n) if has(P, i, j)]


# ---------------------------------------------------------------- classes of structures


@functools.lru_cache(maxsize=None)
def posets(n: int) -> tuple[int, ...]:
    """All strict partial orders on {0..n-1}, built by adding one card at a time."""
    if n > MAX_ENUMERATION:
        raise ValueError("strict partial orders are enumerated for at most %d cards" % MAX_ENUMERATION)
    if n == 0:
        return (0,)
    out = []
    for P in posets(n - 1):
        m = n - 1
        below = {x: {y for y in range(m) if has(P, y, x)} for x in range(m)}
        above = {x: {y for y in range(m) if has(P, x, y)} for x in range(m)}
        elems = list(range(m))
        for r in range(m + 1):
            for D in itertools.combinations(elems, r):
                Ds = set(D)
                if any(not below[d] <= Ds for d in Ds):
                    continue
                rest = [x for x in elems if x not in Ds]
                for t in range(len(rest) + 1):
                    for U in itertools.combinations(rest, t):
                        Us = set(U)
                        if any(not above[u] <= Us for u in Us):
                            continue
                        if any(not has(P, d, u) for d in Ds for u in Us):
                            continue
                        Q = P
                        for d in Ds:
                            Q |= bit(d, m)
                        for u in Us:
                            Q |= bit(m, u)
                        out.append(Q)
    return tuple(out)


def is_asymmetric(R: int, n: int) -> bool:
    return all(not (has(R, i, j) and has(R, j, i)) for i, j in upairs(n))


def is_transitive(R: int, n: int) -> bool:
    for i, j in pairs(n):
        if not has(R, i, j):
            continue
        for k in range(n):
            if k != i and k != j and has(R, j, k) and not has(R, i, k):
                return False
    return True


def is_spo(R: int, n: int) -> bool:
    """Strict partial order: asymmetric and transitive."""
    return is_asymmetric(R, n) and is_transitive(R, n)


def is_weak_order(R: int, n: int) -> bool:
    if not is_spo(R, n):
        return False

    def unrelated(i: int, j: int) -> bool:
        return not has(R, i, j) and not has(R, j, i)

    for i, j, k in itertools.permutations(range(n), 3):
        if unrelated(i, j) and unrelated(j, k) and not unrelated(i, k):
            return False
    return True


def closure(R: int, n: int) -> int:
    """Transitive closure."""
    C = R
    changed = True
    while changed:
        changed = False
        for i, j in pairs(n):
            if has(C, i, j):
                for k in range(n):
                    if k != i and k != j and has(C, j, k) and not has(C, i, k):
                        C |= bit(i, k)
                        changed = True
    return C


def is_acyclic(R: int, n: int) -> bool:
    C = closure(R, n)
    return all(not has(C, i, i) for i in range(n)) and is_asymmetric(C, n)


def is_partition(R: int, n: int) -> bool:
    """On unordered pairs: transitive as an equivalence relation."""
    for i, j, k in itertools.permutations(range(n), 3):
        if has(R, min(i, j), max(i, j)) and has(R, min(j, k), max(j, k)) and not has(R, min(i, k), max(i, k)):
            return False
    return True


def tier_set(n: int, k: int, aside: bool) -> set[int]:
    """Structures a tier board with k rows can record (with or without the aside region)."""
    out = set()
    rows = range(0 if aside else 1, k + 1)
    for assign in itertools.product(rows, repeat=n):
        R = 0
        for i, j in pairs(n):
            if assign[i] >= 1 and assign[j] >= 1 and assign[i] < assign[j]:
                R |= bit(i, j)
        out.add(R)
    return out


def partition_set(n: int) -> set[int]:
    out = set()
    for assign in itertools.product(range(n), repeat=n):
        R = 0
        for i, j in upairs(n):
            if assign[i] == assign[j]:
                R |= bit(i, j)
        out.add(R)
    return out


def linear_orders(n: int) -> list[int]:
    out = []
    for perm in itertools.permutations(range(n)):
        R = 0
        for a in range(n):
            for b in range(a + 1, n):
                R |= bit(perm[a], perm[b])
        out.append(R)
    return out


def dim_at_most_two(P: int, n: int) -> bool:
    exts = [L for L in linear_orders(n) if P & ~L == 0]
    for a in range(len(exts)):
        for b in range(a, len(exts)):
            if exts[a] & exts[b] == P:
                return True
    return False


def recordable(board_kind: str, n: int, k: int = 0) -> set[int] | None:
    """The structures a board can record on n cards, or None when the set is not enumerated."""
    if board_kind == "tier":
        return tier_set(n, k, False)
    if board_kind == "tier_aside":
        return tier_set(n, k, True)
    if board_kind == "pile":
        return partition_set(n)
    if n > MAX_ENUMERATION:
        return None
    if board_kind == "arrow":
        return set(posets(n))
    if board_kind == "plane":
        return {P for P in posets(n) if dim_at_most_two(P, n)}
    if board_kind == "pairs":
        return None  # every assignment of a state to each pair: 3^(n choose 2) records
    raise ValueError("unknown board kind: %s" % board_kind)


# ---------------------------------------------------------------- reading rules of the boards


def reading(board_kind: str, n: int, placements: Any, k: int = 0) -> dict[str, Any]:
    """Apply the reading rule of a board to a placement.

    Returns the structure, whether it is coherent (a strict partial order for the
    order boards, a partition for the pile board) and the pair kind ('prec' for
    ordered pairs, 'sim' for unordered pairs).
    """
    if not isinstance(placements, dict):
        raise ValueError("placements must be an object")
    if board_kind in ("tier", "tier_aside"):
        rows: dict[int, int | None] = {}
        for i in range(n):
            v = placements.get(str(i), placements.get(i))
            if v == "aside":
                if board_kind != "tier_aside":
                    raise ValueError("this board has no aside region")
                rows[i] = None
            else:
                r = int(v)
                if r < 0 or r >= k:
                    raise ValueError("row out of range")
                rows[i] = r
        R = 0
        for i, j in pairs(n):
            ri, rj = rows[i], rows[j]
            if ri is not None and rj is not None and ri < rj:
                R |= bit(i, j)
        return {"structure": R, "coherent": True, "judgments": "prec"}
    if board_kind == "arrow":
        arrows = placements.get("arrows", [])
        if not isinstance(arrows, list):
            raise ValueError("arrows must be a list")
        R = 0
        for a in arrows:
            i, j = int(a[0]), int(a[1])
            if i == j or i < 0 or j < 0 or i >= n or j >= n:
                raise ValueError("invalid arrow")
            R |= bit(i, j)
        return {"structure": closure(R, n), "coherent": is_acyclic(R, n), "judgments": "prec"}
    if board_kind == "pile":
        piles = {}
        for i in range(n):
            v = placements.get(str(i), placements.get(i))
            if v is None:
                raise ValueError("every card needs a pile")
            piles[i] = str(v)
        R = 0
        for i, j in upairs(n):
            if piles[i] == piles[j]:
                R |= bit(i, j)
        return {"structure": R, "coherent": True, "judgments": "sim"}
    if board_kind == "plane":
        pts = {}
        for i in range(n):
            v = placements.get(str(i), placements.get(i))
            if v is None:
                raise ValueError("every card needs a point")
            pts[i] = (float(v[0]), float(v[1]))
        R = 0
        for i, j in pairs(n):
            if pts[i][0] < pts[j][0] and pts[i][1] < pts[j][1]:
                R |= bit(i, j)
        return {"structure": R, "coherent": True, "judgments": "prec"}
    if board_kind == "pairs":
        R = 0
        undecided = []
        for i, j in upairs(n):
            v = placements.get("%d,%d" % (i, j))
            if v is None:
                raise ValueError("every pair needs an answer")
            if v == "a":
                R |= bit(i, j)
            elif v == "b":
                R |= bit(j, i)
            elif v == "undecided":
                # "cannot decide" stays outside the structure: the pair is not observed
                undecided.append((i, j))
            elif v != "apart":
                raise ValueError("invalid answer")
        return {"structure": R, "coherent": is_spo(R, n), "judgments": "prec", "undecided": undecided}
    raise ValueError("unknown board kind: %s" % board_kind)


def placements_complete(board_kind: str, n: int, placements: Any) -> bool:
    if not isinstance(placements, dict):
        return False
    if board_kind == "arrow":
        return isinstance(placements.get("arrows", None), list)
    if board_kind == "pairs":
        return all(("%d,%d" % (i, j)) in placements for i, j in upairs(n))
    return all((str(i) in placements) or (i in placements) for i in range(n))


# ---------------------------------------------------------------- pair notions


def states(P: int, n: int, judgments: str = "prec") -> list[dict[str, Any]]:
    """The state of every unordered pair."""
    out = []
    for i, j in upairs(n):
        if judgments == "sim":
            state = "tie" if has(P, i, j) else "apart"
        elif has(P, i, j):
            state = "a_prec_b"
        elif has(P, j, i):
            state = "b_prec_a"
        else:
            state = "apart"
        out.append({"a": i, "b": j, "state": state})
    return out


def related_pairs(P: int, n: int) -> int:
    return sum(1 for i, j in upairs(n) if has(P, i, j) or has(P, j, i))


def related_share(P: int, n: int) -> float:
    """Share of unordered pairs that the structure relates."""
    return related_pairs(P, n) / math.comb(n, 2)


def covering_pairs(P: int, n: int) -> set[tuple[int, int]]:
    cov = set()
    for i, j in pairs(n):
        if has(P, i, j) and not any(has(P, i, k) and has(P, k, j) for k in range(n) if k not in (i, j)):
            cov.add((min(i, j), max(i, j)))
    return cov


def critical_pairs(P: int, n: int) -> set[tuple[int, int]]:
    """Unrelated unordered pairs {a, b} whose relation would follow from no other pair.

    The confirmation questions of the arrow board ask exactly these pairs; every
    other blank pair is settled by transitivity.
    """
    crit = set()
    for a, b in pairs(n):
        if has(P, a, b) or has(P, b, a):
            continue
        Da = {x for x in range(n) if has(P, x, a)}
        Db = {x for x in range(n) if has(P, x, b)}
        Ua = {x for x in range(n) if has(P, a, x)}
        Ub = {x for x in range(n) if has(P, b, x)}
        if Da <= Db and Ub <= Ua:
            crit.add((min(a, b), max(a, b)))
    return crit


def certifying_pairs(P: int, n: int) -> set[tuple[int, int]]:
    return covering_pairs(P, n) | critical_pairs(P, n)


def observation(P: int, design: Any) -> tuple:
    return tuple((has(P, i, j), has(P, j, i)) for i, j in design)


def compatible(P: int, design: Any, n: int) -> list[int]:
    """Strict partial orders that agree with P on every pair of the design."""
    o = observation(P, design)
    return [Q for Q in posets(n) if observation(Q, design) == o]


def determined(P: int, design: Any, n: int) -> bool:
    return len(compatible(P, design, n)) == 1


# ---------------------------------------------------------------- populations of structures


def mean_structure(profile: list[int], n: int) -> dict[tuple[int, int], float]:
    N = len(profile)
    return {p: (sum(has(C, *p) for C in profile) / N if N else 0.0) for p in pairs(n)}


def pair_shares(profile: list[int], n: int) -> list[dict[str, Any]]:
    """Per unordered pair, the shares of a-before-b, b-before-a and apart."""
    N = len(profile)
    out = []
    for i, j in upairs(n):
        ab = sum(1 for C in profile if has(C, i, j))
        ba = sum(1 for C in profile if has(C, j, i))
        apart = N - ab - ba
        shares = [ab / N, ba / N, apart / N] if N else [0.0, 0.0, 0.0]
        kind = "contested"
        if N and (ab == N or ba == N):
            kind = "shared relation"
        elif N and apart == N:
            kind = "shared non-relation"
        out.append({"a": i, "b": j, "a_prec_b": shares[0], "b_prec_a": shares[1], "apart": shares[2], "kind": kind})
    return out


def common_part(profile: list[int]) -> int:
    """Statements every structure of the profile holds."""
    if not profile:
        return 0
    K = profile[0]
    for C in profile[1:]:
        K &= C
    return K


def union(profile: list[int]) -> int:
    U = 0
    for C in profile:
        U |= C
    return U


def threshold_structure(profile: list[int], n: int, theta: float) -> int:
    """Statements held by more than a share theta of the profile."""
    p = mean_structure(profile, n)
    R = 0
    for q, share in p.items():
        if share > theta + 1e-12:
            R |= bit(*q)
    return R


def total_distance(C: int, profile: list[int]) -> int:
    return sum(dist(C, D) for D in profile)


def nearest_common(profile: list[int], n: int, cls: Any = None) -> dict[str, Any]:
    """Strict partial orders with the least total distance to the profile."""
    N = len(profile)
    if cls is None:
        if n > MAX_ENUMERATION:
            return {"structures": None, "total": None, "mean_distance": None, "enumerated": False}
        cls = posets(n)
    best = None
    found: list[int] = []
    for C in cls:
        v = total_distance(C, profile)
        if best is None or v < best:
            best, found = v, [C]
        elif v == best:
            found.append(C)
    return {"structures": found, "total": best, "mean_distance": (best / N if N else None), "enumerated": True}


def distance_floor(profile: list[int], n: int) -> float:
    p = mean_structure(profile, n)
    return sum(min(v, 1 - v) for v in p.values())


def agreement(profile: list[int], n: int) -> float:
    p = mean_structure(profile, n)
    return sum((2 * v - 1) ** 2 for v in p.values()) / len(p)


def mean_pairwise(profile: list[int]) -> dict[str, float]:
    N = len(profile)
    if N == 0:
        return {"with_replacement": 0.0, "distinct": 0.0}
    D = [[dist(x, y) for y in profile] for x in profile]
    withr = sum(map(sum, D)) / N ** 2
    distinct = (sum(D[i][j] for i in range(N) for j in range(i + 1, N)) / math.comb(N, 2)) if N > 1 else 0.0
    return {"with_replacement": withr, "distinct": distinct}


def distance_to(C: int, targets: list[int]) -> dict[str, Any]:
    """Distance to the nearest target structure, with what C adds and what it lacks."""
    best = min(targets, key=lambda X: dist(C, X))
    return {"distance": dist(C, best), "nearest": best, "adds": C & ~best, "lacks": best & ~C}


def single_moves(C: int, cls: Any) -> list[int]:
    return [X for X in cls if dist(X, C) == 1]


def single_change_effects(profile: list[int], n: int) -> dict[str, Any]:
    """Changes of one statement by one respondent that change the nearest common structure."""
    cls = posets(n)
    base = nearest_common(profile, n, cls)["structures"]
    changing = []
    for s, C in enumerate(profile):
        for X in single_moves(C, cls):
            new = list(profile)
            new[s] = X
            after = nearest_common(new, n, cls)["structures"]
            if after != base:
                changing.append({"respondent": s, "from": C, "to": X, "after": after})
    return {"one_change_suffices": bool(changing), "changes": changing}


def group_totals(profile: list[int], n: int, kmax: int | None = None) -> list[int]:
    """Least total distance when the profile is split into k groups, each with its own structure."""
    N = len(profile)
    cls = posets(n)
    kmax = N if kmax is None else min(kmax, N)

    def parts(items, k):
        if not items:
            yield []
            return
        for part in parts(items[1:], k):
            for i in range(len(part)):
                yield part[:i] + [[items[0]] + part[i]] + part[i + 1:]
            if len(part) < k:
                yield [[items[0]]] + part

    def one(group):
        return min(sum(dist(X, profile[s]) for s in group) for X in cls)

    out = []
    for k in range(1, kmax + 1):
        out.append(min(sum(one(g) for g in part) for part in parts(list(range(N)), k)))
    return out


# ---------------------------------------------------------------- summaries for the researcher pages


def statement_words(P: int, n: int, labels: list[str], judgments: str, word_before: str, word_with: str) -> list[str]:
    if judgments == "sim":
        return ["%s %s %s" % (labels[i], word_with, labels[j]) for i, j in to_upairs(P, n)]
    return ["%s %s %s" % (labels[i], word_before, labels[j]) for i, j in to_pairs(P, n)]


def population_summary(profile: list[int], n: int) -> dict[str, Any]:
    """Quantities shown on the monitor page for a board task (ordered pairs)."""
    N = len(profile)
    out: dict[str, Any] = {"n": n, "N": N}
    if N == 0:
        return out
    out["mean"] = mean_structure(profile, n)
    out["pair_shares"] = pair_shares(profile, n)
    out["common_part"] = common_part(profile)
    out["majority"] = threshold_structure(profile, n, 0.5)
    out["majority_coherent"] = is_spo(out["majority"], n)
    out["distance_floor"] = distance_floor(profile, n)
    out["agreement"] = agreement(profile, n)
    out["pairwise"] = mean_pairwise(profile)
    out["related_share"] = [related_share(C, n) for C in profile]
    near = nearest_common(profile, n)
    out["enumerated"] = near["enumerated"]
    if near["enumerated"]:
        out["nearest"] = near["structures"]
        out["total"] = near["total"]
        out["mean_distance"] = near["mean_distance"]
        out["distances"] = [distance_to(C, near["structures"])["distance"] for C in profile]
    return out
