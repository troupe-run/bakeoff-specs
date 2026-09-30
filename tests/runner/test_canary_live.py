"""Task 26 (OD25): the canary's verdict. Reads the evidence of an owner-run `runner canary` (real quota, real GitHub);
this test itself runs nothing, but it is meaningful only after that run and needs the keychain for the secret scan,
so it is opt-in: `--run-live --run-docker --run-network`, only after OD25 is approved and the canary has run."""
import pytest

from runner import orchestrate

pytestmark = [pytest.mark.live, pytest.mark.docker, pytest.mark.network]


def test_every_canary_check_row_holds_on_the_owner_run_canary_evidence():
    rows = orchestrate.canary_check()
    assert all(ok for _, ok, _ in rows), [r for r in rows if not r[1]]
