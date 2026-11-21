"""Write the README number blocks and docs/index.html from the results files.

Nobody types a number into the README. `csvmend readme` fills the blocks between
`<!-- gen:NAME -->` markers, and `csvmend readme --check` fails if any block is stale.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .executor import load, read_log, run
from .messes import MESSES, write_dataset
from .planners import rule_plan
from .profiler import profile
from .tables import SCHEMAS

FINAL = Path("results/bench.json")
SECOND = Path("results/bench_seed2.json")
DEMO = {"kind": "customers", "seed": 7, "n": 10, "rate": 0.4}
DEMO["messes"] = [
    "mixed_dates",
    "currency",
    "category_typos",
    "near_duplicates",
    "split_merge",
    "whitespace_encoding",
    "missing_values",
]
LABEL = {m: m.replace("_", " ") for m in MESSES}


def pct(x: dict | None) -> str:
    if not x or x["value"] is None:
        return "n/a"
    return f"{100 * x['value']:.1f}% ({100 * x['lo']:.1f} to {100 * x['hi']:.1f})"


def _table(res: dict, split: str) -> str:
    rules = res["planners"]["rules"][split]["metrics"]
    noop = res["planners"]["noop"][split]["metrics"]
    llm = res["planners"].get("llm", {}).get(split, {}).get("metrics")
    head = "| Mess type | Datasets | Cell accuracy, rules | Row recall, rules | Duplicate F1, rules | Cell accuracy, no plan |"  # fmt: skip
    if llm:
        head += " Cell accuracy, LLM | Row recall, LLM |"
    lines = [head, "|" + "|".join([" --- "] * (head.count("|") - 1)) + "|"]
    for m in ["all"] + MESSES:
        r, n = rules[m], noop[m]
        name = "all cells" if m == "all" else LABEL[m]
        row = f"| {name} | {r['rows']['datasets']} | {pct(r['cells'])} | {pct(r['rows'])} | {pct(r.get('dup_f1')) if 'dup_f1' in r else ''} | {pct(n['cells'])} |"  # fmt: skip
        if llm:
            row += f" {pct(llm[m]['cells'])} | {pct(llm[m]['rows'])} |"
        lines.append(row)
    return "\n".join(lines)


def blocks(root: Path) -> dict[str, str]:
    res = json.loads((root / FINAL).read_text())
    meta = res["meta"]
    out = {}
    held = res["planners"]["rules"]["heldout"]
    out["results"] = "\n".join(
        [
            f"Held out sets ({meta['datasets']['heldout']} datasets, generator seeds {meta['generator_seeds'].split('heldout ')[1].replace('-', ' to ')}, new mixes of four to six messes). Run on {meta['date']}. Bootstrap: {meta['bootstrap']['resamples']} resamples over datasets, seed {meta['bootstrap']['seed']}. The rule baseline is deterministic. LLM model: {meta['model'] or 'none recorded (see Limits)'}.",  # fmt: skip
            "",
            _table(res, "heldout"),
            "",
            f"The verifier passed every check on {held['verifier_pass']} of {meta['datasets']['heldout']} held out outputs. Most failures are the row count check, which flags outputs that lost more than a fifth of their rows.",  # fmt: skip
        ]
    )
    if (root / SECOND).exists():
        sec = json.loads((root / SECOND).read_text())
        a = sec["planners"]["rules"]["heldout"]["metrics"]["all"]
        out["results"] += (
            f"\n\nSecond held out run with new seeds ({sec['meta']['generator_seeds'].split('heldout ')[1].replace('-', ' to ')}), because the first looked very good: "  # fmt: skip
            f"cell accuracy {pct(a['cells'])}, row recall {pct(a['rows'])}, duplicate F1 {pct(a['dup_f1'])}."
        )
    out["dev"] = "\n".join(
        [
            f"Development sets ({meta['datasets']['dev']} datasets, seeds 0 to 39, three messes each). The rules were tuned on these, so expect them to look better than the held out sets.",  # fmt: skip
            "",
            _table(res, "dev"),
        ]
    )
    tokens = round(held["prompt_chars_mean"] / 4)
    out["cost"] = "\n".join(
        [
            "| Planner | Money | Time per dataset | Operations per plan | Model calls |",
            "| --- | --- | --- | --- | --- |",
            f"| rule baseline | 0 dollars | {held['ms_mean']:.0f} ms (profile, plan, run, verify) | {held['ops_mean']:.1f} | 0 |",  # fmt: skip
            f"| LLM planner | 0 dollars on a free tier | not measured | not measured | 1 per dataset, about {tokens} prompt tokens |",  # fmt: skip
            "",
            f"Times come from {meta['cpu']}, Python {meta['python']}, {meta['date']}. Token counts are characters divided by four, an estimate.",  # fmt: skip
        ]
    )
    return out


def fill(text: str, values: dict[str, str]) -> str:
    for name, body in values.items():
        text = re.sub(
            rf"<!-- gen:{name} -->.*?<!-- /gen:{name} -->",
            lambda _m, n=name, b=body: f"<!-- gen:{n} -->\n{b}\n<!-- /gen:{n} -->",
            text,
            flags=re.S,
        )
    return text


def _demo_run(work: Path):
    src = write_dataset(work, "demo", DEMO["kind"], DEMO["seed"], DEMO["messes"], n=DEMO["n"], rate=DEMO["rate"])  # fmt: skip
    plan = rule_plan(profile(load(src)), SCHEMAS[DEMO["kind"]])
    result = run(src, plan, work / "out")
    return (
        src,
        plan,
        result,
        read_log(work / "out" / "changes.csv"),
        load(work / "out" / "clean.csv"),
    )


def demo(work: Path) -> str:
    src, plan, result, log, clean = _demo_run(work)
    raw = load(src)
    lines = ["BEFORE (messy input, first 6 rows)"]
    lines += [" | ".join(raw.header)] + [" | ".join(r["v"].values()) for r in raw.rows[:6]]
    lines += ["", "PLAN"] + [f"{i}. {s['op']}: {s['why']}" for i, s in enumerate(plan["steps"], 1)]
    lines += (
        ["", "RUN"]
        + [
            f"step {s['step']} {s['op']}: changed {s['changed']}, failed {s['failed']}, dropped {s['dropped']}"  # fmt: skip
            for s in result["steps"]
        ]
    )
    lines += ["", "AFTER (clean output, first 6 rows)"]
    lines += [" | ".join(clean.header)] + [" | ".join(r["v"].values()) for r in clean.rows[:6]]
    cells = sum(e["kind"] == "cell" for e in log)
    lines += ["", f"{result['rows_in']} rows in, {result['rows_out']} out, {cells} cell changes logged in changes.csv"]  # fmt: skip
    return "\n".join(lines)


def demo_html(work: Path, res: dict) -> str:
    src, plan, result, log, clean = _demo_run(work)
    raw = load(src)
    changed = {(int(e["row"]), e["column"]) for e in log if e["kind"] == "cell"}
    dropped = {int(e["row"]): e["old"] for e in log if e["kind"] == "drop_row"}

    def table(header, rows, mark):
        h = "".join(f"<th>{html.escape(c)}</th>" for c in header)
        body = []
        for r in rows:
            tds = "".join(
                f'<td class="{"changed" if mark and (r["src"], c) in changed else ""}">{html.escape(r["v"][c])}</td>'  # fmt: skip
                for c in header
            )
            cls = ' class="dropped"' if not mark and r["src"] in dropped else ""
            body.append(f"<tr{cls}><td>{r['src']}</td>{tds}</tr>")
        return f"<table><tr><th>row</th>{h}</tr>{''.join(body)}</table>"

    a = res["planners"]["rules"]["heldout"]["metrics"]["all"]
    steps = "".join(
        f"<li><code>{html.escape(json.dumps({k: v for k, v in s.items() if k != 'why'}, ensure_ascii=False))}</code> {html.escape(s['why'])}</li>"  # fmt: skip
        for s in plan["steps"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>csvmend demo</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:system-ui,sans-serif;margin:24px;color:#1b1f24;background:#fff}}
table{{border-collapse:collapse;font-size:13px;margin:8px 0 20px}}
td,th{{border:1px solid #ccd;padding:3px 6px;white-space:pre}}
th{{background:#eef}} td.changed{{background:#ffe58a}} tr.dropped td{{background:#f6c6c6;text-decoration:line-through}}
code{{font-size:12px}}
</style></head><body>
<h1 id="top">csvmend demo</h1>
<p>A generated customer table with {len(DEMO["messes"])} kinds of mess. The rule baseline read a profile and wrote the plan below. Plain code ran it on a copy. Yellow cells changed. Red rows were dropped, and the reason is in the change log.</p>
<p>Held out benchmark for the rule baseline: cell accuracy {pct(a["cells"])}, row recall {pct(a["rows"])}, duplicate F1 {pct(a["dup_f1"])}. Source: results/bench.json, run on {res["meta"]["date"]}.</p>
<h2 id="before">Before</h2>{table(raw.header, raw.rows, False)}
<h2 id="plan">Plan</h2><ol>{steps}</ol>
<h2 id="after">After</h2>{table(clean.header, clean.rows, True)}
<p>{result["rows_in"]} rows in, {result["rows_out"]} rows out, {sum(e["kind"] == "cell" for e in log)} cell changes in the log.</p>
</body></html>
"""


def write(root: Path, check: bool = False, work: Path | None = None) -> list[str]:
    """Regenerate the README blocks and docs/index.html. With check, report stale files."""
    import tempfile

    stale = []
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    new = fill(text, blocks(root))
    res = json.loads((root / FINAL).read_text())
    with tempfile.TemporaryDirectory() as tmp:
        page = demo_html(Path(work or tmp), res)
    targets = [(readme, text, new), (root / "docs" / "index.html", None, page)]
    for path, old, body in targets:
        old = path.read_text(encoding="utf-8") if old is None and path.exists() else old
        if old != body:
            stale.append(str(path.relative_to(root)))
            if not check:
                path.write_text(body, encoding="utf-8")
    return stale
