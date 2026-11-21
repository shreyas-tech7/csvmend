"""Score a cleaned table against the generator's ground truth.

- cell accuracy: share of cells in recovered rows that equal the clean value
- row recall: share of clean rows that appear in the output
- duplicate F1: over (kept row, dropped row) pairs from the dedupe step

Numbers compare with a small tolerance (0.006) because unit round trips can move the
third decimal. Everything else compares as exact strings.
"""

from __future__ import annotations

from .tables import SCHEMAS

TOL = 0.006


def same(out: str, truth: str, kind: str) -> bool:
    if out == truth:
        return True
    if kind in ("int", "float", "money") and out and truth:
        try:
            return abs(float(out) - float(truth)) <= TOL
        except ValueError:
            return False
    return False


def score(header: list[str], rows: list[list[str]], kept: list[int], log: list[dict], truth):
    """rows are the output rows, kept[i] is the input row number of rows[i]."""
    cols = SCHEMAS[truth["kind"]]["columns"]
    uid_of = truth["row_uid"]
    pos = {c: header.index(c) for c in cols if c in header}
    first: dict[int, int] = {}
    for i, src in enumerate(kept):
        first.setdefault(uid_of[src], i)
    at = {src: i for i, src in enumerate(kept)}

    def ok_at(i: int, uid: int, col: str) -> bool:
        if col not in pos:
            return False
        return same(rows[i][pos[col]].strip(), truth["rows"][uid][col], cols[col]["type"])

    res = {}
    n_truth = len(truth["rows"])
    cells = [(u, c) for u in first for c in cols]
    res["all"] = {
        "cells": [sum(ok_at(first[u], u, c) for u, c in cells), len(cells)],
        "rows": [len(first), n_truth],
        "extra_rows": len(kept) - len(first),
    }
    for m in truth["messes"]:
        # A touched cell counts where its own input row landed in the output.
        touched = [(s, c) for s, c in truth["touched"][m] if s in at]
        ok = sum(ok_at(at[s], uid_of[s], c) for s, c in touched)
        rows_t = {uid_of[s] for s in truth["touched_rows"][m]}
        res[m] = {
            "cells": [ok, len(touched)],
            "rows": [sum(u in first for u in rows_t), len(rows_t)],
        }
    gold = {frozenset(p) for p in truth["dup_pairs"]}
    pred = {
        frozenset((int(e["row"]), int(e["old"].split(":")[1])))
        for e in log
        if e["kind"] == "drop_row" and str(e["old"]).startswith("dup_of:")
    }
    tp = len(gold & pred)
    res["dups"] = {"tp": tp, "fp": len(pred - gold), "fn": len(gold - pred)}
    res["dups"]["f1"] = [2 * tp, 2 * tp + res["dups"]["fp"] + res["dups"]["fn"]]
    return res
