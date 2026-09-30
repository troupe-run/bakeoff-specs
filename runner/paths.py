"""Every on-disk location the runner uses. Nothing else in runner/ builds a state/ or results/ path."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE = REPO_ROOT / "state"
RESULTS = REPO_ROOT / "results"
LOCK = STATE / "runner.lock"
FAULTS = RESULTS / "faults.jsonl"          # real passes; dry passes are namespaced (Task 22)
HALTED = RESULTS / "HALTED"
IMAGES_SAVE = STATE / "images"             # `docker save` tars (Task 2)
REAL_PASSES = ("pass1",)                   # the real run (owner, 2026-09-29: pass 2 is retired; follow-up 10)


def brief_path(pass_: str) -> Path:
    """The real brief for real passes; a copy for dry runs, the probe and the canary (never edits the real one)."""
    return REPO_ROOT / "scenario" / "po-brief.md" if pass_ in REAL_PASSES else STATE / pass_ / "po-brief.md"


@dataclass(frozen=True)
class Paths:
    pass_: str
    arm: str

    @property
    def base(self) -> Path: return STATE / self.pass_ / self.arm
    @property
    def home(self) -> Path: return self.base / "home"
    @property
    def config_dir(self) -> Path: return self.home / ".claude"
    @property
    def work(self) -> Path: return self.base / "work"
    @property
    def repo(self) -> Path: return self.work / f"bakeoff-specs-{self.arm}"
    def inbox(self, role: str) -> Path: return self.base / "inbox" / role
    @property
    def snapshots(self) -> Path: return self.base / "snapshots"
    @property
    def progress(self) -> Path: return self.base / "progress.json"
    @property
    def scratch(self) -> Path: return self.base / "scratch"
    @property
    def po_home(self) -> Path: return STATE / self.pass_ / "po-home" / self.arm
    def teammate_home(self, attempt: int) -> Path: return self.base / f"teammate-home-{attempt}"
    @property
    def results(self) -> Path: return RESULTS / self.pass_ / self.arm
    def step(self, n: int) -> Path: return self.results / f"{n:02d}"
    @property
    def setup_results(self) -> Path: return self.results / "00-setup"
    @property
    def container_repo(self) -> str: return f"/work/bakeoff-specs-{self.arm}"
    @property
    def container_home(self) -> str: return "/home/actor"
