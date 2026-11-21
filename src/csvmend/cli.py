"""Command line: csvmend <command>. Run `csvmend -h` for the list."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .executor import load, read_log, replay, run
from .messes import MESSES, write_dataset
from .plan import validate_plan
from .planners import LLMPlanner, build_prompt, rule_plan
from .profiler import profile, sample_rows
from .tables import SCHEMAS
from .verifier import summary, verify

ROOT = Path(__file__).resolve().parents[2]


def _schema(arg: str) -> dict:
    return SCHEMAS[arg] if arg in SCHEMAS else json.loads(Path(arg).read_text())


def _llm(spec: str, record: bool) -> LLMPlanner:
    provider, model = spec.split(":", 1)
    return LLMPlanner(provider, model, ROOT / "fixtures" / "llm", "record" if record else "replay")


def cmd_generate(a):
    p = write_dataset(Path(a.out), a.name, a.kind, a.seed, a.messes, n=a.rows, rate=a.rate)
    print(f"wrote {p} with its .truth.json and .schema.json")


def cmd_profile(a):
    print(json.dumps(profile(load(Path(a.file))), indent=1, ensure_ascii=False))


def cmd_prompt(a):
    t = load(Path(a.file))
    print(build_prompt(profile(t), sample_rows(t), _schema(a.schema)))


def cmd_plan(a):
    t = load(Path(a.file))
    prof, schema = profile(t), _schema(a.schema)
    if a.llm:
        plan = _llm(a.llm, a.record).plan(Path(a.file).stem, prof, sample_rows(t), schema)
    else:
        plan = rule_plan(prof, schema)
    _, errors = validate_plan(plan, t.header)
    text = json.dumps(plan, indent=2, ensure_ascii=False)
    Path(a.out).write_text(text + "\n") if a.out else print(text)
    for e in errors:
        print("INVALID", e, file=sys.stderr)
    return 1 if errors else 0


def cmd_run(a):
    plan = json.loads(Path(a.plan).read_text())
    r = run(Path(a.file), plan, Path(a.out))
    for s in r["steps"]:
        print(f"step {s['step']:>2} {s['op']:<18} changed {s['changed']:>4}  failed {s['failed']:>3}  dropped {s['dropped']:>3}")  # fmt: skip
    print(f"{r['rows_in']} rows in, {r['rows_out']} rows out, {r['log_entries']} log entries")
    print(f"wrote {a.out}/clean.csv, plan.json, changes.csv, run.json")


def cmd_verify(a):
    t = load(Path(a.file))
    checks = verify(t, _schema(a.schema), a.rows_in or len(t.rows))
    print(summary(checks))
    return 0 if all(c["ok"] for c in checks) else 1


def cmd_replay(a):
    text = replay(Path(a.file), read_log(Path(a.log)))
    Path(a.out).write_text(text, encoding="utf-8") if a.out else print(text, end="")


def cmd_bench(a):
    from .bench import bench

    llm = _llm(a.llm, a.record) if a.llm else None
    r = bench(Path(a.work), Path(a.out), llm=llm, limit=a.limit, held_base=a.held_base)
    for name, p in r["planners"].items():
        for split in ("dev", "heldout"):
            if split in p:
                c = p[split]["metrics"]["all"]["cells"]
                print(f"{name:<6} {split:<8} cell accuracy {c['value']:.3f} [{c['lo']:.3f}, {c['hi']:.3f}]")  # fmt: skip
    print("wrote", a.out)


def cmd_readme(a):
    from .report import write

    stale = write(ROOT, check=a.check)
    for s in stale:
        print("out of date:", s)
    return 1 if stale else 0


def cmd_demo(a):
    from .report import demo

    print(demo(Path(a.work)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="csvmend", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write a messy CSV with ground truth")
    g.add_argument("--kind", choices=sorted(SCHEMAS), default="customers")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--messes", nargs="+", choices=MESSES, default=MESSES)
    g.add_argument("--rows", type=int, default=80)
    g.add_argument("--rate", type=float, default=0.3)
    g.add_argument("--name", default="messy")
    g.add_argument("--out", default="data")
    for name, help_ in [("profile", "summarize each column"), ("prompt", "print the LLM prompt")]:
        p = sub.add_parser(name, help=help_)
        p.add_argument("file")
        if name == "prompt":
            p.add_argument("--schema", required=True, help="a built-in kind or a schema JSON file")
    p = sub.add_parser("plan", help="write a plan with the rule baseline or an LLM")
    p.add_argument("file")
    p.add_argument("--schema", required=True, help="a built-in kind or a schema JSON file")
    p.add_argument("--llm", help="provider:model, for example groq:llama-3.3-70b-versatile")
    p.add_argument("--record", action="store_true", help="call the provider (needs a key)")
    p.add_argument("-o", "--out")
    r = sub.add_parser("run", help="run a plan on a copy of the file")
    r.add_argument("file")
    r.add_argument("--plan", required=True)
    r.add_argument("--out", required=True)
    v = sub.add_parser("verify", help="check a cleaned file against a schema")
    v.add_argument("file")
    v.add_argument("--schema", required=True)
    v.add_argument("--rows-in", type=int)
    rp = sub.add_parser("replay", help="apply a change log to the input")
    rp.add_argument("file")
    rp.add_argument("--log", required=True)
    rp.add_argument("-o", "--out")
    b = sub.add_parser("bench", help="run the benchmark")
    b.add_argument("--work", default=".cache/bench")
    b.add_argument("--out", default="results/bench.json")
    b.add_argument("--llm")
    b.add_argument("--record", action="store_true")
    b.add_argument("--limit", type=int)
    b.add_argument("--held-base", type=int, default=1000)
    rd = sub.add_parser("readme", help="write the README tables and docs/index.html")
    rd.add_argument("--check", action="store_true")
    d = sub.add_parser("demo", help="clean one small dataset and show before and after")
    d.add_argument("--work", default=".cache/demo")
    a = ap.parse_args(argv)
    return globals()[f"cmd_{a.cmd}"](a) or 0


if __name__ == "__main__":
    sys.exit(main())
