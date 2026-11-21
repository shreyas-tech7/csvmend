"""The plan language. A plan is JSON data with a list of steps. It is never code.

There are exactly 12 operations. Each one checks its own arguments here, before anything
runs. `validate_plan` also follows the header through every step, so a step that names a
column that will not exist fails before the executor touches a row.
"""

from __future__ import annotations

from datetime import datetime

UNITS = {"kg": 1.0, "g": 0.001, "lb": 0.45359237, "oz": 0.028349523125}


class PlanError(ValueError):
    pass


def _str(v):
    return None if isinstance(v, str) and v != "" else "must be a non-empty string"


def _bool(v):
    return None if isinstance(v, bool) else "must be true or false"


def _strlist(min_len=1):
    def check(v):
        if not isinstance(v, list) or len(v) < min_len or not all(isinstance(x, str) for x in v):
            return f"must be a list of at least {min_len} strings"
        if len(set(v)) != len(v):
            return "must not repeat a name"
        return None

    return check


def _columns(v):
    return None if v == "*" else _strlist()(v)


def _formats(v):
    err = _strlist()(v)
    if err:
        return err
    for f in v:
        if "%" not in f:
            return f"format {f!r} has no % code"
        try:
            datetime.strptime(datetime(2024, 1, 2).strftime(f), f)
        except ValueError:
            return f"format {f!r} is not a valid date format"
    return None


def _decimals(v):
    ok = isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 6
    return None if ok else "must be an integer from 0 to 6"


def _threshold(v):
    ok = isinstance(v, int | float) and not isinstance(v, bool) and 0.5 <= v <= 1.0
    return None if ok else "must be a number from 0.5 to 1.0"


def _mapping(v):
    if not isinstance(v, dict) or not v:
        return "must be a non-empty object"
    if not all(isinstance(k, str) and isinstance(x, str) for k, x in v.items()):
        return "keys and values must be strings"
    return None


def _rename_map(v):
    err = _mapping(v)
    if err:
        return err
    if any(x == "" for x in v.values()) or len(set(v.values())) != len(v):
        return "new names must be non-empty and different"
    if any(x in v and x != k for k, x in v.items()):
        return "a new name may not also be renamed in the same step (swap or chain)"
    return None


def _unit(v):
    return None if v in UNITS else f"must be one of {sorted(UNITS)}"


def _type(v):
    return None if v in ("int", "float", "str") else "must be int, float or str"


def _any_str(v):
    return None if isinstance(v, str) else "must be a string"


def _where(v):
    if v == {"ragged": True}:
        return None
    if isinstance(v, dict) and set(v) == {"column", "equals"}:
        return _str(v["column"]) or _any_str(v["equals"])
    if isinstance(v, dict) and set(v) == {"column", "empty"} and v["empty"] is True:
        return _str(v["column"])
    return 'must be {"ragged": true}, {"column", "equals"} or {"column", "empty": true}'


def _format_one(v):
    return _formats([v]) if isinstance(v, str) else "must be a string"


def _tokens(v):
    ok = isinstance(v, list) and all(isinstance(x, str) for x in v)
    return None if ok else "must be a list of strings"


NULLS = ["", "N/A", "NA", "null", "None", "NaN", "-", "?"]


def _maxsplit(v):
    ok = isinstance(v, int) and not isinstance(v, bool) and v >= 1
    return None if ok else "must be an integer of 1 or more"


# op name -> {arg: (check, required, default)}
OPS = {
    "parse_dates": {
        "column": (_str, True, None),
        "formats": (_formats, True, None),
        "output": (_format_one, False, "%Y-%m-%d"),
    },
    "normalize_currency": {"column": (_str, True, None), "decimals": (_decimals, False, 2)},
    "map_values": {
        "column": (_str, True, None),
        "mapping": (_mapping, True, None),
        "case_insensitive": (_bool, False, True),
    },
    "fuzzy_dedupe": {
        "columns": (_strlist(), True, None),
        "threshold": (_threshold, False, 0.9),
        "block_on": (_str, False, None),
    },
    "split_column": {
        "column": (_str, True, None),
        "into": (_strlist(2), True, None),
        "sep": (_any_str, True, None),
        "maxsplit": (_maxsplit, False, None),
    },
    "merge_columns": {
        "columns": (_strlist(2), True, None),
        "into": (_str, True, None),
        "sep": (_any_str, True, None),
    },
    "convert_units": {
        "column": (_str, True, None),
        "to": (_unit, True, None),
        "assume": (_unit, False, None),
        "decimals": (_decimals, False, 2),
    },
    "trim": {"columns": (_columns, False, "*"), "unicode": (_bool, False, False)},
    "fill_missing": {
        "columns": (_columns, True, None),
        "tokens": (_tokens, False, NULLS),
        "value": (_any_str, False, ""),
    },
    "drop_rows": {"where": (_where, True, None)},
    "cast": {
        "column": (_str, True, None),
        "type": (_type, True, None),
        "decimals": (_decimals, False, 2),
    },
    "rename": {"mapping": (_rename_map, True, None)},
}
assert len(OPS) == 12, "the plan language is capped at 12 operations"


def check_step(step) -> tuple[dict, list[str]]:
    """Check one step's arguments. Return (step with defaults filled, errors)."""
    if not isinstance(step, dict):
        return {}, ["step must be an object"]
    op = step.get("op")
    if not isinstance(op, str) or op not in OPS:
        return {}, [f"unknown op {op!r}"]
    spec = OPS[op]
    errors = []
    for k in step:
        if k not in spec and k not in ("op", "why"):
            errors.append(f"{op}: unknown argument {k!r}")
    if "why" in step and not isinstance(step["why"], str):
        errors.append(f"{op}: why must be a string")
    full = {"op": op}
    for arg, (check, required, default) in spec.items():
        if arg not in step:
            if required:
                errors.append(f"{op}: missing argument {arg!r}")
            full[arg] = default
            continue
        err = check(step[arg])
        if err:
            errors.append(f"{op}: {arg} {err}")
        full[arg] = step[arg]
    if op == "merge_columns" and not errors and step["into"] in step["columns"]:
        errors.append(f"{op}: into must be a new column name")
    if op == "split_column" and not errors and step["column"] in step["into"]:
        errors.append(f"{op}: into may not reuse the column being split")
    return full, errors


def _uses(step: dict) -> list[str]:
    op = step["op"]
    if op == "rename":
        return list(step["mapping"])
    if op in ("merge_columns", "fuzzy_dedupe"):
        cols = list(step["columns"])
        return cols + ([step["block_on"]] if step.get("block_on") else [])
    if op in ("trim", "fill_missing"):
        return [] if step["columns"] == "*" else list(step["columns"])
    if op == "drop_rows":
        return [step["where"]["column"]] if "column" in step["where"] else []
    return [step["column"]]


def apply_header(step: dict, header: list[str]) -> list[str]:
    """Return the header after a step. Only rename, split and merge change it."""
    h = list(header)
    op = step["op"]
    if op == "rename":
        return [step["mapping"].get(c, c) for c in h]
    if op == "split_column":
        i = h.index(step["column"])
        return h[:i] + list(step["into"]) + h[i + 1 :]
    if op == "merge_columns":
        i = min(h.index(c) for c in step["columns"])
        rest = [c for c in h if c not in step["columns"]]
        rest.insert(i, step["into"])
        return rest
    return h


def validate_plan(plan, header: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Check a whole plan. With a header, also check that every named column exists then."""
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        return [], ['plan must be an object with a "steps" list']
    steps, errors = [], []
    h = list(header) if header is not None else None
    for i, raw in enumerate(plan["steps"], 1):
        step, errs = check_step(raw)
        errors += [f"step {i}: {e}" for e in errs]
        if errs:
            continue
        if h is not None:
            missing = [c for c in _uses(step) if c not in h]
            if missing:
                errors.append(f"step {i}: {step['op']}: no column named {missing}")
                continue
            new = apply_header(step, h)
            if len(set(new)) != len(new):
                errors.append(f"step {i}: {step['op']}: makes a duplicate column name")
                continue
            h = new
        steps.append(step)
    return steps, errors
