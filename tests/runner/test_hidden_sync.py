"""Final fix batch A2: a network failure installing the arm's project is the harness's (`infra-sync`), never an arm
attempt; resolution, build and packaging errors are the arm's. uv output and the proxy log decide; offline (the prep
container and the egress stage are faked)."""
import json
import subprocess
import pytest
from runner import hidden
from runner.faults import HarnessFault
from runner.paths import Paths

HOSTS = [r"^pypi\.org$", r"^files\.pythonhosted\.org$"]
DNS = "error: Failed to fetch: `https://pypi.org/simple/click/`\n  Caused by: dns error: failed to lookup address information"
RESET = "error: Request failed after 3 retries\n  Caused by: Connection reset by peer (os error 54)"
INDEX_5XX = "error: Failed to fetch: `https://pypi.org/simple/rich/`\n  Caused by: HTTP status server error (503 Service Unavailable)"
NO_SOLUTION = "  × No solution found when resolving dependencies:\n  ╰─▶ Because nothing-like-this was not found in the package registry"
BUILD = "  × Failed to build `troupe @ file:///work/bakeoff-specs-x`\n  ├─▶ The build backend returned an error"
REFUSED_OK = 'CONNECT pypi.org:443\nrefused on filtered domain "pypi.org"\n'
REFUSED_ARM = 'CONNECT evil.example.com:443\nrefused on filtered domain "evil.example.com"\n'


@pytest.mark.parametrize("log,proxy,cause", [
    (DNS, "", "network"), (RESET, "", "network"), (INDEX_5XX, "", "network"),
    ("error: tunnel failed", REFUSED_OK, "network"),                 # the proxy refused an allowlisted host
    (NO_SOLUTION, "", "arm"), (BUILD, "", "arm"),
    ("error: tunnel failed", REFUSED_ARM, "arm"),                    # the arm's project wants a host off the list
    ("something else went wrong", "", "arm"),
])
def test_a_failed_sync_is_classified_from_the_uv_output_and_the_proxy_log(log, proxy, cause):
    got, why = hidden.classify_sync(log, proxy, HOSTS)
    assert got == cause and why


class _Stage:
    def __init__(self, logs):
        self.net, self.hosts, self._logs = "none", HOSTS, logs

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def log_text(self):                             # like `docker logs`: everything so far
        self._so_far = getattr(self, "_so_far", "") + (self._logs.pop(0) if self._logs else "")
        return self._so_far


def _fake(monkeypatch, outcomes, proxy_logs=()):
    """Each sync returns the next (exit, log); the stage's proxy log for that try is the next of `proxy_logs`."""
    runs, sleeps = [], []
    monkeypatch.setattr(hidden, "_run", lambda s, timeout, extra=None: runs.append(s) or
                        subprocess.CompletedProcess(s.cmd, outcomes[len(runs) - 1][0], b"", outcomes[len(runs) - 1][1].encode()))
    monkeypatch.setattr(hidden, "_sleep", sleeps.append)
    monkeypatch.setattr(hidden.egress, "Stage", lambda *a, **k: _Stage(list(proxy_logs)))
    return runs, sleeps


def test_a_network_failure_is_retried_with_backoff_then_is_an_infra_sync_fault(tmp_state, tmp_path, monkeypatch):
    runs, sleeps = _fake(monkeypatch, [(1, DNS)] * 4)
    with pytest.raises(HarnessFault) as e:
        hidden.prepare_copy(Paths("dry9", "control"), tmp_path / "a" / "x", tmp_path, "03-a1")
    assert e.value.kind == "infra-sync" and len(runs) == 4 and sleeps == [10, 30, 90]
    rec = json.loads((tmp_path / "hidden" / "prep-03-a1.json").read_text())      # the evidence is kept
    assert rec["hidden"]["ok"] is False and rec["hidden"]["cause"] == "network"
    assert [t["cause"] for t in rec["hidden"]["tries"]] == ["network"] * 4


def test_a_network_blip_that_clears_on_a_retry_installs(tmp_state, tmp_path, monkeypatch):
    runs, sleeps = _fake(monkeypatch, [(1, RESET), (0, "")])
    prep = hidden.prepare_copy(Paths("dry9", "control"), tmp_path / "a" / "x", tmp_path, "03-a1")
    assert prep.prep["hidden"]["ok"] is True and sleeps == [10]


def test_a_resolution_error_is_the_arms_install_failure_not_a_fault(tmp_state, tmp_path, monkeypatch):
    runs, sleeps = _fake(monkeypatch, [(1, NO_SOLUTION)] * 4)
    prep = hidden.prepare_copy(Paths("dry9", "control"), tmp_path / "a" / "x", tmp_path, "03-a1")
    assert prep.prep["hidden"]["ok"] is False and prep.prep["hidden"]["cause"] == "arm"


def test_a_proxy_refusing_an_allowlisted_host_is_infra_sync(tmp_state, tmp_path, monkeypatch):
    _fake(monkeypatch, [(1, "error: tunnel failed")] * 4, [REFUSED_OK] * 4)
    with pytest.raises(HarnessFault, match="infra-sync"):
        hidden.prepare_copy(Paths("dry9", "control"), tmp_path / "a" / "x", tmp_path, "03-a1")


def test_the_install_record_reaches_the_hidden_summary(tmp_path):
    rec = {"ok": False, "cause": "arm", "why": "No solution found", "lockfile": True, "command": "uv sync --frozen",
           "tries": [{"exit": 1, "cause": "arm", "why": "No solution found", "log": "long…"}]}
    s = hidden.summarise(1, {}, ["m::t"], [], [], -1, install_failed=True, collected=["m::t"],
                         install=hidden.install_record(rec))
    s.write(tmp_path)
    got = json.loads((tmp_path / "hidden" / "summary.json").read_text())["install"]
    assert got == {"ok": False, "cause": "arm", "why": "No solution found",
                   "tries": [{"exit": 1, "cause": "arm", "why": "No solution found"}]}


# ---- follow-up 3: only uv's own error lines decide "network"; the arm's build output never does -----------------------

BUILD_SAYS_REFUSED = """\
  × Failed to build `troupe @ file:///work/bakeoff-specs-x`
  ├─▶ The build backend returned an error
  ╰─▶ Call to `setuptools.build_meta.build_wheel` failed (exit status: 1)

      [stderr]
      Traceback (most recent call last):
        File "setup.py", line 3, in <module>
      ConnectionRefusedError: [Errno 111] Connection refused
      error: tcp connect error while fetching the arm's own thing

      hint: This usually indicates a problem with the package or the build environment.
"""


def test_a_broken_build_that_prints_connection_refused_is_the_arms():
    got, why = hidden.classify_sync(BUILD_SAYS_REFUSED, "", HOSTS)
    assert got == "arm" and "Failed to build" in why


def test_uvs_own_caused_by_line_after_a_backend_block_is_still_read():
    log = BUILD_SAYS_REFUSED + "error: Request failed after 3 retries\n  Caused by: Connection reset by peer\n"
    assert hidden.classify_sync(log, "", HOSTS)[0] == "network"
