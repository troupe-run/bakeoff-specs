import json
from runner.scoring import values


def test_val_carries_value_and_source():
    assert values.val(3, "results/p/a/01/run.json") == {"value": 3, "source": "results/p/a/01/run.json"}


def test_missing_is_never_a_value():
    m = values.missing("results/p/a/01/run.json", "no such file")
    assert values.is_missing(m) and "value" not in m


def test_dump_is_sorted_and_stable():
    a = values.dump({"b": 1, "a": {"d": 2, "c": 3}})
    b = values.dump({"a": {"c": 3, "d": 2}, "b": 1})
    assert a == b and json.loads(a) == {"a": {"c": 3, "d": 2}, "b": 1} and a.endswith("\n")
