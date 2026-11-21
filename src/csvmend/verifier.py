"""Check a cleaned table against the user's schema. It reports; it changes nothing.

Checks: the column set, the type of every non-empty cell, ranges, the unique key, allowed
values and the row count. It cannot tell a wrong value of the right type from a right one.
"""

from __future__ import annotations

import re
from datetime import date

from .executor import Table

MAX_DROP = 0.2


def _type_ok(v: str, kind: str) -> bool:
    if kind == "int":
        return re.fullmatch(r"-?\d+", v) is not None
    if kind in ("float", "money"):
        return re.fullmatch(r"-?\d+(\.\d+)?", v) is not None
    if kind == "date":
        try:
            date.fromisoformat(v)
            return re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) is not None
        except ValueError:
            return False
    return True


def verify(t: Table, schema: dict, rows_in: int) -> list[dict]:
    checks = []

    def add(name, bad, total, examples):
        checks.append(
            {"check": name, "ok": not bad, "bad": len(bad), "total": total, "examples": examples}
        )

    cols = schema["columns"]
    missing = [c for c in cols if c not in t.header]
    extra = [c for c in t.header if c not in cols]
    add("columns", missing + extra, len(cols), {"missing": missing, "extra": extra})
    for c, spec in cols.items():
        if c not in t.header:
            continue
        vals = [(r["src"], r["v"][c]) for r in t.rows if r["v"][c] != ""]
        bad = [(s, v) for s, v in vals if not _type_ok(v, spec["type"])]
        add(f"type:{c}", bad, len(vals), bad[:3])
        if "min" in spec:
            nums = [(s, float(v)) for s, v in vals if _type_ok(v, spec["type"])]
            out = [(s, v) for s, v in nums if not spec["min"] <= v <= spec["max"]]
            add(f"range:{c}", out, len(nums), out[:3])
        if "allowed" in spec:
            out = [(s, v) for s, v in vals if v not in spec["allowed"]]
            add(f"allowed:{c}", out, len(vals), out[:3])
    key = schema["key"]
    if key in t.header:
        seen, dup = set(), []
        for r in t.rows:
            k = r["v"][key]
            if k in seen or not k:
                dup.append((r["src"], k))
            seen.add(k)
        add(f"unique:{key}", dup, len(t.rows), dup[:3])
    n = len(t.rows)
    bad = [] if (1 - MAX_DROP) * rows_in <= n <= rows_in else [n]
    add("row_count", bad, rows_in, {"rows_in": rows_in, "rows_out": n, "max_drop": MAX_DROP})
    return checks


def summary(checks: list[dict]) -> str:
    failed = [c for c in checks if not c["ok"]]
    lines = [f"{len(checks) - len(failed)}/{len(checks)} checks pass"]
    lines += [f"  FAIL {c['check']}: {c['bad']} of {c['total']} {c['examples']}" for c in failed]
    return "\n".join(lines)
