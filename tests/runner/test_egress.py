import pytest
from runner import egress
from runner.egress import decisions, allowlist_text

LOG = '''Sep 28 11:41:44 [1]: Request (file descriptor 4): CONNECT api.anthropic.com:443 HTTP/1.1
Sep 28 11:41:45 [1]: Request (file descriptor 4): CONNECT example.com:443 HTTP/1.1
Sep 28 11:41:45 [1]: Proxying refused on filtered domain "example.com"
'''

def test_decisions_pair_each_connect_with_its_outcome():
    assert decisions(LOG) == [("api.anthropic.com", "allowed"), ("example.com", "refused")]

def test_allowlist_is_one_anchored_pattern_per_line():
    assert allowlist_text([r"^a\.b$", r"^c\.d$"]) == "^a\\.b$\n^c\\.d$\n"


def _fake_docker_run(monkeypatch):
    calls = []
    def fake_run(argv, **kw):
        calls.append(argv)
        return type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()
    monkeypatch.setattr(egress.subprocess, "run", fake_run)
    return calls


def test_exit_cleans_up_even_when_saving_the_log_raises(monkeypatch, tmp_path):   # fix round 1, item 2
    calls = _fake_docker_run(monkeypatch)
    monkeypatch.setattr(egress.Stage, "_save_log",
                        lambda self: (_ for _ in ()).throw(OSError("disk full")))

    with egress.Stage("t", "arm", "run", [], tmp_path / "egress.log") as st:
        pass

    assert ["docker", "rm", "-f", st.proxy] in calls
    assert ["docker", "network", "rm", st.net] in calls
    assert not egress.Path(st._allow.name).exists()


def test_exit_does_not_mask_a_with_body_exception_when_log_save_also_fails(monkeypatch, tmp_path):  # item 2
    _fake_docker_run(monkeypatch)
    monkeypatch.setattr(egress.Stage, "_save_log",
                        lambda self: (_ for _ in ()).throw(OSError("disk full")))

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        with egress.Stage("t", "arm", "run", [], tmp_path / "egress.log"):
            raise Boom("original")
