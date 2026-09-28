"""Which scenario step this reference build behaves as. Gates later-step features."""
from __future__ import annotations
import os

STEP = int(os.environ.get("TROUPE_REF_STEP", "7"))
