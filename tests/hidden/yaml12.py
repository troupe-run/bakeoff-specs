"""A YAML 1.2 (core schema) loader for hidden tests that parse a candidate's YAML output.

The contract (scenario/contract.md) is written against YAML 1.2. PyYAML implements YAML 1.1, whose
implicit-typing resolver turns bare `yes`/`no`/`on`/`off` into booleans — a correct YAML 1.2
candidate that prints `flag: yes` (a string, per 1.2's core schema) would be misjudged as wrong by
`yaml.safe_load`. Use `load()` here instead of `yaml.safe_load` for any hidden test that parses an
arm's output.
"""
from __future__ import annotations
from ruamel.yaml import YAML

def load(text: str):
    return YAML(typ="safe").load(text)
