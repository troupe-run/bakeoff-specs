import pytest
from runner import paths


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Point STATE/RESULTS (and derived constants) at tmp_path for tests that write evidence."""
    monkeypatch.setattr(paths, "STATE", tmp_path / "state")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(paths, "FAULTS", tmp_path / "results" / "faults.jsonl")
    monkeypatch.setattr(paths, "HALTED", tmp_path / "results" / "HALTED")
    monkeypatch.setattr(paths, "LOCK", tmp_path / "state" / "runner.lock")
    monkeypatch.setattr(paths, "IMAGES_SAVE", tmp_path / "state" / "images")
    return tmp_path
