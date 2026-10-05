"""The JSON conventions every scoring stage shares: a value always carries its source; missing is never zero."""
from __future__ import annotations
import json


def val(value, source: str) -> dict:
    return {"value": value, "source": source}


def missing(source: str, why: str) -> dict:
    return {"missing": source, "why": why}


def is_missing(x) -> bool:
    return isinstance(x, dict) and "missing" in x


def dump(obj) -> str:
    """Byte-stable JSON: sorted keys, two-space indent, trailing newline (deterministic stages, spec §12)."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
