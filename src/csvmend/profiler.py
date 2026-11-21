"""Profile a CSV: a short summary of each column that never holds the whole file.

Examples come only from a fixed sample of at most 20 rows. Top values are listed only for
low cardinality columns, so a unique id from a row outside the sample never appears.
"""

from __future__ import annotations

import random
import re
from collections import Counter

from .executor import Table, fix_mojibake

SAMPLE_ROWS = 20
MAX_TOP = 80
NULL_WORDS = {"", "n/a", "na", "null", "none", "nan", "-", "?"}
DATE_HINT = re.compile(
    r"^(\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}|\d{1,2} [A-Za-z]{3} \d{4}|[A-Za-z]{3} \d{1,2}, \d{4})$"
)
MONEY_HINT = re.compile(r"[$€£]|US\$|USD|\d,\d{2}$")
UNIT_HINT = re.compile(r"^-?\d+(?:[.,]\d+)?\s*[a-zA-Z]+$")


def shape(s: str) -> str:
    """Pattern of a value: digit runs become 9s, letter runs become 'a' or 'A'."""
    s = re.sub(r"\d", "9", s)
    s = re.sub(r"[A-Z][a-z]+", "Aa", s)
    s = re.sub(r"[a-z]+", "a", s)
    return re.sub(r"[A-Z]+", "A", s)


def kind_of(s: str) -> str:
    v = s.strip()
    if v.lower() in NULL_WORDS:
        return "null"
    if re.fullmatch(r"-?\d+", v):
        return "int"
    if re.fullmatch(r"-?\d+\.\d+", v):
        return "float"
    if DATE_HINT.match(v):
        return "date"
    if MONEY_HINT.search(v) and re.search(r"\d", v):
        return "money"
    if UNIT_HINT.match(v):
        return "number_with_unit"
    return "text"


def sample_indices(n: int, seed: int = 0, k: int = SAMPLE_ROWS) -> list[int]:
    return sorted(random.Random(seed).sample(range(n), min(k, n)))


def profile(t: Table, seed: int = 0) -> dict:
    n = len(t.rows)
    sample = sample_indices(n, seed)
    # Rows with the wrong field count put values under the wrong column, so the column
    # summaries skip them. The profile still counts them.
    good = [r for r in t.rows if not r["ragged"]] or t.rows
    cols = []
    for c in t.header:
        vals = [r["v"][c] for r in good]
        kinds = Counter(kind_of(v) for v in vals)
        nonnull = [v for v in vals if kind_of(v) != "null"]
        distinct = Counter(v.strip() for v in nonnull)
        col = {
            "name": c,
            "kinds": dict(kinds.most_common()),
            "null_rate": round(kinds.get("null", 0) / len(vals), 3) if vals else 0.0,
            "null_tokens": sorted({v for v in vals if kind_of(v) == "null"}),
            "distinct": len(distinct),
            "shapes": dict(Counter(shape(v.strip()) for v in nonnull).most_common(8)),
            "whitespace": sum(1 for v in vals if v != re.sub(r"\s+", " ", v).strip()),
            "nbsp": sum(1 for v in vals if " " in v),
            "mojibake": sum(1 for v in vals if fix_mojibake(v) != v),
            "examples": [t.rows[i]["v"][c] for i in sample[:3]],
        }
        if 0 < len(distinct) <= MAX_TOP and len(distinct) <= 0.8 * len(nonnull):
            col["top_values"] = dict(distinct.most_common())
        cols.append(col)
    return {
        "rows": n,
        "columns": len(t.header),
        "header": list(t.header),
        "encoding": next((e["old"] for e in t.log if e["kind"] == "encoding"), "utf-8"),
        "ragged_rows": sum(1 for r in t.rows if r["ragged"]),
        "sample_rows": sample,
        "column_profiles": cols,
    }


def sample_rows(t: Table, seed: int = 0) -> list[list[str]]:
    return [[t.rows[i]["v"][c] for c in t.header] for i in sample_indices(len(t.rows), seed)]
