import dataclasses
import pytest
from runner import config, images


def test_build_refuses_while_digests_are_unpinned(monkeypatch):
    p = dataclasses.replace(config.load_pins(), digests={"debian": "", "node": "x", "uv": "y"}, binary_sha256="z")
    monkeypatch.setattr(images.config, "load_pins", lambda: p)
    with pytest.raises(images.NotPinned, match="debian"):
        images.check_pinned()


def test_base_build_args_use_digests_not_tags():
    args = images.base_build_args(dataclasses.replace(
        config.load_pins(), digests={"debian": "sha256:a", "node": "sha256:b", "uv": "sha256:c"}, binary_sha256="d"))
    assert args["DEBIAN_IMAGE"] == "debian:bookworm-slim@sha256:a"
    assert args["NODE_IMAGE"] == "node:22-bookworm-slim@sha256:b"
    assert args["UV_IMAGE"] == "ghcr.io/astral-sh/uv:0.12.19@sha256:c"
    assert args["CLAUDE_SHA256"] == "d"


def test_cc_sdd_version_probe_reads_the_version_not_the_prefix():          # review C-15
    out = '{"dependencies": {"cc-sdd": {"version": "3.1.0"}}}'
    assert images.npm_version(out, "cc-sdd") == "3.1.0"


def test_pin_writer_only_touches_the_digests_table(tmp_path):              # review B1
    """A pins file with both `[images] uv = "0.12.19"` and `[images.digests] uv = ""` must get only the
    digest filled — the [images] version key is a different table and must survive untouched."""
    pins_file = tmp_path / "pins.toml"
    pins_file.write_text(
        '[images]\n'
        'base = "bakeoff-base:cc2.1.281"\n'
        'uv = "0.12.19"\n'
        '\n'
        '[images.digests]\n'
        'debian = ""\n'
        'uv = ""\n'
    )
    images._set_toml_value(pins_file, "uv", "sha256:deadbeef", table="images.digests")
    text = pins_file.read_text()
    assert 'uv = "0.12.19"' in text                       # [images] version key untouched
    assert '[images.digests]\ndebian = ""\nuv = "sha256:deadbeef"' in text


def test_dockerignore_keeps_the_build_context_small():                     # review M10
    root = images.IMAGES.parent.parent
    ignore = (root / ".dockerignore").read_text()
    for pattern in ["state/", "results/", ".venv/", ".superpowers/", ".git/"]:
        assert pattern in ignore
