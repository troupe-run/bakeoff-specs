"""Scalar-form include -> mapping form (step 5 overrides): byte-surgical, verified, then extended by
the ordinary new-key splice."""
import pytest
from troupe_ref.surgical import SpliceError, convert_include_to_mapping, surgical_set

CASES = [
    # (before, site path, after conversion, after adding temperature: 0.3)
    ("agents:\n  coder: file:agents/coder.yaml  # the coder\n", ("agents", "coder"),
     "agents:\n  coder:  # the coder\n    $include: file:agents/coder.yaml\n",
     "agents:\n  coder:  # the coder\n    $include: file:agents/coder.yaml\n    temperature: 0.3\n"),
    ("x: 1\ncoder: \"file:c.yaml\"", ("coder",),
     "x: 1\ncoder:\n  $include: \"file:c.yaml\"",
     "x: 1\ncoder:\n  $include: \"file:c.yaml\"\n  temperature: 0.3"),
    ("a: {coder: file:c.yaml}                     # z\n", ("a", "coder"),
     "a: {coder: {$include: file:c.yaml}}         # z\n",
     "a: {coder: {$include: file:c.yaml, temperature: 0.3}} # z\n"),
    ("l:\n  - file:c.yaml  # c\n  - 2\n", ("l", 0),
     "l:\n  -  # c\n    $include: file:c.yaml\n  - 2\n",
     "l:\n  -  # c\n    $include: file:c.yaml\n    temperature: 0.3\n  - 2\n"),
    ("a:\r\n  coder: file:c.yaml\r\nb: 1\r\n", ("a", "coder"),
     "a:\r\n  coder:\r\n    $include: file:c.yaml\r\nb: 1\r\n",
     "a:\r\n  coder:\r\n    $include: file:c.yaml\r\n    temperature: 0.3\r\nb: 1\r\n"),
]


@pytest.mark.parametrize("before,site,converted,added", CASES)
def test_conversion_is_byte_surgical(before, site, converted, added):
    assert convert_include_to_mapping(before, site) == converted
    assert surgical_set(converted, (*site, "temperature"), 0.3) == added


def test_anchored_include_is_refused_rather_than_mangled():
    with pytest.raises(SpliceError):
        convert_include_to_mapping("coder: &c file:c.yaml\n", ("coder",))


def test_conversion_indents_at_the_files_indentation():
    before = "agents:\n    coder: file:coder.yaml  # c\n    other: 1\n"
    assert convert_include_to_mapping(before, ("agents", "coder")) == (
        "agents:\n    coder:  # c\n        $include: file:coder.yaml\n    other: 1\n")


def test_conversion_of_a_top_level_key_uses_the_indentation_found_elsewhere_in_the_file():
    before = "coder: file:coder.yaml\nlimits:\n    a: 1\n"
    assert convert_include_to_mapping(before, ("coder",)) == (
        "coder:\n    $include: file:coder.yaml\nlimits:\n    a: 1\n")
