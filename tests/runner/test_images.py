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


def test_cc_sdd_version_probe_reads_the_version_not_the_v_prefix():        # review C-15, fix-round-1 item 6
    assert images.cc_sdd_version("cc-sdd v3.1.0\n") == "3.1.0"


def test_specify_version_probe_reads_the_version_out_of_the_banner():
    """`specify version` always prints its ASCII banner and a boxed info panel first — found building the
    speckit image for real (task-3-report.md); `_versions` must not take the banner's first line."""
    banner = (
        "              ███████╗██████╗ "
        "███████╗\n"
        "╭───────── Specify CLI Information ─────────╮\n"
        "│     CLI Version    1.0.12                                                    │\n"
        "│          Python    3.12.14                                                   │\n"
    )
    assert images.specify_version(banner) == "1.0.12"


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


def test_unpinned_plugins_lists_plugins_missing_a_recorded_sha():          # review B2
    plugins = [config.Plugin(name="a", marketplace="", install="", version="1", repo="x/y", tag="v1",
                              sha="abc123", subdir=""),
               config.Plugin(name="b", marketplace="", install="", version="1", repo="x/y", tag="v1",
                              sha="", subdir="")]
    arm = dataclasses.replace(config.load_arm("control"), plugins=plugins)
    assert images._unpinned_plugins(arm) == ["b"]


def test_pin_plugins_parks_a_plugin_whose_tag_does_not_exist_instead_of_raising(tmp_path, monkeypatch):
    """review B2: a plugin whose tag can't be resolved (e.g. bmad-plugins has no `v6.12.0` tag) is recorded
    as an error, sha stays empty, and the *other* plugin in the same arm still gets pinned."""
    from runner import gitops
    arm_toml = tmp_path / "x.toml"
    arm_toml.write_text(
        'name = "x"\ntool = "t"\nversion = "1"\ncitation = "c"\nimage = "i"\ntracker = "github"\n'
        'repo_name = "bakeoff-specs-x"\nenv = {}\n\n[egress]\nsetup = []\nrun = []\n\n[setup]\nshell = []\n'
        'agent = []\n'
        'plugins = [{ name = "good", marketplace = "", install = "", version = "1", repo = "obra/superpowers",'
        ' tag = "v6.4.2", sha = "", subdir = "" },\n'
        '           { name = "bad", marketplace = "", install = "", version = "1", '
        'repo = "bmad-code-org/bmad-plugins", tag = "v6.12.0", sha = "", subdir = "" }]\n'
        'manifest_paths = [".claude"]\n\n[drive]\nentry = "{handoff}"\nbug_entry = "{handoff}"\nmust_run = []\n'
        'must_run_source = ""\nfresh_session_before = []\nexport_after = ""\n')
    monkeypatch.setattr(config, "ARMS_DIR", tmp_path)

    def fake_ls_remote_tag(repo, tag):
        if repo == "bmad-code-org/bmad-plugins":
            raise gitops.TagNotFound(f"{repo}@{tag}: no such tag on the remote")
        return "8ca22dba9a94f28898bbce59f2537ff4d87c747d"
    monkeypatch.setattr(gitops, "ls_remote_tag", fake_ls_remote_tag)

    got, errors = images._pin_plugins(["x"])
    assert got == {"x:good": "8ca22dba9a94f28898bbce59f2537ff4d87c747d"}
    assert "x:bad" in errors and "no such tag" in errors["x:bad"]
    text = arm_toml.read_text()
    assert 'tag = "v6.4.2", sha = "8ca22dba9a94f28898bbce59f2537ff4d87c747d"' in text
    assert 'tag = "v6.12.0", sha = ""' in text          # parked: left unresolved, not raised


def test_unpinned_plugins_is_empty_once_every_plugin_has_a_sha():
    """The gate `build_all` uses to decide whether an arm is buildable (review B2): non-empty means park."""
    arm = dataclasses.replace(config.load_arm("bmad"), plugins=[
        config.Plugin(name="good", marketplace="", install="", version="1", repo="x/y", tag="v1",
                      sha="deadbeef", subdir="")])
    assert images._unpinned_plugins(arm) == []


def test_build_all_skips_an_unpinned_arm_and_records_the_error_without_failing_the_rest(monkeypatch, tmp_path):
    """review fix-round-1 item 4: build_all's B2 skip-and-record path, isolated from real docker calls."""
    pins = dataclasses.replace(config.load_pins(),
                                digests={"debian": "sha256:d", "node": "sha256:n", "uv": "sha256:u",
                                         "alpine": "sha256:a"},
                                binary_sha256="deadbeef", bd_sha256="beadbeef")
    monkeypatch.setattr(images.config, "load_pins", lambda: pins)
    monkeypatch.setattr(images, "LOCK", tmp_path / "images.lock.json")
    monkeypatch.setattr(images, "_build", lambda *a, **k: None)
    monkeypatch.setattr(images, "_save", lambda tag: "tarhash")
    monkeypatch.setattr(images, "current_id", lambda tag: f"id:{tag}")
    monkeypatch.setattr(images, "_versions", lambda tag, extra: {})

    lock = images.build_all(["bmad", "control"], rebuild=True)

    assert lock["arms"]["bmad"]["image"] == "bakeoff-arm-bmad:1"
    assert "unpinned plugin(s)" in lock["arms"]["bmad"]["error"]
    assert "id" not in lock["arms"]["bmad"]
    assert lock["arms"]["control"]["id"] == "id:bakeoff-base:cc2.1.281"
    assert "error" not in lock["arms"]["control"]
