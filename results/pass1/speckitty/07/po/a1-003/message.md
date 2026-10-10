The spec for step 7 is written and committed on `feat/troupe-config-remote-includes`. Nothing is on `main` yet: the request is delivered only once the code is built in the later phases and merged into `main`.

- **Spec:** `kitty-specs/troupe-config-remote-includes-01M4BMJ5/spec.md`. It records the confirmed summary, the contract rules, and agent choices S-1 to S-12, each with its reason. S-1 is tied to decision `01M4BMKN…`. S-13 is recorded as following from the contract.
- **Requirements:** 12 functional (FR-001–FR-012), 5 non-functional with measurable limits (NFR-001–NFR-005), and 6 constraints (C-001–C-006). Six user stories, each with acceptance scenarios.
- **Checklist:** `checklists/requirements.md`. Every item passed on the first pass, with no open clarifications.
- **Commits:** `b718e81` (spec and `meta.json`) and `edc9bbe` (decision record and checklist).

Things to know before planning:
- **Existing test changes:** S-13 changes step-1 behaviour. `set b file:p.md` will now write `b: !literal file:p.md`, so the existing test that expects it to create an include has to pass `--include`. The spec's success criterion SC-005 allows for that.
- **New dependency:** the plan will probably add a JSON Schema 2020-12 validator library. The spec mentions this only as an assumption and doesn't name a library.
- **Offline tests:** remote includes will be tested against a local HTTP server the tests start themselves, so no test needs outside network access (C-006).
- **Leftover files:** checking whether the spec was ready for planning (`setup-plan`) created an empty `plan.md`, which is untracked. `status.events.jsonl` has a small uncommitted change made by the tool. Both are left for the plan phase.

The plan-readiness check still reported `phase_complete: false` after the commit.

Next is `/spec-kitty.plan`. Nothing has been pushed and no PR was opened.