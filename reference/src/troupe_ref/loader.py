"""Resolves the theatre's config file and loads it into a `Config` (from the ported spike)."""
from __future__ import annotations
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ruamel.yaml.error import YAMLError

from .config import Config, ConfigError
from .step import STEP

SCHEMA_FILE = ".troupe/troupe.schema.json"


class LoadError(Exception):
    pass


def config_file(theatre: Path) -> Path:
    found = [p for p in (theatre / ".troupe/troupe.yml", theatre / ".troupe/troupe.yaml") if p.exists()]
    if len(found) != 1:
        raise LoadError(f"{theatre / '.troupe'}: expected exactly one of troupe.yml / troupe.yaml, found {len(found)}")
    return found[0]


def load_schema(theatre: Path) -> dict | None:
    """`.troupe/troupe.schema.json` (JSON Schema 2020-12), from step 7; None when absent."""
    f = theatre / SCHEMA_FILE
    if STEP < 7 or not f.exists():
        return None
    try:
        schema = json.loads(f.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (ValueError, SchemaError) as e:
        raise LoadError(f"{f}: not a valid JSON Schema: {e}") from e
    return schema


def load(theatre: Path) -> Config:
    try:
        # the merged configuration is validated against the schema as it loads (SchemaViolation)
        return Config(config_file(theatre), schema=load_schema(theatre))
    except LoadError:
        raise
    # ConfigError (and its subclass IncludeCycleError): missing/cyclic includes, multi-document YAML.
    # OSError: a missing include target file.
    # YAMLError: ruamel parse/scan/compose errors for invalid YAML.
    except (ConfigError, OSError, YAMLError) as e:
        raise LoadError(str(e)) from e
