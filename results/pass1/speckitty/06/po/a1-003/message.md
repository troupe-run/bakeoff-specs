The spec is written and committed on `fix/troupe-config-anchor-aliases`, so the specify phase is done. Nothing is on `main` yet, and the bug isn't fixed in code: the plan, tasks, implementation, review and merge into `main` still have to happen.

**Spec contents:**
- **Contract rules:** the four Aliases rules exactly as you gave them, with the worked example of `set --expand-alias coder.settings.model sonnet` turning `settings: *d` into `settings:  # expanded from *d by troupe` followed by `model: sonnet`.
- **Out-of-contract choices:** your merge-key decision (A) is recorded as A-0, plus C1–C12, each with its reason.
- **Requirements:** 9 functional requirements, 4 measurable non-functional requirements, 5 constraints, 4 user stories with acceptance scenarios, and the edge cases.
- **Bug finding:** the spec notes that on `main` the reporter's file can't be loaded at all (exit 4), so today's code can't make the reported wrong write. The real fix is making anchors load and adding the new `set` rules.

**Checks:**
- The quality checklist passed every item on the first pass, with no open clarification markers.
- `spec-kitty agent decision verify` came back clean.

**Commits on `fix/troupe-config-anchor-aliases`:**
- `c20e4d1` adds `spec.md`, `meta.json` and `checklists/requirements.md`.
- `88e2578` records the merge-key decision.

Checking readiness for planning created an empty `plan.md`; it's left uncommitted for `/spec-kitty.plan` to fill in.

Bug `bakeoff-specs-speckitty-qht` stays claimed and open until the fix reaches `main`.

**Next:** run `/spec-kitty.plan`, then tasks, implementation and review. After that the branch gets merged into `main` locally, with no push and no PR.

Files are in `kitty-specs/troupe-config-anchor-aliases-01M48SQ8/`:
- `spec.md`
- `checklists/requirements.md`