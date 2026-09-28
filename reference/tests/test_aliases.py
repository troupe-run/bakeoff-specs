"""Step 6 aliases at the splice level: "refuse" (step 6), "expand" (--expand-alias), "anchor" (the naive
pre-step-6 write). Hidden tests cover a mapping alias and a scalar alias; these pin the other shapes."""
import pytest
from troupe_ref.surgical import AliasTargetError, RejectedSet, alias_sites, surgical_set

SHARED = "defaults: &d\n  model: opus\ncoder:\n  settings: *d\nreviewer:\n  settings: *d\n"

EXPAND = [
    # (name, before, path, value, after)
    ("mapping alias", SHARED, ("coder", "settings", "model"), "sonnet",
     "defaults: &d\n  model: opus\ncoder:\n  settings:  # expanded from *d by troupe\n    model: sonnet\n"
     "reviewer:\n  settings: *d\n"),
    ("new key through an alias", SHARED, ("coder", "settings", "temp"), 0.3,
     "defaults: &d\n  model: opus\ncoder:\n  settings:  # expanded from *d by troupe\n    model: opus\n"
     "    temp: 0.3\nreviewer:\n  settings: *d\n"),
    ("scalar alias; comment stays two spaces after a longer value", "a: &x 1  # anchor\nb: *x\n", ("b",),
     "longer value", "a: &x 1  # anchor\nb: longer value  # expanded from *x by troupe\n"),
    ("scalar alias keeps the anchor's quoting and an existing comment", "a: &x 'one'\nb: *x  # mine\n",
     ("b",), "two", "a: &x 'one'\nb: 'two'  # expanded from *x by troupe  # mine\n"),
    ("alias as a list item: the mark goes on the dash line", "d: &d\n  model: opus\nl:\n  - *d\n  - x\n",
     ("l", 0, "model"), "sonnet",
     "d: &d\n  model: opus\nl:\n  -  # expanded from *d by troupe\n    model: sonnet\n  - x\n"),
    ("two aliases on the path: each is expanded, outermost first",
     "base: &b\n  x: 1\nmid: &m\n  inner: *b\n  other: 5\ntop: *m\n", ("top", "inner", "x"), 2,
     "base: &b\n  x: 1\nmid: &m\n  inner: *b\n  other: 5\n"
     "top:  # expanded from *m by troupe\n  inner:  # expanded from *b by troupe\n    x: 2\n  other: 5\n"),
    ("an alias inside the copy, off the path, stays an alias",
     "base: &b\n  x: 1\nmid: &m\n  inner: *b\n  other: 5\ntop: *m\n", ("top", "other"), 6,
     "base: &b\n  x: 1\nmid: &m\n  inner: *b\n  other: 5\ntop:  # expanded from *m by troupe\n"
     "  inner: *b\n  other: 6\n"),
    ("an anchor inside the copied node is referred to, never redefined",
     "d: &d\n  sub: &s\n    a: 1\n  b: 'q'\nc: *d\n", ("c", "b"), "r",
     "d: &d\n  sub: &s\n    a: 1\n  b: 'q'\nc:  # expanded from *d by troupe\n  sub: *s\n  b: 'r'\n"),
    ("the copy follows the file's indentation (4, lists at the key's column)",
     "d: &d\n    model: opus\n    tools:\n    - a\nc:\n    s: *d\n", ("c", "s", "model"), "x",
     "d: &d\n    model: opus\n    tools:\n    - a\nc:\n    s:  # expanded from *d by troupe\n"
     "        model: x\n        tools:\n        - a\n"),
    ("a flow-style anchored mapping is copied in block style", "d: &d {model: opus, n: 1}\nc: *d\n",
     ("c", "model"), "x", "d: &d {model: opus, n: 1}\nc:  # expanded from *d by troupe\n  model: x\n  n: 1\n"),
    ("a null in the copy stays `key:`", "d: &d\n  model:\n  n: 1\nc: *d\n", ("c", "n"), 2,
     "d: &d\n  model:\n  n: 1\nc:  # expanded from *d by troupe\n  model:\n  n: 2\n"),
    ("a block-scalar anchor, then the set", "p: &p |\n  hello\n  world\nq: *p\n", ("q",), "bye",
     "p: &p |\n  hello\n  world\nq: bye  # expanded from *p by troupe\n"),
    ("CRLF", "d: &d\r\n  model: opus\r\nc: *d\r\n", ("c", "model"), "x",
     "d: &d\r\n  model: opus\r\nc:  # expanded from *d by troupe\r\n  model: x\r\n"),
    ("replacing the whole aliased value", "d: &d\n  model: opus\nc: *d\n", ("c",), {"k": 1},
     "d: &d\n  model: opus\nc:  # expanded from *d by troupe\n  k: 1\n"),
]


@pytest.mark.parametrize("name,before,path,value,after", EXPAND, ids=[c[0] for c in EXPAND])
def test_expand(name, before, path, value, after):
    assert surgical_set(before, path, value, alias="expand") == after


@pytest.mark.parametrize("name,before,path,value,after", EXPAND, ids=[c[0] for c in EXPAND])
def test_refuse_names_the_alias_and_the_flag(name, before, path, value, after):
    with pytest.raises(AliasTargetError, match=r"alias \*\w+; use --expand-alias"):
        surgical_set(before, path, value, alias="refuse")


def test_refuse_is_the_default():
    with pytest.raises(AliasTargetError):
        surgical_set(SHARED, ("coder", "settings", "model"), "sonnet")


def test_setting_at_the_anchor_is_not_through_an_alias():
    assert surgical_set(SHARED, ("defaults", "model"), "sonnet", alias="refuse") == \
        SHARED.replace("model: opus", "model: sonnet")


@pytest.mark.parametrize("before,path,after", [
    (SHARED, ("coder", "settings", "model"), SHARED.replace("model: opus", "model: sonnet")),
    ("a: &x 1  # anchor\nb: *x\n", ("b",), "a: &x sonnet # anchor\nb: *x\n"),  # EOL rule: one space
    ("base: &b\n  x: 1\nmid: &m\n  inner: *b\ntop: *m\n", ("top", "inner", "x"),
     "base: &b\n  x: sonnet\nmid: &m\n  inner: *b\ntop: *m\n"),
])
def test_anchor_mode_is_the_naive_pre_step_6_write(before, path, after):
    assert surgical_set(before, path, "sonnet", alias="anchor") == after


@pytest.mark.parametrize("before,path", [
    ("d: &d\n  <<: {z: 1}\n  model: opus\nc: *d\n", ("c", "model")),  # the copy would write a merge key
    ("d: &d\n  model: opus\nc: {s: *d}\n", ("c", "s", "model")),       # no block-style copy in flow
])
def test_expand_refuses_what_it_cannot_copy_faithfully(before, path):
    with pytest.raises(RejectedSet):
        surgical_set(before, path, "x", alias="expand")


def test_alias_sites_skip_merge_keys_and_find_list_items():
    sites = alias_sites("d: &d {a: 1}\ne:\n  <<: *d\nl:\n  - *d\n")
    assert list(sites) == [("l", "0")]
    assert sites[("l", "0")].name == "d"
