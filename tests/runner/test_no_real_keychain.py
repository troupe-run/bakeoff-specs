"""Follow-up round 2, item 1: no test ever reads the real keychain. Every keychain reader, driven down to the
`security` binary, hits the guard (tests/runner/conftest.py) and fails loudly — never an absent item, never a value."""
import pytest

from runner import credentials, secrets
from tests.runner.conftest import KeychainBlocked


@pytest.mark.parametrize("read", [
    lambda: credentials.from_keychain(),
    lambda: credentials.github_pat("pass1", "control"),
    lambda: credentials.github_disc_pat("pass1", "control"),
    lambda: credentials._pat_item("bakeoff-gh-pass1-control", "pass1"),
    lambda: secrets.keychain_pat("pass1", "control"),
    lambda: secrets.keychain_disc_pat("pass1", "control"),
    lambda: secrets._oauth(),
    lambda: secrets.literals(),
    lambda: credentials.keychain_item_exists("bakeoff-gh-canary-control"),
], ids=["from_keychain", "github_pat", "github_disc_pat", "_pat_item", "keychain_pat", "keychain_disc_pat",
        "oauth", "literals", "keychain_item_exists"])
def test_every_keychain_reader_is_blocked_in_tests(read):
    with pytest.raises(KeychainBlocked):
        read()
    assert secrets._KEYCHAIN == {} or all(not isinstance(v, str) for v in secrets._KEYCHAIN.values())


def test_a_test_may_still_fake_the_security_call_explicitly(monkeypatch):
    class R:
        returncode, stdout = 0, "fake-token-value\n"
    monkeypatch.setattr(credentials.subprocess, "run", lambda argv, **k: R())
    assert credentials.github_pat("pass1", "control") == "fake-token-value"


def test_other_subprocess_calls_are_untouched():
    assert credentials.subprocess.run(["true"]).returncode == 0
