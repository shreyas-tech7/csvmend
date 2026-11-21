"""Generator, profiler, LLM prompt, verifier, score and benchmark."""

import json
import re

import pytest

from csvmend.bench import interval, run_one, suite
from csvmend.executor import Table, load
from csvmend.messes import MESSES, make_dataset, write_dataset
from csvmend.planners import LLMPlanner, build_prompt, parse_plan, rule_plan
from csvmend.profiler import SAMPLE_ROWS, profile, sample_rows
from csvmend.score import score
from csvmend.tables import SCHEMAS, clean_table
from csvmend.verifier import verify


def test_generator_is_seeded():
    assert make_dataset("orders", 3, MESSES) == make_dataset("orders", 3, MESSES)
    assert make_dataset("orders", 3, MESSES) != make_dataset("orders", 4, MESSES)


@pytest.mark.parametrize("mess", MESSES)
def test_each_mess_leaves_a_mark(mess):
    for kind in SCHEMAS:
        header, rows, _, truth = make_dataset(kind, 11, [mess], n=60)
        clean_h, clean = clean_table(kind, 11, 60)
        if truth["touched"][mess] or truth["dup_pairs"]:
            break
    else:
        pytest.fail(f"{mess} changed nothing")
    if mess == "near_duplicates":
        assert len(rows) > len(clean) and len(truth["dup_pairs"]) == len(rows) - len(clean)
    if mess == "shifted_rows":
        assert any(len(r) != len(header) for r in rows)


def test_ground_truth_keeps_clean_values_and_blanks_lost_ones():
    _, _, _, truth = make_dataset("customers", 2, ["missing_values", "currency"], n=60)
    _, clean = clean_table("customers", 2, 60)
    lost = {(s, c) for s, c in truth["touched"]["missing_values"]}
    for i, row in enumerate(truth["rows"]):
        for c, v in row.items():
            assert v == ("" if (i, c) in lost else clean[i][c])


def test_profile_examples_come_only_from_the_sample(tmp_path):
    src = write_dataset(tmp_path, "c", "customers", 5, MESSES, n=120)
    t = load(src)
    p = profile(t, seed=5)
    assert len(p["sample_rows"]) == SAMPLE_ROWS
    ids = {r["v"]["customer_id"] for r in t.rows}
    sampled = {t.rows[i]["v"]["customer_id"] for i in p["sample_rows"]}
    text = json.dumps(p, ensure_ascii=False)
    assert {i for i in ids if i in text} <= sampled


def test_llm_prompt_holds_only_profile_and_20_rows(tmp_path):
    """Broken case: a prompt that pastes the whole file would carry ids from every row."""
    src = write_dataset(tmp_path, "c", "orders", 8, MESSES, n=140)
    t = load(src)
    prof, rows = profile(t, seed=8), sample_rows(t, seed=8)
    prompt = build_prompt(prof, rows, SCHEMAS["orders"])
    assert len(rows) == SAMPLE_ROWS
    sample_lines = prompt.split("SAMPLE ROWS")[1].strip().splitlines()[2:]
    assert len(sample_lines) == SAMPLE_ROWS
    ids = {r["v"]["order_id"] for r in t.rows}
    in_prompt = set(re.findall(r"O\d{5}", prompt)) & ids
    sampled = {t.rows[i]["v"]["order_id"] for i in prof["sample_rows"]}
    assert in_prompt <= sampled and len(in_prompt) <= SAMPLE_ROWS
    with pytest.raises(ValueError):
        build_prompt(prof, sample_rows(t) * 2, SCHEMAS["orders"])


def test_llm_planner_replays_a_fixture(tmp_path):
    """The fixture here is written by the test. It is not a model answer."""
    src = write_dataset(tmp_path, "inv", "inventory", 9, ["currency"], n=40)
    t = load(src)
    prof, rows = profile(t), sample_rows(t)
    prompt = build_prompt(prof, rows, SCHEMAS["inventory"])
    planner = LLMPlanner("groq", "test-model", tmp_path / "fx")
    planner.dir.mkdir(parents=True)
    import hashlib

    answer = 'Plan:\n{"version": 1, "steps": [{"op": "normalize_currency", "column": "unit_cost"}]}'
    rec = {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "answer": answer}
    (planner.dir / "inv.json").write_text(json.dumps(rec))
    assert (
        planner.plan("inv", prof, rows, SCHEMAS["inventory"])["steps"][0]["op"]
        == "normalize_currency"
    )
    rec["prompt_sha256"] = "0" * 64
    (planner.dir / "inv.json").write_text(json.dumps(rec))
    with pytest.raises(ValueError):
        planner.plan("inv", prof, rows, SCHEMAS["inventory"])


def test_parse_plan_needs_json():
    assert parse_plan('```json\n{"steps": []}\n```') == {"steps": []}
    with pytest.raises(ValueError):
        parse_plan("I would trim the columns.")


def _table(header, rows):
    return Table(header, [{"src": i, "ragged": False, "v": dict(zip(header, r, strict=True))} for i, r in enumerate(rows)])  # fmt: skip


def test_verifier_catches_each_broken_case():
    header, clean = clean_table("orders", 1, 30)
    good = _table(header, [[r[c] for c in header] for r in clean])
    assert all(c["ok"] for c in verify(good, SCHEMAS["orders"], 30))
    rows = [[r[c] for c in header] for r in clean]
    rows[0][header.index("order_date")] = "03/04/2024"
    rows[1][header.index("quantity")] = "999"
    rows[2][header.index("category")] = "Furn."
    rows[3][header.index("order_id")] = rows[4][header.index("order_id")]
    failed = {
        c["check"] for c in verify(_table(header, rows), SCHEMAS["orders"], 30) if not c["ok"]
    }
    assert failed == {"type:order_date", "range:quantity", "allowed:category", "unique:order_id"}
    short = _table(header[:-1], [r[:-1] for r in rows[:10]])
    failed = {c["check"] for c in verify(short, SCHEMAS["orders"], 30) if not c["ok"]}
    assert {"columns", "row_count"} <= failed


def test_score_rewards_the_truth_and_punishes_the_mess(tmp_path):
    header, rows, _, truth = make_dataset("customers", 3, ["near_duplicates", "currency"], n=50)
    kept = [i for i in range(len(rows)) if not any(i == p[1] for p in truth["dup_pairs"])]
    perfect = [[truth["rows"][truth["row_uid"][i]][c] for c in truth["header"]] for i in kept]
    log = [{"kind": "drop_row", "row": str(c), "old": f"dup_of:{o}"} for o, c in truth["dup_pairs"]]
    s = score(truth["header"], perfect, kept, log, truth)
    assert s["all"]["cells"][0] == s["all"]["cells"][1] and s["all"]["rows"] == [50, 50]
    assert s["dups"]["fp"] == 0 and s["dups"]["fn"] == 0
    messy = score(header, rows, list(range(len(rows))), [], truth)
    assert messy["currency"]["cells"][0] < messy["currency"]["cells"][1]
    assert messy["dups"]["fn"] == len(truth["dup_pairs"]) and messy["all"]["extra_rows"] > 0


def test_suite_has_dev_and_held_out_sets_with_new_mixes():
    s = suite()
    dev = [d for d in s if d["split"] == "dev"]
    held = [d for d in s if d["split"] == "heldout"]
    assert len(dev) == 40 and len(held) >= 20
    assert not {frozenset(d["messes"]) for d in dev} & {frozenset(d["messes"]) for d in held}
    assert not {d["seed"] for d in dev} & {d["seed"] for d in held}
    for m in MESSES:
        assert any(m in d["messes"] for d in held), m


def test_interval_brackets_the_value():
    pairs = [[8, 10], [9, 10], [10, 10], [7, 10]]
    r = interval(pairs)
    assert r["lo"] <= r["value"] <= r["hi"] and r["value"] == 34 / 40


def test_rule_baseline_cleans_one_dataset_end_to_end(tmp_path):
    ds = {"name": "x", "split": "dev", "kind": "customers", "seed": 21, "n": 60, "rate": 0.3}
    ds["messes"] = ["mixed_dates", "category_typos", "whitespace_encoding"]
    planner = {"name": "rules", "fn": lambda n, p, r, s: rule_plan(p, s)}
    rec = run_one(ds, planner, tmp_path)
    assert rec["plan_errors"] == [] and rec["ops"] >= 3
    cells = rec["score"]["all"]["cells"]
    assert cells[0] / cells[1] > 0.95


def test_bench_counts_an_unreadable_answer_as_a_rejected_plan(tmp_path):
    """Broken case: a model answers with prose and no JSON. The run goes on with an empty plan."""

    def bad(name, prof, rows, schema):
        return parse_plan("Sorry, I cannot help with that.")

    rec = run_one(suite()[0], {"name": "llm", "fn": bad}, tmp_path)
    assert rec["plan_errors"] and rec["ops"] == 0


def test_cli_reports_a_bad_plan_without_a_traceback(tmp_path, capsys):
    from csvmend.cli import main

    src = tmp_path / "in.csv"
    src.write_text("a\n1\n")
    plan = tmp_path / "p.json"
    plan.write_text("{not json")
    assert main(["run", str(src), "--plan", str(plan), "--out", str(tmp_path / "o")]) == 2
    assert "error:" in capsys.readouterr().err
