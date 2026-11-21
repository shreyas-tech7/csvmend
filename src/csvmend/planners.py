"""Planners turn a profile and the user's schema into a plan. They never see or edit data
beyond what they are given, and a plan is only data.

- `noop_plan`: an empty plan. It measures how messy the input is.
- `rule_plan`: the rule baseline. It maps profile patterns to operations.
- `LLMPlanner`: builds a prompt from the profile and at most 20 sample rows, then asks a
  model (record mode) or reads a saved answer (replay mode).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

from .plan import OPS, apply_header
from .profiler import SAMPLE_ROWS

DATE_SHAPES = {
    "9999-99-99": "%Y-%m-%d",
    "9999/99/99": "%Y/%m/%d",
    "99/99/9999": "%m/%d/%Y",
    "99.99.9999": "%d.%m.%Y",
    "99 Aa 9999": "%d %b %Y",
    "Aa 99, 9999": "%b %d, %Y",
}
SEPARATORS = [", ", " ", "-", "/", "|", ";"]


def snake(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", name.strip().lower()).strip("_")


def noop_plan(profile: dict, schema: dict) -> dict:
    return {"version": 1, "steps": []}


def _sep_of(values: list[str]) -> str | None:
    values = [v for v in values if v.strip()]
    for sep in SEPARATORS:
        if values and sum(sep in v for v in values) >= 0.8 * len(values):
            return sep
    return None


def _close(value: str, allowed: list[str]) -> str | None:
    v = re.sub(r"\s+", " ", value).strip().lower()
    low = {a.lower(): a for a in allowed}
    if v in low:
        return low[v]
    if v.endswith("."):
        hits = [a for k, a in low.items() if k.startswith(v[:-1]) and len(v) > 2]
        if len(hits) == 1:
            return hits[0]
    hit = difflib.get_close_matches(v, list(low), n=1, cutoff=0.75)
    return low[hit[0]] if hit else None


def rule_plan(profile: dict, schema: dict) -> dict:
    cols = schema["columns"]
    prof = {p["name"]: p for p in profile["column_profiles"]}
    steps: list[dict] = []

    def add(step: dict, why: str) -> None:
        steps.append(step | {"why": why})

    header = list(profile["header"])
    rename = {h: snake(h) for h in header if snake(h) != h}
    if rename:
        add({"op": "rename", "mapping": rename}, "header names to snake_case")
        header = [rename.get(h, h) for h in header]
        prof = {rename.get(k, k): v for k, v in prof.items()}
    if any(p["whitespace"] or p["nbsp"] or p["mojibake"] for p in prof.values()):
        mojibake = any(p["mojibake"] for p in prof.values())
        add({"op": "trim", "columns": "*", "unicode": mojibake}, "stray whitespace or bad bytes")
    if profile["ragged_rows"]:
        add({"op": "drop_rows", "where": {"ragged": True}}, "rows with the wrong field count")
    tokens = sorted({t for p in prof.values() for t in p["null_tokens"] if t.strip()})
    if tokens:
        add({"op": "fill_missing", "columns": "*", "tokens": tokens, "value": ""}, "null words")

    # Structure: join split columns first, then split merged ones.
    missing = [c for c in cols if c not in header]
    for target in list(missing):
        parts = [h for h in header if h.startswith(target + "_") and h not in cols]
        if len(parts) >= 2:
            sep = _sep_of([cols[target].get("example", "-")]) or "-"
            step = {"op": "merge_columns", "columns": parts, "into": target, "sep": sep}
            add(step, f"rebuild {target}")
            header = apply_header(step, header)
            missing.remove(target)
    for extra in [h for h in header if h not in cols]:
        if len(missing) < 2:
            break
        p = prof[extra]
        values = list(p.get("top_values", {})) + p["examples"] + list(p["shapes"])
        sep = _sep_of(values)
        if sep is None:
            continue
        into = missing[:2]
        step = {"op": "split_column", "column": extra, "into": into, "sep": sep}
        add(step, f"split {extra}")
        header = apply_header(step, header)
        missing = missing[2:]

    for c, spec in cols.items():
        if c not in header or c not in prof:
            continue
        p = prof[c]
        if spec["type"] == "date":
            fmts = [DATE_SHAPES[s] for s in p["shapes"] if s in DATE_SHAPES]
            if any(f != "%Y-%m-%d" for f in fmts):
                fmts = ["%Y-%m-%d"] + [f for f in fmts if f != "%Y-%m-%d"]
                add({"op": "parse_dates", "column": c, "formats": fmts}, "mixed date formats")
        elif spec["type"] == "money":
            if p["kinds"].get("money") or any("," in s for s in p["shapes"]):
                add({"op": "normalize_currency", "column": c, "decimals": 2}, "money formats")
        elif spec.get("unit") and p["kinds"].get("number_with_unit"):
            step = {"op": "convert_units", "column": c, "to": spec["unit"], "decimals": 2}
            add(step, f"mixed units, target {spec['unit']}")
        if "allowed" in spec and p.get("top_values"):
            mapping = {}
            for v in p["top_values"]:
                hit = _close(v, spec["allowed"])
                if hit and hit != v:
                    mapping[v] = hit
            if mapping:
                add({"op": "map_values", "column": c, "mapping": mapping}, "typos and case")
        if spec["type"] == "int" and p["kinds"].get("float"):
            add({"op": "cast", "column": c, "type": "int"}, "whole numbers written as decimals")
    dedupe = [c for c in schema["dedupe_on"] if c in header]
    if dedupe:
        add({"op": "fuzzy_dedupe", "columns": dedupe, "threshold": 0.92}, "near duplicate rows")
    return {"version": 1, "steps": steps}


# ---------- LLM planner ----------

INSTRUCTIONS = """You clean one CSV file by writing a plan. You never edit data yourself.
A plan is JSON: {"version": 1, "steps": [ ... ]}. Each step is {"op": <name>, ...args, "why": <short reason>}.
Steps run in order on the whole file. Use only these 12 operations and arguments:
OPS_HERE
Goal: the output must match the target schema below (column names, types, allowed values,
units, dates as YYYY-MM-DD, money as plain numbers with 2 decimals). Remove near duplicate
rows with fuzzy_dedupe on the schema's dedupe_on columns. Leave lost values empty.
You see a profile of every column and at most 20 sample rows. Answer with the JSON plan only."""


def _ops_text() -> str:
    lines = []
    for name, spec in OPS.items():
        args = ", ".join(f"{a}{'' if req else '?'}" for a, (_, req, _d) in spec.items())
        lines.append(f"- {name}({args})")
    return "\n".join(lines)


def build_prompt(profile: dict, rows: list[list[str]], schema: dict) -> str:
    """The whole model input. It holds the schema, the profile and the sample rows only."""
    if len(rows) > SAMPLE_ROWS:
        raise ValueError(f"the prompt may hold at most {SAMPLE_ROWS} rows")
    sample = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    return "\n\n".join(
        [
            INSTRUCTIONS.replace("OPS_HERE", _ops_text()),
            "TARGET SCHEMA\n" + json.dumps(schema, ensure_ascii=False),
            "PROFILE\n" + json.dumps(profile, ensure_ascii=False),
            f"SAMPLE ROWS ({len(rows)} of {profile['rows']}, header first)\n"
            + json.dumps(profile["header"], ensure_ascii=False)
            + "\n"
            + sample,
        ]
    )


def parse_plan(text: str) -> dict:
    """Pull the first JSON object out of a model answer."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in the answer")
    return json.loads(m.group())


PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
}


class LLMPlanner:
    """mode="replay" reads <fixtures>/<provider>-<model>/<dataset>.json. mode="record" calls
    the provider and saves the answer there first. A fixture stores the prompt's sha256, so a
    changed prompt cannot reuse an old answer."""

    def __init__(self, provider: str, model: str, fixtures: Path, mode: str = "replay"):
        self.provider, self.model, self.mode = provider, model, mode
        self.dir = Path(fixtures) / re.sub(r"[^\w.-]+", "_", f"{provider}-{model}")

    def _call(self, prompt: str) -> str:
        url, key_var = PROVIDERS[self.provider]
        headers = {"Content-Type": "application/json"}
        if os.environ.get(key_var):
            headers["Authorization"] = f"Bearer {os.environ[key_var]}"
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(url, json.dumps(body).encode(), headers)  # noqa: S310
        wait = 5
        for _ in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                    return json.loads(resp.read())["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                time.sleep(wait)
                wait *= 2
        raise RuntimeError("rate limited 5 times")

    def plan(self, name: str, profile: dict, rows: list[list[str]], schema: dict) -> dict:
        prompt = build_prompt(profile, rows, schema)
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        path = self.dir / f"{name}.json"
        if self.mode == "record":
            answer = self._call(prompt)
            self.dir.mkdir(parents=True, exist_ok=True)
            rec = {"model": self.model, "prompt_sha256": digest, "answer": answer}
            path.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        rec = json.loads(path.read_text())
        if rec["prompt_sha256"] != digest:
            raise ValueError(f"fixture {path.name} was recorded for a different prompt")
        return parse_plan(rec["answer"])
