"""Block designs and the reading of block tasks.

Two block techniques share the design machinery:

* Subjective Order Blocks: the respondent sorts the k items of a block into k
  strata (lower stratum first) or into a side bin; two items in one stratum or
  in the side bin are recorded as incomparable.
* Tap-order blocks: the respondent taps the cards of a block in order (first tap
  first); an optional anchor card appears in every block, so every item is also
  ordered against a fixed reference card.

Designs are balanced incomplete block designs (v, k, lambda): v items in blocks
of k, every item in r blocks, every pair of items together in lambda blocks.
"""
from __future__ import annotations

import csv
import itertools
import json
import random
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

DESIGN_DIR = Path(__file__).resolve().parent / "designs"

# Designs that the library constructs directly in addition to the published scan.
EXTRA_DESIGNS: dict[str, list[list[int]]] = {
    # Fano plane: 7 items, 7 blocks of 3, every pair once
    "v7_k3_lambda1": [[0, 1, 2], [0, 3, 4], [0, 5, 6], [1, 3, 5], [1, 4, 6], [2, 3, 6], [2, 4, 5]],
}


def design_key(v: int, k: int, lam: int) -> str:
    return f"v{v}_k{k}_lambda{lam}"


@lru_cache(maxsize=1)
def design_library() -> dict[str, dict[str, Any]]:
    """Every design the system offers, keyed by v, k and lambda, each verified on load."""
    blocks: dict[str, list[list[int]]] = {}
    path = DESIGN_DIR / "bibd_constructed_blocks.json"
    if path.exists():
        blocks.update(json.loads(path.read_text(encoding="utf-8")))
    blocks.update(EXTRA_DESIGNS)
    notes: dict[str, str] = {}
    rec = DESIGN_DIR / "bibd_recommended.csv"
    if rec.exists():
        with rec.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                notes[design_key(int(row["v"]), int(row["k"]), int(row["lambda"]))] = row.get("recommendation", "")
    out = {}
    for key, bl in blocks.items():
        v = 1 + max(max(b) for b in bl)
        check = verify_index_blocks(bl, v)
        if not check["balanced"]:
            continue
        out[key] = {
            "key": key,
            "v": v,
            "k": check["k"],
            "lambda": check["lambda"],
            "r": check["r"],
            "b": len(bl),
            "blocks": bl,
            "recommendation": notes.get(key, "constructed" if key in EXTRA_DESIGNS else ""),
        }
    return dict(sorted(out.items(), key=lambda kv: (kv[1]["v"], kv[1]["k"], kv[1]["lambda"])))


def designs_for(v: int) -> list[dict[str, Any]]:
    return [d for d in design_library().values() if d["v"] == v]


def verify_index_blocks(blocks: list[list[int]], v: int) -> dict[str, Any]:
    sizes = {len(b) for b in blocks}
    k = next(iter(sizes)) if len(sizes) == 1 else 0
    pc = Counter(p for b in blocks for p in itertools.combinations(sorted(b), 2))
    rc = Counter(i for b in blocks for i in b)
    lambdas = {pc.get(p, 0) for p in itertools.combinations(range(v), 2)}
    rs = {rc.get(i, 0) for i in range(v)}
    balanced = bool(k) and len(lambdas) == 1 and len(rs) == 1 and 0 not in lambdas
    return {
        "k": k,
        "lambda": next(iter(lambdas)) if len(lambdas) == 1 else None,
        "r": next(iter(rs)) if len(rs) == 1 else None,
        "balanced": balanced,
    }


def verify_blocks(blocks: list[list[str]], codes: list[str], technique: str = "sob") -> dict[str, Any]:
    """Check a block schedule over item codes; returns parameters and messages.

    Messages are codes with arguments, so the interface can show them in any language.
    """
    messages: list[dict[str, Any]] = []
    if not blocks:
        return {"v": len(codes), "k": 0, "lambda": None, "r": None, "b": 0, "balanced": False,
                "messages": [{"code": "no_blocks"}]}
    code_set = set(codes)
    sizes = {len(b) for b in blocks}
    k = next(iter(sizes)) if len(sizes) == 1 else 0
    if len(sizes) != 1:
        messages.append({"code": "unequal_blocks"})
    for idx, block in enumerate(blocks, start=1):
        if len(set(block)) != len(block):
            messages.append({"code": "repeated_item", "block": idx})
        unknown = [c for c in block if c not in code_set]
        if unknown:
            messages.append({"code": "unknown_items", "block": idx, "items": unknown})
    rc = Counter(c for b in blocks for c in b)
    absent = [c for c in codes if rc[c] == 0]
    if absent:
        messages.append({"code": "absent_items", "items": absent})
    pc: Counter = Counter()
    for block in blocks:
        for p in itertools.combinations(sorted(block), 2):
            if p[0] in code_set and p[1] in code_set:
                pc[p] += 1
    lambdas = [pc[p] for p in itertools.combinations(sorted(codes), 2)]
    lam = lambdas[0] if lambdas and len(set(lambdas)) == 1 else None
    rs = {rc[c] for c in codes}
    r = next(iter(rs)) if len(rs) == 1 else None
    if lam is None:
        messages.append({"code": "unbalanced_pairs"})
    elif lam == 0:
        messages.append({"code": "pairs_never_together"})
    elif lam % 2 == 0:
        messages.append({"code": "even_lambda", "lambda": lam})
    if technique == "sob" and k and k not in (3, 4):
        messages.append({"code": "sob_block_size", "k": k})
    if technique == "tap" and k and k > 6:
        messages.append({"code": "tap_block_size", "k": k})
    balanced = lam is not None and lam > 0 and r is not None and k > 0
    return {"v": len(codes), "k": k, "lambda": lam, "r": r, "b": len(blocks), "balanced": balanced, "messages": messages}


def blocks_from_design(key: str, codes: list[str]) -> list[list[str]]:
    d = design_library()[key]
    if d["v"] != len(codes):
        raise ValueError("design %s needs %d items, the task has %d" % (key, d["v"], len(codes)))
    return [[codes[i] for i in b] for b in d["blocks"]]


# ---------------------------------------------------------------- schedules for one respondent


def build_schedule(blocks: list[list[str]], rng: random.Random, *, shuffle_blocks: bool = True,
                   shuffle_cards: bool = True, duplicates: int = 0, attention: int = 0,
                   attention_code: str = "ATTN", anchor_code: str | None = None) -> list[dict[str, Any]]:
    """The sequence of screens of a block task for one respondent.

    Every entry records the design block it shows, the order of the cards on the
    screen, whether it repeats an earlier block and whether it is an attention block.
    The anchor card, when the task has one, is always shown last.
    """
    order = list(range(len(blocks)))
    if shuffle_blocks:
        rng.shuffle(order)
    entries: list[dict[str, Any]] = [{"design_block": i, "items": list(blocks[i]), "repeat_of": None, "attention": False} for i in order]
    for _ in range(min(duplicates, len(blocks))):
        candidates = [e["design_block"] for e in entries if e["repeat_of"] is None and not e["attention"]
                      and not any(x["repeat_of"] == e["design_block"] for x in entries)]
        if not candidates:
            break
        src = rng.choice(candidates)
        pos_src = next(i for i, e in enumerate(entries) if e["design_block"] == src and e["repeat_of"] is None)
        lo = min(pos_src + 3, len(entries))
        pos = rng.randint(lo, len(entries))
        entries.insert(pos, {"design_block": src, "items": list(blocks[src]), "repeat_of": src, "attention": False})
    for _ in range(attention):
        src = rng.randrange(len(blocks))
        pos = rng.randint(1, len(entries)) if entries else 0
        entries.insert(pos, {"design_block": src, "items": list(blocks[src]) + [attention_code], "repeat_of": None, "attention": True})
    for e in entries:
        cards = list(e["items"])
        if shuffle_cards:
            rng.shuffle(cards)
        if anchor_code:
            cards.append(anchor_code)
        e["cards"] = cards
    for pos, e in enumerate(entries):
        e["position"] = pos
    return entries


# ---------------------------------------------------------------- reading of block responses


def read_sob(cards: list[str], placements: dict[str, Any], k: int) -> list[dict[str, Any]]:
    """Pair observations of a Subjective Order Blocks screen.

    A lower stratum is foundational to a higher one; the same stratum or the side
    bin records the pair as incomparable.
    """
    for c in cards:
        v = placements.get(c)
        if v is None:
            raise ValueError("every item needs a stratum or the side bin")
        if v != "side":
            t = int(v)
            if t < 0 or t >= k:
                raise ValueError("stratum out of range")
    out = []
    for a, b in itertools.combinations(cards, 2):
        pa, pb = placements[a], placements[b]
        relation = "incomparable"
        if pa != "side" and pb != "side":
            ta, tb = int(pa), int(pb)
            if ta < tb:
                relation = "a_prec_b"
            elif tb < ta:
                relation = "b_prec_a"
        out.append({"item_a": a, "item_b": b, "relation": relation})
    return out


def read_tap(cards: list[str], taps: list[str]) -> dict[str, Any]:
    """Reading of a tap-order screen: the tapped sequence is a full order of the cards."""
    if sorted(taps) != sorted(cards) or len(set(taps)) != len(taps):
        raise ValueError("every card must be tapped exactly once")
    rank = {c: i for i, c in enumerate(taps)}
    obs = []
    for a, b in itertools.combinations(cards, 2):
        obs.append({"item_a": a, "item_b": b, "relation": "a_prec_b" if rank[a] < rank[b] else "b_prec_a"})
    return {"order": list(taps), "rank": rank, "pairs": obs}


def anchor_positions(taps: list[str], anchor_code: str) -> dict[str, int]:
    """For each card, +1 when tapped before the anchor, -1 when after."""
    if anchor_code not in taps:
        return {}
    a = taps.index(anchor_code)
    return {c: (1 if i < a else -1) for i, c in enumerate(taps) if c != anchor_code}


def attention_passed(taps: list[str], attention_code: str, where: str = "last") -> bool:
    if attention_code not in taps:
        return False
    if where == "first":
        return taps[0] == attention_code
    return taps[-1] == attention_code


def pair_tallies(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per respondent, the share of observations of each state for every pair of items."""
    tally: dict[tuple[str, str], Counter] = {}
    for o in observations:
        a, b = o["item_a"], o["item_b"]
        key = (a, b) if a <= b else (b, a)
        rel = o["relation"]
        if (a, b) != key:
            rel = {"a_prec_b": "b_prec_a", "b_prec_a": "a_prec_b"}.get(rel, rel)
        tally.setdefault(key, Counter())[rel] += 1
    out = []
    for (a, b), c in sorted(tally.items()):
        m = sum(c.values())
        out.append({"item_a": a, "item_b": b, "observations": m,
                    "a_prec_b": c["a_prec_b"] / m, "b_prec_a": c["b_prec_a"] / m,
                    "incomparable": c["incomparable"] / m})
    return out


def cyclic_triads(order_pairs: dict[tuple[str, str], int], items: list[str]) -> int:
    """Number of cyclic triads in a tournament given as majority preferences.

    order_pairs[(a, b)] is +1 when a is (by majority) before b, -1 when after,
    0 when tied; ties are skipped.
    """
    def before(x: str, y: str) -> int:
        if (x, y) in order_pairs:
            return order_pairs[(x, y)]
        if (y, x) in order_pairs:
            return -order_pairs[(y, x)]
        return 0

    n = 0
    for x, y, z in itertools.combinations(items, 3):
        a, b, c = before(x, y), before(y, z), before(z, x)
        if a and b and c and a == b == c:
            n += 1
    return n
