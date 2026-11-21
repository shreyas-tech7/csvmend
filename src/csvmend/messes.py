"""Seeded mess generator. It starts from a clean table, applies named messes and keeps the
clean table as ground truth.

The ground truth for a value that a mess destroys (a blanked cell) is an empty cell, because
no cleaner can know the old value. Every other cell keeps its clean value.
"""

from __future__ import annotations

import csv
import io
import json
import random
import re
from datetime import date
from pathlib import Path

from .tables import SCHEMAS, clean_table

MESSES = [
    "mixed_dates",
    "currency",
    "category_typos",
    "near_duplicates",
    "unit_mismatch",
    "split_merge",
    "whitespace_encoding",
    "missing_values",
    "shifted_rows",
]
NULL_TOKENS = ["", "N/A", "null", "-", "?", "NaN"]
DATE_FORMATS = ["%m/%d/%Y", "%d.%m.%Y", "%d %b %Y", "%b %d, %Y", "%Y/%m/%d"]
# Structural messes: (kind, sources, new column(s), separator). "merge" joins clean columns
# into one messy column. "split" breaks one clean column into two messy columns.
STRUCTURE = {
    "customers": [
        ("merge", ["first_name", "last_name"], "name", " "),
        ("split", ["phone"], ["phone_area", "phone_line"], "-"),
    ],
    "orders": [("merge", ["ship_city", "ship_state"], "ship_to", ", ")],
    "inventory": [("split", ["sku"], ["sku_prefix", "sku_number"], "-")],
}
SOFT = {
    "customers": ["first_name", "last_name"],
    "orders": ["category"],
    "inventory": ["product_name"],
}


def _typo(rng: random.Random, s: str) -> str:
    kinds = ["lower", "upper", "swap", "drop", "double", "abbrev"]
    k = rng.choice(kinds)
    if len(s) < 4 or k == "lower":
        return s.lower()
    if k == "upper":
        return s.upper()
    i = rng.randrange(1, len(s) - 1)
    if k == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2 :]
    if k == "drop":
        return s[:i] + s[i + 1 :]
    if k == "double":
        return s[:i] + s[i] + s[i:]
    return s[:4] + "."


def _money(rng: random.Random, v: float) -> str:
    style = rng.randrange(5)
    if style == 0:
        return f"${v:,.2f}"
    if style == 1:
        return f"US$ {v:.2f}"
    if style == 2:
        return f"USD {v:,.2f}"
    us = f"{v:,.2f}"
    eu = us.replace(",", "_").replace(".", ",").replace("_", ".")
    return eu if style == 3 else eu.replace(".", " ") + " $"


def _weight(rng: random.Random, kg: float) -> str:
    style = rng.randrange(3)
    if style == 0:
        return f"{kg / 0.45359237:.3f} lb"
    if style == 1:
        return f"{round(kg * 1000)} g"
    return f"{kg:.2f} kg"


def _mojibake(s: str) -> str:
    try:
        return s.encode("utf-8").decode("cp1252")
    except UnicodeDecodeError:
        return s


def _header_variant(rng: random.Random, name: str) -> str:
    words = name.split("_")
    style = rng.randrange(3)
    if style == 0:
        return " ".join(w.capitalize() for w in words)
    if style == 1:
        return name.upper()
    return f" {name} "


def make_dataset(kind: str, seed: int, messes: list[str], n: int = 80, rate: float = 0.3):
    """Build one messy dataset.

    Returns (messy_header, messy_rows, encoding, truth). messy_rows are lists of strings and
    can be ragged. truth holds the clean rows, the source of every messy row and the cells
    that each mess touched.
    """
    rng = random.Random(f"mess:{kind}:{seed}:{','.join(messes)}")
    header, clean = clean_table(kind, seed, n)
    schema = SCHEMAS[kind]
    cols = schema["columns"]
    key = schema["key"]
    truth_rows = [dict(r) for r in clean]
    recs = [{"rid": i, "uid": i, "copy": False, "v": dict(r)} for i, r in enumerate(clean)]
    touched: dict[str, set] = {m: set() for m in messes}
    touched_rows: dict[str, set] = {m: set() for m in messes}
    structure = STRUCTURE[kind] if "split_merge" in messes else []
    struct_cols = {c for s in structure for c in s[1]}

    def touch(m, rec, col):
        touched[m].add((rec["rid"], col))
        touched_rows[m].add(rec["rid"])

    if "missing_values" in messes:
        pool = [c for c in header if c != key and c not in struct_cols]
        for rec in recs:
            if rng.random() < rate:
                col = rng.choice(pool)
                rec["v"][col] = rng.choice(NULL_TOKENS)
                truth_rows[rec["uid"]][col] = ""
                touch("missing_values", rec, col)

    if "near_duplicates" in messes:
        next_id = n + 1
        for rec in list(recs):
            if rng.random() < rate / 2:
                v = dict(rec["v"])
                digits = re.search(r"\d+$", v[key])
                v[key] = v[key][: digits.start()] + f"{9000 + next_id:0{len(digits.group())}d}"
                next_id += 1
                col = rng.choice(SOFT[kind])
                if v[col]:
                    v[col] = _typo(rng, v[col]) if rng.random() < 0.6 else v[col].lower()
                cp = {"rid": len(recs), "uid": rec["uid"], "copy": True, "v": v}
                touched_rows["near_duplicates"].add(rec["rid"])
                pos = recs.index(rec) + 1 + rng.randrange(0, 15)
                recs.insert(min(pos, len(recs)), cp)
                cp["orig"] = rec["rid"]

    for rec in recs:
        v = rec["v"]
        for col, spec in cols.items():
            val = v[col]
            if val in NULL_TOKENS:
                continue
            if "category_typos" in messes and "allowed" in spec and rng.random() < rate:
                v[col] = _typo(rng, val)
                touch("category_typos", rec, col)
            elif "mixed_dates" in messes and spec["type"] == "date" and rng.random() < 0.5:
                v[col] = date.fromisoformat(val).strftime(rng.choice(DATE_FORMATS))
                touch("mixed_dates", rec, col)
            elif "currency" in messes and spec["type"] == "money" and rng.random() < 0.6:
                v[col] = _money(rng, float(val))
                touch("currency", rec, col)
            elif "unit_mismatch" in messes and spec.get("unit") and rng.random() < 0.6:
                v[col] = _weight(rng, float(val))
                touch("unit_mismatch", rec, col)
        if "whitespace_encoding" in messes:
            for col, spec in cols.items():
                val = v[col]
                if col == key or spec["type"] != "str" or val in NULL_TOKENS:
                    continue
                if not val.isascii() and rng.random() < 0.6:
                    v[col] = _mojibake(val)
                    touch("whitespace_encoding", rec, col)
                elif rng.random() < rate:
                    pad = rng.choice(["  {}", "{} ", "\t{}", "{} ", "{}  "])
                    v[col] = pad.format(val.replace(" ", "  ", 1) if " " in val else val)
                    touch("whitespace_encoding", rec, col)

    messy_header = list(header)
    for kind_, sources, new, sep in structure:
        pos = messy_header.index(sources[0])
        for rec in recs:
            for c in sources:
                touch("split_merge", rec, c)
        if kind_ == "merge":
            for rec in recs:
                rec["v"][new] = sep.join(rec["v"].pop(c) for c in sources)
            messy_header[pos : pos + len(sources)] = [new]
        else:
            for rec in recs:
                parts = rec["v"].pop(sources[0]).split(sep, len(new) - 1)
                parts += [""] * (len(new) - len(parts))
                rec["v"].update(zip(new, parts, strict=True))
            messy_header[pos : pos + 1] = new

    encoding = "utf-8-sig"
    if "whitespace_encoding" in messes:
        ws_cols = [c for c in messy_header if c != key]
        for c in rng.sample(ws_cols, k=min(3, len(ws_cols))):
            i = messy_header.index(c)
            messy_header[i] = _header_variant(rng, c)
            for rec in recs:
                if c in cols:
                    touch("whitespace_encoding", rec, c)
        if rng.random() < 0.5:
            encoding = "cp1252"

    rows = []
    for rec in recs:
        rec["v"] = {
            mh: rec["v"][c] for mh, c in zip(messy_header, _orig_names(messy_header), strict=True)
        }
        row = list(rec["v"].values())
        if "shifted_rows" in messes and rng.random() < rate / 3:
            k = rng.randrange(1, len(row))
            row.insert(k, "")
            for c in cols:
                touch("shifted_rows", rec, c)
        rows.append(row)

    index = {rec["rid"]: i for i, rec in enumerate(recs)}
    truth = {
        "kind": kind,
        "seed": seed,
        "messes": messes,
        "encoding": encoding,
        "header": header,
        "rows": truth_rows,
        "row_uid": [rec["uid"] for rec in recs],
        "dup_pairs": sorted([index[rec["orig"]], index[rec["rid"]]] for rec in recs if rec["copy"]),
        "touched": {m: sorted([index[r], c] for r, c in s) for m, s in touched.items()},
        "touched_rows": {m: sorted(index[r] for r in s) for m, s in touched_rows.items()},
    }
    return messy_header, rows, encoding, truth


def _orig_names(messy_header: list[str]) -> list[str]:
    return [h.strip().lower().replace(" ", "_") for h in messy_header]


def write_csv(path: Path, header: list[str], rows: list[list[str]], encoding: str) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    text = buf.getvalue()
    try:
        data = text.encode(encoding)
    except UnicodeEncodeError:
        data = text.encode("utf-8-sig")
    path.write_bytes(data)


def write_dataset(out_dir: Path, name: str, kind: str, seed: int, messes: list[str], **kw):
    """Write <name>.csv (messy), <name>.truth.json and <name>.schema.json into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    header, rows, enc, truth = make_dataset(kind, seed, messes, **kw)
    csv_path = out_dir / f"{name}.csv"
    write_csv(csv_path, header, rows, enc)
    (out_dir / f"{name}.truth.json").write_text(json.dumps(truth, ensure_ascii=False))
    (out_dir / f"{name}.schema.json").write_text(json.dumps(SCHEMAS[kind], indent=1))
    return csv_path
