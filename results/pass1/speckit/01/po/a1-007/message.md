Not converged yet: one gap remains. I appended task T054 as **Phase 8: Convergence** in `tasks.md` and committed it as `e2cfcd3` on `main`. No code was changed.

**The gap:** `troupe config set p file:o.md` is refused with exit 3, even when `o.md` exists. The value is a valid string, but once written it loads as an include. The check before writing then compares the included file's content with the literal string `file:o.md`, sees a mismatch, and refuses. The error message ("would not read back as the requested value") doesn't explain that.

**T054 asks for:**
- Allow writing a `file:` value when the target loads, checking it against the loaded include instead of the literal string.
- If the target is missing or the include makes a cycle, still refuse with exit 3, but name the include target in the message.
- Add tests for a text target, a YAML target and a missing target, and record the decision in `research.md`.

Nothing else turned up. The other probes behaved as specified, including the fixes from the last pass. Values with explicit YAML tags like `!!binary` lose their tag when written; that's outside the contract, so I didn't raise it.

No extension hooks are registered. Next step: run `/speckit-implement` to complete T054; another converge run after that should come back clean.