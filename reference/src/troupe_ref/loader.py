"""Resolves the theatre's config file and loads it into a `Config` (from the ported spike)."""
from __future__ import annotations
from pathlib import Path

from ruamel.yaml.error import YAMLError

from .config import Config, ConfigError


class LoadError(Exception):
    pass


def config_file(theatre: Path) -> Path:
    found = [p for p in (theatre / ".troupe/troupe.yml", theatre / ".troupe/troupe.yaml") if p.exists()]
    if len(found) != 1:
        raise LoadError(f"{theatre / '.troupe'}: expected exactly one of troupe.yml / troupe.yaml, found {len(found)}")
    return found[0]


def load(theatre: Path) -> Config:
    try:
        return Config(config_file(theatre))
    except LoadError:
        raise
    # ConfigError (and its subclass IncludeCycleError): missing/cyclic includes, multi-document YAML.
    # OSError: a missing include target file.
    # YAMLError: ruamel parse/scan/compose errors for invalid YAML.
    except (ConfigError, OSError, YAMLError) as e:
        raise LoadError(str(e)) from e
