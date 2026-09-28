"""YAML rendering for `show`: plain (`render_yaml`) and source-annotated (`render_with_sources`)."""
from __future__ import annotations
import io
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

def _literalise(v):
    if isinstance(v, dict):
        return {k: _literalise(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_literalise(x) for x in v]
    if isinstance(v, str) and "\n" in v:
        return LiteralScalarString(v)
    return v

# Never wrap a scalar onto a continuation line. `render_yaml` backs `render_with_sources`'s
# `scalar_text` (below), which takes only the first line of its output to attach a trailing
# `# from <file>` comment — a wrapped plain scalar would silently lose everything past the first
# line. A block collection's structure is unaffected by `width`, so this is safe for whole-value
# `show` output too.
NO_WRAP = 1_000_000

def render_yaml(value) -> str:
    y = YAML()
    y.default_flow_style = False
    y.indent(mapping=2, sequence=4, offset=2)
    y.width = NO_WRAP
    buf = io.StringIO()
    y.dump(_literalise(value), buf)
    return buf.getvalue()

def render_with_sources(cfg, path: tuple, theatre: Path) -> str:
    """Render line by line so each scalar's line can carry `# from <file>`."""
    def rel(p) -> str:
        return Path(cfg.provenance[p].source).resolve().relative_to(theatre.resolve()).as_posix()
    out: list[str] = []
    def scalar_text(v) -> str:
        return render_yaml(v).rstrip("\n").removesuffix("\n...").splitlines()[0]
    def emit(node, p: tuple, indent: int):
        pad = " " * indent
        items = node.items() if isinstance(node, dict) else enumerate(node)
        for k, v in items:
            head = f"{pad}{k}:" if isinstance(node, dict) else f"{pad}-"
            cp = (*p, k)
            if isinstance(v, (dict, list)):
                if not v:  # an empty collection has no lines of its own to hold a source comment;
                    out.append(f"{head} {'{}' if isinstance(v, dict) else '[]'}")
                else:
                    out.append(head)
                    emit(v, cp, indent + 2)
            elif isinstance(v, str) and "\n" in v:
                out.append(f"{head} |  # from {rel(cp)}" if v.endswith("\n") else f"{head} |-  # from {rel(cp)}")
                out.extend(f"{pad}  {line}" for line in v.splitlines())
            else:
                out.append(f"{head} {scalar_text(v)}  # from {rel(cp)}")
    node = cfg.merged
    for seg in path:
        node = node[seg]
    emit(node, path, 0)
    return "\n".join(out) + "\n"
