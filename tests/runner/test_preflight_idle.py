"""preflight.idle(): host AND Docker VM load (review §3 NOTE 8). Pure: docker and load readings are patched."""
from runner import preflight


def _patch(monkeypatch, *, others=(), host=0.1, vm=(0.1, 8)):
    monkeypatch.setattr(preflight.docker, "running", lambda label="bakeoff.run": list(others))
    monkeypatch.setattr(preflight.os, "getloadavg", lambda: (host, host, host))
    monkeypatch.setattr(preflight.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(preflight, "_vm_load", lambda: vm)


def test_idle_is_ok_when_nothing_runs_and_both_loads_are_low(monkeypatch):
    _patch(monkeypatch)
    ok, detail = preflight.idle()
    assert ok, detail


def test_a_busy_docker_vm_makes_the_machine_not_idle_even_with_a_quiet_host(monkeypatch):   # review m11
    _patch(monkeypatch, host=0.1, vm=(7.9, 8))          # load_factor 0.5 x 8 = 4.0
    ok, detail = preflight.idle()
    assert ok is False and "vm_load1=7.90" in detail and "vm_cpus=8" in detail


def test_a_busy_host_makes_the_machine_not_idle(monkeypatch):
    _patch(monkeypatch, host=6.0)
    assert preflight.idle()[0] is False


def test_another_bakeoff_container_makes_the_machine_not_idle(monkeypatch):
    _patch(monkeypatch, others=["abc123"])
    ok, detail = preflight.idle()
    assert ok is False and "containers=1" in detail
