"""The input never changes, every change is logged, and replaying the log rebuilds the output."""

import hashlib
import json

import pytest

from csvmend.executor import load, read_log, replay, run
from csvmend.messes import MESSES, write_dataset
from csvmend.plan import PlanError
from csvmend.planners import rule_plan
from csvmend.profiler import profile
from csvmend.tables import SCHEMAS

CASES = [("customers", 1), ("orders", 2), ("inventory", 3), ("customers", 4)]


def _dataset(tmp_path, kind, seed, messes=MESSES):
    return write_dataset(tmp_path / "data", f"{kind}{seed}", kind, seed, messes, n=50)


def _rule_run(tmp_path, kind, seed):
    src = _dataset(tmp_path, kind, seed)
    plan = rule_plan(profile(load(src)), SCHEMAS[kind])
    return src, run(src, plan, tmp_path / "out"), tmp_path / "out"


@pytest.mark.parametrize("kind,seed", CASES)
def test_input_file_is_never_changed(tmp_path, kind, seed):
    """Broken case: an executor that cleans in place changes the input hash."""
    src = _dataset(tmp_path, kind, seed)
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    plan = rule_plan(profile(load(src)), SCHEMAS[kind])
    run(src, plan, tmp_path / "out")
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before


def test_refuses_to_write_over_the_input(tmp_path):
    src = tmp_path / "clean.csv"
    src.write_text("a\n1\n")
    with pytest.raises(PlanError):
        run(src, {"steps": []}, tmp_path)
    assert src.read_text() == "a\n1\n"


def test_invalid_plan_runs_nothing(tmp_path):
    src = _dataset(tmp_path, "orders", 5)
    with pytest.raises(PlanError):
        run(src, {"steps": [{"op": "trim", "columns": ["nope"]}]}, tmp_path / "out")
    assert not (tmp_path / "out" / "clean.csv").exists()


@pytest.mark.parametrize("kind,seed", CASES)
def test_replaying_the_log_rebuilds_the_output(tmp_path, kind, seed):
    """Broken case: a change made outside the log would make replay differ from clean.csv."""
    src, _, out = _rule_run(tmp_path, kind, seed)
    log = read_log(out / "changes.csv")
    assert replay(src, log) == (out / "clean.csv").read_text(encoding="utf-8")


def test_replay_catches_a_tampered_log(tmp_path):
    src, _, out = _rule_run(tmp_path, "customers", 6)
    log = read_log(out / "changes.csv")
    cell = next(e for e in log if e["kind"] == "cell")
    cell["old"] = cell["old"] + "x"
    with pytest.raises(PlanError):
        replay(src, log)


@pytest.mark.parametrize("kind,seed", CASES)
def test_every_changed_cell_is_in_the_log(tmp_path, kind, seed):
    """Compare input and output cell by cell, through renames, and look up each change."""
    src, result, out = _rule_run(tmp_path, kind, seed)
    log = read_log(out / "changes.csv")
    t_in, t_out = load(src), load(out / "clean.csv")
    names = {h: h for h in t_in.header}
    for e in log:
        if e["kind"] == "rename":
            names = {k: (e["new"] if v == e["old"] else v) for k, v in names.items()}
    logged = {(int(e["row"]), e["column"]) for e in log if e["kind"] == "cell"}
    by_src = {r["src"]: r for r in t_in.rows}
    checked = 0
    for src_row, out_row in zip(result["kept_rows"], t_out.rows, strict=True):
        for old_name, new_name in names.items():
            if new_name not in t_out.header:
                continue
            if by_src[src_row]["v"][old_name] != out_row["v"][new_name]:
                assert (src_row, new_name) in logged or (src_row, old_name) in logged
                checked += 1
    assert checked > 0
    dropped = {int(e["row"]) for e in log if e["kind"] == "drop_row"}
    assert dropped == set(by_src) - set(result["kept_rows"])


def test_encoding_change_is_logged_first(tmp_path):
    src = tmp_path / "in.csv"
    src.write_bytes("name\nJos\xe9\n".encode("latin-1"))
    run(src, {"steps": []}, tmp_path / "out")
    log = read_log(tmp_path / "out" / "changes.csv")
    assert log[0]["kind"] == "encoding" and log[0]["old"] == "cp1252"
    assert (tmp_path / "out" / "clean.csv").read_text(encoding="utf-8") == "name\nJosé\n"


def test_outputs_are_written(tmp_path):
    src, result, out = _rule_run(tmp_path, "inventory", 7)
    assert {p.name for p in out.iterdir()} == {"clean.csv", "plan.json", "changes.csv", "run.json"}
    assert json.loads((out / "run.json").read_text())["rows_out"] == result["rows_out"]
