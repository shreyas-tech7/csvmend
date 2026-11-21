"""Every operation: one valid step passes, each broken argument fails, and the op does its job."""

import pytest

from csvmend.executor import Table, execute
from csvmend.plan import OPS, check_step, validate_plan

VALID = {
    "parse_dates": {"op": "parse_dates", "column": "d", "formats": ["%m/%d/%Y"]},
    "normalize_currency": {"op": "normalize_currency", "column": "m"},
    "map_values": {"op": "map_values", "column": "c", "mapping": {"furn.": "Furniture"}},
    "fuzzy_dedupe": {"op": "fuzzy_dedupe", "columns": ["name"], "threshold": 0.9},
    "split_column": {"op": "split_column", "column": "full", "into": ["a", "b"], "sep": " "},
    "merge_columns": {"op": "merge_columns", "columns": ["a", "b"], "into": "ab", "sep": "-"},
    "convert_units": {"op": "convert_units", "column": "w", "to": "kg"},
    "trim": {"op": "trim", "columns": "*", "unicode": True},
    "fill_missing": {"op": "fill_missing", "columns": ["m"], "tokens": ["N/A"], "value": ""},
    "drop_rows": {"op": "drop_rows", "where": {"ragged": True}},
    "cast": {"op": "cast", "column": "q", "type": "int"},
    "rename": {"op": "rename", "mapping": {"Q": "q"}},
}
INVALID = [
    ("parse_dates", {"formats": "%Y"}),
    ("parse_dates", {"formats": ["no code"]}),
    ("parse_dates", {"column": ""}),
    ("normalize_currency", {"decimals": 9}),
    ("normalize_currency", {"decimals": True}),
    ("map_values", {"mapping": {}}),
    ("map_values", {"mapping": {"a": 1}}),
    ("map_values", {"case_insensitive": "yes"}),
    ("fuzzy_dedupe", {"threshold": 0.2}),
    ("fuzzy_dedupe", {"columns": []}),
    ("fuzzy_dedupe", {"columns": ["a", "a"]}),
    ("split_column", {"into": ["only"]}),
    ("split_column", {"sep": 5}),
    ("split_column", {"maxsplit": 0}),
    ("merge_columns", {"columns": ["a"]}),
    ("merge_columns", {"into": "a"}),
    ("convert_units", {"to": "stone"}),
    ("convert_units", {"assume": "ton"}),
    ("trim", {"columns": "a"}),
    ("trim", {"unicode": 1}),
    ("fill_missing", {"tokens": "N/A"}),
    ("fill_missing", {"value": None}),
    ("drop_rows", {"where": {"ragged": False}}),
    ("drop_rows", {"where": {"column": "a"}}),
    ("cast", {"type": "decimal"}),
    ("cast", {"decimals": -1}),
    ("rename", {"mapping": {"a": ""}}),
    ("rename", {"mapping": {"a": "x", "b": "x"}}),
    ("rename", {"mapping": {"a": "b", "b": "a"}}),
    ("rename", {"mapping": {"a": "b", "b": "c"}}),
    ("parse_dates", {"formats": ["%Q"]}),
]


def test_language_is_capped_at_twelve_ops():
    assert len(OPS) == 12 and set(VALID) == set(OPS)


@pytest.mark.parametrize("op", sorted(VALID))
def test_valid_step_passes(op):
    _, errors = check_step(VALID[op])
    assert errors == []


@pytest.mark.parametrize("op,change", INVALID, ids=[f"{o}-{sorted(c)[0]}" for o, c in INVALID])
def test_invalid_argument_fails(op, change):
    """Broken case: a step with one bad argument would reach the executor."""
    _, errors = check_step(VALID[op] | change)
    assert errors, f"{op} accepted {change}"


@pytest.mark.parametrize("op", sorted(VALID))
def test_missing_required_or_unknown_argument_fails(op):
    _, errors = check_step(VALID[op] | {"surprise": 1})
    assert any("unknown argument" in e for e in errors)
    required = [a for a, (_, req, _) in OPS[op].items() if req]
    if required:
        broken = {k: v for k, v in VALID[op].items() if k != required[0]}
        assert any("missing argument" in e for e in check_step(broken)[1])


def test_unknown_op_and_bad_plan_shape():
    assert validate_plan({"steps": [{"op": "eval", "code": "x"}]})[1]
    assert validate_plan(["not", "a", "plan"])[1]
    assert validate_plan({"steps": "trim"})[1]


def test_header_is_followed_through_the_plan():
    plan = {
        "steps": [
            {"op": "rename", "mapping": {"Full Name": "full"}},
            {"op": "split_column", "column": "full", "into": ["first", "last"], "sep": " "},
            {"op": "trim", "columns": ["first"]},
        ]
    }
    assert validate_plan(plan, ["Full Name", "x"])[1] == []
    bad = {"steps": [{"op": "trim", "columns": ["full"]}]}
    assert "no column named" in validate_plan(bad, ["Full Name"])[1][0]
    dup = {"steps": [{"op": "rename", "mapping": {"a": "b"}}]}
    assert "duplicate column" in validate_plan(dup, ["a", "b"])[1][0]


def _run(header, rows, step):
    t = Table(list(header), [{"src": i, "ragged": False, "v": dict(zip(header, r, strict=True))} for i, r in enumerate(rows)])  # fmt: skip
    steps, errors = validate_plan({"steps": [step]}, t.header)
    assert errors == []
    execute(t, steps)
    return t, [[r["v"][c] for c in t.header] for r in t.rows]


def test_ops_do_their_job():
    _, r = _run(["d"], [["03/14/2025"], ["14.03.2025"], ["bad"]], {"op": "parse_dates", "column": "d", "formats": ["%m/%d/%Y", "%d.%m.%Y"]})  # fmt: skip
    assert r == [["2025-03-14"], ["2025-03-14"], ["bad"]]
    _, r = _run(
        ["m"], [["$1,234.50"], ["1.234,50"], ["USD 7"], ["12,5"]], VALID["normalize_currency"]
    )
    assert r == [["1234.50"], ["1234.50"], ["7.00"], ["12.50"]]
    _, r = _run(["c"], [["FURN."], ["Desk"]], VALID["map_values"])
    assert r == [["Furniture"], ["Desk"]]
    t, r = _run(["name"], [["Ana Lopez"], ["ana lopez"], ["Ben Kim"]], VALID["fuzzy_dedupe"])
    assert r == [["Ana Lopez"], ["Ben Kim"]] and t.log[-1]["old"] == "dup_of:0"
    t, r = _run(["full", "z"], [["Ana Maria Lopez", "1"]], VALID["split_column"])
    assert t.header == ["a", "b", "z"] and r == [["Ana", "Maria Lopez", "1"]]
    t, r = _run(["a", "b"], [["512", "555-0134"], ["", "9"]], VALID["merge_columns"])
    assert t.header == ["ab"] and r == [["512-555-0134"], ["9"]]
    _, r = _run(["w"], [["2.2046 lb"], ["1500 g"], ["3"], ["heavy"]], VALID["convert_units"])
    assert r == [["1.00"], ["1.50"], ["3.00"], ["heavy"]]
    _, r = _run(["s"], [["  Ana  "], ["JosÃ©"]], VALID["trim"])
    assert r == [["Ana"], ["José"]]
    _, r = _run(["m"], [["N/A"], ["n/a "], ["5"]], VALID["fill_missing"])
    assert r == [[""], [""], ["5"]]
    _, r = _run(["q"], [["3.0"], ["2.5"], ["x"]], VALID["cast"])
    assert r == [["3"], ["2.5"], ["x"]]
    t, _ = _run(["Q"], [["1"]], VALID["rename"])
    assert t.header == ["q"]
    _, r = _run(["a"], [[""], ["x"]], {"op": "drop_rows", "where": {"column": "a", "empty": True}})
    assert r == [["x"]]


def test_drop_rows_ragged():
    t = Table(["a", "b"], [{"src": 0, "ragged": True, "v": {"a": "1", "b": ""}}, {"src": 1, "ragged": False, "v": {"a": "2", "b": "3"}}])  # fmt: skip
    execute(t, validate_plan({"steps": [VALID["drop_rows"]]}, t.header)[0])
    assert [r["src"] for r in t.rows] == [1]


@pytest.mark.parametrize("op", [["trim"], {}, 3])
def test_op_that_is_not_a_string_is_a_plan_error(op):
    _, errors = check_step({"op": op})
    assert errors


def test_split_into_its_own_name_fails():
    _, errors = check_step(
        {"op": "split_column", "column": "full", "sep": " ", "into": ["full", "last"]}
    )
    assert errors
