"""Run a plan on a copy of a CSV, log every change and replay a log.

The input file is opened read only and never written. Every change goes through one of the
five `Table` primitives (set, rename, add_col, drop_col, drop_row). Each primitive writes a
log entry, so the log is complete by construction. `replay` applies a log with the same
primitives and must rebuild the same output.
"""

from __future__ import annotations

import csv
import difflib
import io
import json
import re
from datetime import datetime
from pathlib import Path

from .plan import UNITS, PlanError, validate_plan

LOG_FIELDS = ["step", "op", "kind", "row", "column", "old", "new"]


def read_text(path: Path) -> tuple[str, str]:
    """Decode a CSV. Try UTF-8 (with or without a BOM), then cp1252. Return (text, encoding)."""
    data = Path(path).read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8-sig"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252"), "cp1252"


class Table:
    def __init__(self, header: list[str], rows: list[dict]):
        self.header = header
        self.rows = rows  # each row: {"src": input row number, "ragged": bool, "v": {col: str}}
        self.log: list[dict] = []
        self.step, self.op = 0, "load"

    def _entry(self, kind, row="", column="", old="", new=""):
        self.log.append(
            {"step": self.step, "op": self.op, "kind": kind, "row": row}
            | {"column": column, "old": old, "new": new}
        )

    def set(self, row: dict, col: str, new: str) -> bool:
        old = row["v"][col]
        if new == old:
            return False
        row["v"][col] = new
        self._entry("cell", row["src"], col, old, new)
        return True

    def rename(self, old: str, new: str) -> None:
        self.header[self.header.index(old)] = new
        for r in self.rows:
            r["v"] = {(new if k == old else k): x for k, x in r["v"].items()}
        self._entry("rename", "", old, old, new)

    def add_col(self, name: str, pos: int) -> None:
        self.header.insert(pos, name)
        for r in self.rows:
            r["v"][name] = ""
        self._entry("add_column", "", name, "", str(pos))

    def drop_col(self, name: str) -> None:
        self.header.remove(name)
        for r in self.rows:
            del r["v"][name]
        self._entry("drop_column", "", name, name, "")

    def drop_row(self, row: dict, reason: str) -> None:
        self.rows.remove(row)
        self._entry("drop_row", row["src"], "*", reason, "")


def load(path: Path) -> Table:
    text, enc = read_text(path)
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, [])
    t = Table(list(header), [])
    if enc != "utf-8":
        t._entry("encoding", "", "*", enc, "utf-8")
    n = len(header)
    for i, raw in enumerate(reader):
        vals = (raw + [""] * n)[:n]
        t.rows.append(
            {"src": i, "ragged": len(raw) != n, "v": dict(zip(header, vals, strict=True))}
        )
        if len(raw) != n:
            t._entry("ragged", i, "*", json.dumps(raw, ensure_ascii=False), json.dumps(vals))
    return t


def to_csv(t: Table) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(t.header)
    for r in t.rows:
        w.writerow([r["v"][c] for c in t.header])
    return buf.getvalue()


# ---------- value helpers ----------

MONEY_MARKS = re.compile(r"US\$|USD|EUR|GBP|[$€£]")


def parse_money(s: str) -> float | None:
    x = MONEY_MARKS.sub("", s).replace(" ", "").replace(" ", "").strip()
    if not x:
        return None
    if "," in x and "." in x:
        dec = "," if x.rfind(",") > x.rfind(".") else "."
    elif "," in x:
        dec = "," if re.search(r",\d{1,2}$", x) else ""
    else:
        dec = "."
    thousands = {",": ".", ".": ",", "": ","}[dec]
    x = x.replace(thousands, "").replace(dec, ".") if dec else x.replace(",", "")
    try:
        return float(x)
    except ValueError:
        return None


UNIT_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([a-zA-Z]*)\s*$")
UNIT_NAMES = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "g": "g", "gr": "g", "grams": "g",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb", "oz": "oz",
}  # fmt: skip


def parse_quantity(s: str, assume: str) -> float | None:
    m = UNIT_RE.match(s)
    if not m:
        return None
    unit = UNIT_NAMES.get(m.group(2).lower()) if m.group(2) else assume
    if unit is None:
        return None
    return float(m.group(1).replace(",", ".")) * UNITS[unit]


def fix_mojibake(s: str) -> str:
    try:
        fixed = s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s
    return fixed


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------- the 12 operations ----------


def _cols(t: Table, cols) -> list[str]:
    return list(t.header) if cols == "*" else list(cols)


def op_trim(t, s, stats):
    for c in _cols(t, s["columns"]):
        for r in t.rows:
            v = r["v"][c].replace(" ", " ")
            if s["unicode"]:
                v = fix_mojibake(v)
            stats["changed"] += t.set(r, c, re.sub(r"\s+", " ", v).strip())


def op_rename(t, s, stats):
    for old, new in s["mapping"].items():
        t.rename(old, new)
        stats["changed"] += 1


def op_parse_dates(t, s, stats):
    for r in t.rows:
        v = r["v"][s["column"]].strip()
        if not v:
            continue
        for f in s["formats"]:
            try:
                new = datetime.strptime(v, f).strftime(s["output"])
                break
            except ValueError:
                continue
        else:
            stats["failed"] += 1
            continue
        stats["changed"] += t.set(r, s["column"], new)


def op_normalize_currency(t, s, stats):
    for r in t.rows:
        v = r["v"][s["column"]]
        if not v.strip():
            continue
        x = parse_money(v)
        if x is None:
            stats["failed"] += 1
            continue
        stats["changed"] += t.set(r, s["column"], f"{x:.{s['decimals']}f}")


def op_map_values(t, s, stats):
    m = s["mapping"]
    if s["case_insensitive"]:
        m = {_norm(k): v for k, v in m.items()}
    for r in t.rows:
        v = r["v"][s["column"]]
        key = _norm(v) if s["case_insensitive"] else v
        if key in m:
            stats["changed"] += t.set(r, s["column"], m[key])


def op_fuzzy_dedupe(t, s, stats):
    cols, block = s["columns"], s["block_on"] or s["columns"][0]
    kept: dict[str, list[dict]] = {}
    for r in list(t.rows):
        key = _norm(r["v"][block])[:2]
        sig = [_norm(r["v"][c]) for c in cols]
        match = None
        for k in kept.get(key, []):
            ksig = [_norm(k["v"][c]) for c in cols]
            score = sum(
                1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()
                for a, b in zip(sig, ksig, strict=True)
            ) / len(cols)
            if score >= s["threshold"]:
                match = k
                break
        if match is None:
            kept.setdefault(key, []).append(r)
        else:
            t.drop_row(r, f"dup_of:{match['src']}")
            stats["dropped"] += 1


def op_split_column(t, s, stats):
    col, into = s["column"], s["into"]
    pos = t.header.index(col)
    for i, name in enumerate(into):
        t.add_col(name, pos + i)
    maxsplit = s["maxsplit"] or len(into) - 1
    for r in t.rows:
        parts = r["v"][col].split(s["sep"], maxsplit)
        if len(parts) > len(into):
            parts = parts[: len(into) - 1] + [s["sep"].join(parts[len(into) - 1 :])]
        for name, part in zip(into, parts + [""] * (len(into) - len(parts)), strict=True):
            stats["changed"] += t.set(r, name, part)
    t.drop_col(col)


def op_merge_columns(t, s, stats):
    pos = min(t.header.index(c) for c in s["columns"])
    t.add_col(s["into"], pos)
    for r in t.rows:
        parts = [r["v"][c] for c in s["columns"] if r["v"][c].strip()]
        stats["changed"] += t.set(r, s["into"], s["sep"].join(parts))
    for c in s["columns"]:
        t.drop_col(c)


def op_convert_units(t, s, stats):
    assume = s["assume"] or s["to"]
    for r in t.rows:
        v = r["v"][s["column"]]
        if not v.strip():
            continue
        kg = parse_quantity(v, assume)
        if kg is None:
            stats["failed"] += 1
            continue
        stats["changed"] += t.set(r, s["column"], f"{kg / UNITS[s['to']]:.{s['decimals']}f}")


def op_fill_missing(t, s, stats):
    tokens = {_norm(x) for x in s["tokens"]}
    for c in _cols(t, s["columns"]):
        for r in t.rows:
            if _norm(r["v"][c]) in tokens:
                stats["changed"] += t.set(r, c, s["value"])


def op_drop_rows(t, s, stats):
    w = s["where"]
    for r in list(t.rows):
        if w.get("ragged"):
            hit = r["ragged"]
        elif "equals" in w:
            hit = r["v"][w["column"]] == w["equals"]
        else:
            hit = not r["v"][w["column"]].strip()
        if hit:
            t.drop_row(r, "where:" + json.dumps(w, sort_keys=True))
            stats["dropped"] += 1


def op_cast(t, s, stats):
    for r in t.rows:
        v = r["v"][s["column"]].strip()
        if not v or s["type"] == "str":
            continue
        try:
            x = float(v)
        except ValueError:
            stats["failed"] += 1
            continue
        if s["type"] == "int":
            if not x.is_integer():
                stats["failed"] += 1
                continue
            new = str(int(x))
        else:
            new = f"{x:.{s['decimals']}f}"
        stats["changed"] += t.set(r, s["column"], new)


RUNNERS = {name[3:]: fn for name, fn in globals().items() if name.startswith("op_")}


def execute(t: Table, steps: list[dict]) -> list[dict]:
    """Run checked steps on a loaded table. Return one stats record per step."""
    report = []
    for i, s in enumerate(steps, 1):
        t.step, t.op = i, s["op"]
        stats = {"step": i, "op": s["op"], "changed": 0, "failed": 0, "dropped": 0}
        RUNNERS[s["op"]](t, s, stats)
        report.append(stats)
    return report


def run(input_path: Path, plan: dict, out_dir: Path) -> dict:
    """Run a plan on a copy of input_path. Write clean.csv, plan.json, changes.csv, run.json."""
    input_path, out_dir = Path(input_path).resolve(), Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    t = load(input_path)
    steps, errors = validate_plan(plan, t.header)
    if errors:
        raise PlanError("; ".join(errors))
    outputs = {n: out_dir / n for n in ("clean.csv", "plan.json", "changes.csv", "run.json")}
    if input_path in outputs.values():
        raise PlanError("the output folder would overwrite the input file")
    report = execute(t, steps)
    outputs["clean.csv"].write_text(to_csv(t), encoding="utf-8")
    outputs["plan.json"].write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    write_log(outputs["changes.csv"], t.log)
    result = {
        "input": str(input_path),
        "rows_in": len(load(input_path).rows),
        "rows_out": len(t.rows),
        "kept_rows": [r["src"] for r in t.rows],
        "steps": report,
        "log_entries": len(t.log),
    }
    outputs["run.json"].write_text(json.dumps(result, indent=1) + "\n")
    return result


def write_log(path: Path, log: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, LOG_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(log)


def read_log(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def replay(input_path: Path, log: list[dict]) -> str:
    """Apply a change log to the input with the same primitives. Return the output CSV text.

    Each cell entry must find its recorded old value, so a log that does not match the input
    fails loudly instead of producing a different file.
    """
    t = load(input_path)
    by_src = {r["src"]: r for r in t.rows}
    for e in log:
        kind = e["kind"]
        if kind in ("encoding", "ragged"):
            continue
        if kind == "cell":
            r = by_src[int(e["row"])]
            if r["v"][e["column"]] != e["old"]:
                raise PlanError(f"log does not match input at row {e['row']} {e['column']}")
            t.set(r, e["column"], e["new"])
        elif kind == "rename":
            t.rename(e["old"], e["new"])
        elif kind == "add_column":
            t.add_col(e["column"], int(e["new"]))
        elif kind == "drop_column":
            t.drop_col(e["column"])
        elif kind == "drop_row":
            t.drop_row(by_src[int(e["row"])], e["old"])
        else:
            raise PlanError(f"unknown log entry kind {kind!r}")
    return to_csv(t)
