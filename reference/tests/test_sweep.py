"""Sweep (ported from spike A's test_q9_sweep.py): every scalar leaf, every mapping (add key) and every
sequence (append) in every "before" of the step-1 golden corpus, set to a battery of awkward values. Each
must splice AND pass source-level verification (target == value, every other node byte-identical in
kind/tag/style/raw value), or be refused on policy grounds (RejectedSet). A SpliceError is a fallback: the
reference could not make the write surgical, and the CLI would refuse it — that is a bug to catch here."""
import importlib.util
from pathlib import Path

from ruamel.yaml.comments import TaggedScalar
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from troupe_ref.surgical import RejectedSet, SpliceError, index, surgical_set

_CORPUS = Path(__file__).resolve().parents[2] / "tests/hidden/writeback_corpus.py"
_spec = importlib.util.spec_from_file_location("writeback_corpus", _CORPUS)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CASES = _mod.CASES

VALUES = ["changed", 42, "a: b", "multi\nline\n", "", "*x", "with 'quote' and \"dq\"", True, "ü ✓",
          {"k": 1}, [1, "two"]]
# step 7: an include-shaped string set without --include is written tagged `!literal`
VALUES += [TaggedScalar("http://h/z.yaml", tag="!literal"), TaggedScalar("file:x.yaml", tag="!literal")]


def sweep():
    tally = {"spliced": 0, "rejected": 0, "failed": []}
    for c in CASES:
        if c.expect != "splice":
            continue
        refs = index(c.before)
        for p, r in refs.items():
            targets = []
            if p:
                targets.append(p)  # replace: scalar leaves AND whole collections
            if isinstance(r.node, MappingNode):
                targets.append((*p, "zz_new"))
            if isinstance(r.node, SequenceNode):
                targets.append((*p, len(r.node.value)))
            for t in targets:
                for v in VALUES:
                    try:
                        surgical_set(c.before, t, v)
                        tally["spliced"] += 1
                    except RejectedSet:
                        tally["rejected"] += 1
                    except SpliceError as e:
                        tally["failed"].append((c.name, t, v, str(e)[:120]))
    return tally


def test_every_leaf_add_and_append_in_corpus_splices():
    t = sweep()
    print(f"spliced={t['spliced']} rejected={t['rejected']} failed={len(t['failed'])}")
    for f in t["failed"][:20]:
        print(f)
    assert t["spliced"] > 2000
    assert t["failed"] == []
