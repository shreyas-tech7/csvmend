"""The benchmark: generated datasets with ground truth, run end to end through each planner.

40 development datasets use seeds 0 to 39 and three messes each. 24 held out datasets use
seeds 1000 to 1023, four to six messes each, a higher mess rate and only mixes that no
development dataset uses. Intervals are 95% percentile bootstrap intervals over datasets.
"""

from __future__ import annotations

import json
import platform
import random
import time
from datetime import date
from pathlib import Path

from .executor import load, read_log, run
from .messes import MESSES, write_dataset
from .plan import validate_plan
from .planners import build_prompt, noop_plan, rule_plan
from .profiler import profile, sample_rows
from .score import score
from .tables import SCHEMAS
from .verifier import verify

KINDS = ["customers", "orders", "inventory"]
BOOT = 2000


def suite(held_base: int = 1000) -> list[dict]:
    dev, seen = [], set()
    for s in range(40):
        rng = random.Random(f"dev:{s}")
        messes = sorted(rng.sample(MESSES, 3), key=MESSES.index)
        seen.add(frozenset(messes))
        dev.append(
            {"name": f"dev{s:02d}", "split": "dev", "kind": KINDS[s % 3], "seed": s}
            | {"messes": messes, "n": rng.randrange(60, 121), "rate": 0.3}
        )
    held = []
    for s in range(held_base, held_base + 24):
        rng = random.Random(f"held:{s}")
        while True:
            messes = sorted(rng.sample(MESSES, rng.randrange(4, 7)), key=MESSES.index)
            if frozenset(messes) not in seen:
                break
        held.append(
            {"name": f"held{s}", "split": "heldout", "kind": KINDS[s % 3], "seed": s}
            | {"messes": messes, "n": rng.randrange(80, 151), "rate": 0.35}
        )
    return dev + held


def run_one(ds: dict, planner, work: Path) -> dict:
    """Generate, profile, plan, validate, execute, verify and score one dataset."""
    data = work / "data"
    csv_path = data / f"{ds['name']}.csv"
    if not csv_path.exists():
        write_dataset(data, ds["name"], ds["kind"], ds["seed"], ds["messes"], n=ds["n"], rate=ds["rate"])  # fmt: skip
    truth = json.loads((data / f"{ds['name']}.truth.json").read_text())
    schema = SCHEMAS[ds["kind"]]
    out = work / "runs" / planner["name"] / ds["name"]
    t0 = time.perf_counter()
    table = load(csv_path)
    prof = profile(table, seed=ds["seed"])
    rows = sample_rows(table, seed=ds["seed"])
    prompt_chars = len(build_prompt(prof, rows, schema))
    try:
        plan = planner["fn"](ds["name"], prof, rows, schema)
        steps, errors = validate_plan(plan, table.header)
    except ValueError as e:  # no JSON in a model answer, or JSON that does not parse
        steps, errors = [], [f"unreadable answer: {e}"]
    if errors:
        plan = {"version": 1, "steps": []}
    result = run(csv_path, plan, out)
    clean = load(out / "clean.csv")
    checks = verify(clean, schema, result["rows_in"])
    ms = (time.perf_counter() - t0) * 1000
    rows = [[r["v"][c] for c in clean.header] for r in clean.rows]
    sc = score(clean.header, rows, result["kept_rows"], read_log(out / "changes.csv"), truth)
    return {
        "name": ds["name"],
        "split": ds["split"],
        "kind": ds["kind"],
        "messes": ds["messes"],
        "plan_errors": errors,
        "ops": len(steps) if not errors else 0,
        "checks_failed": [c["check"] for c in checks if not c["ok"]],
        "ms": round(ms, 1),
        "prompt_chars": prompt_chars,
        "score": sc,
    }


def _ratio(pairs):
    num, den = sum(p[0] for p in pairs), sum(p[1] for p in pairs)
    return num / den if den else None


def interval(pairs: list, seed: int = 0) -> dict:
    """Ratio of sums with a 95% bootstrap interval that resamples datasets."""
    pairs = [p for p in pairs if p[1]]
    if not pairs:
        return {"value": None, "lo": None, "hi": None, "datasets": 0, "n": 0}
    rng = random.Random(seed)
    stats = sorted(_ratio([rng.choice(pairs) for _ in pairs]) for _ in range(BOOT))
    return {
        "value": _ratio(pairs),
        "lo": stats[int(0.025 * BOOT)],
        "hi": stats[int(0.975 * BOOT) - 1],
        "datasets": len(pairs),
        "n": sum(p[1] for p in pairs),
    }


def aggregate(records: list[dict]) -> dict:
    out = {}
    for split in ("dev", "heldout"):
        recs = [r for r in records if r["split"] == split]
        if not recs:
            continue
        table = {
            "all": {
                "cells": interval([r["score"]["all"]["cells"] for r in recs]),
                "rows": interval([r["score"]["all"]["rows"] for r in recs]),
                "dup_f1": interval([r["score"]["dups"]["f1"] for r in recs]),
            }
        }
        for m in MESSES:
            mr = [r for r in recs if m in r["messes"]]
            table[m] = {
                "cells": interval([r["score"][m]["cells"] for r in mr]),
                "rows": interval([r["score"][m]["rows"] for r in mr]),
            }
            if m == "near_duplicates":
                table[m]["dup_f1"] = interval([r["score"]["dups"]["f1"] for r in mr])
        out[split] = {
            "datasets": len(recs),
            "metrics": table,
            "ops_mean": sum(r["ops"] for r in recs) / len(recs),
            "ms_mean": sum(r["ms"] for r in recs) / len(recs),
            "prompt_chars_mean": sum(r["prompt_chars"] for r in recs) / len(recs),
            "plans_rejected": sum(bool(r["plan_errors"]) for r in recs),
            "verifier_pass": sum(not r["checks_failed"] for r in recs),
        }
    return out


def planners(llm=None) -> list[dict]:
    ps = [
        {
            "name": "noop",
            "label": "no plan (input as is)",
            "fn": lambda n, p, r, s: noop_plan(p, s),
        },  # fmt: skip
        {"name": "rules", "label": "rule baseline", "fn": lambda n, p, r, s: rule_plan(p, s)},
    ]
    if llm is not None:
        ps.append({"name": "llm", "label": f"LLM {llm.model}", "fn": llm.plan})
    return ps


def bench(
    work: Path, out_file: Path, llm=None, limit: int | None = None, held_base: int = 1000
) -> dict:
    datasets = suite(held_base)[:limit] if limit else suite(held_base)
    results = {"planners": {}, "records": {}}
    work = work / f"held{held_base}"
    for p in planners(llm):
        recs = [run_one(ds, p, work) for ds in datasets]
        results["records"][p["name"]] = recs
        results["planners"][p["name"]] = {"label": p["label"]} | aggregate(recs)
    results["meta"] = {
        "date": date.today().isoformat(),
        "datasets": {
            "dev": sum(d["split"] == "dev" for d in datasets),
            "heldout": sum(d["split"] == "heldout" for d in datasets),
        },
        "generator_seeds": f"dev 0-39, heldout {held_base}-{held_base + 23}",
        "bootstrap": {"resamples": BOOT, "seed": 0},
        "cpu": _cpu(),
        "python": platform.python_version(),
        "model": llm.model if llm else None,
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    return results


def _cpu() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip() + ", 1 core used"
    except OSError:
        pass
    return platform.processor() or "unknown"
