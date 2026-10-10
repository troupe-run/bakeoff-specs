The task plan isn't finalized. The second sanity review returned `NEEDS_FIXES` (review mode: `independent`), and the skill allows only one repair round, so I stopped. `spec.json` is unchanged and the plan isn't approved.

Neither review returned `RETURN_TO_DESIGN`. Every finding has been applied to the draft, but they are unreviewed and uncommitted:
- **Task plan (draft):** `.kiro/specs/config-aliases/tasks.md` (new).
- **Design (already approved):** `design.md` now has four clarifications, so I need your approval before they're committed:
  - **Provenance through `$ref` overrides:** `overrides.deep_merge` must keep `anchor`, `alias` and `merge` from the included side. Today it drops them. An alias behind `$ref` overrides would then lose its marker, and a write could reach the anchor.
  - **Refusal order:** target resolution refuses first, then the alias guard, then the planner.
  - **Checking the expanded write:** the widened intended configuration comes from the expanded document, while verification runs against the original files.
  - **Copy containing `<<`:** refused with the merge-key message plus the alias name. I also removed a wrong diagram edge.

**What the second review found, now fixed in the draft:**
1. After 2.1 accepts anchors, an alias would load silently as a plain copy before 2.2 builds alias places. 2.1 now refuses aliases on load (exit 4) until 2.2 removes that refusal.
2. The temporary `set` refusal had no test for a file that uses only an inline `<<`. 2.3 now pins one.
3. A grep over all of `tests/` can't check traceability, because earlier specs use the same `Req N.M` numbers. The check is now limited to this spec's own test files.
4. The design and task 3.6 gave different messages for the refusal to copy a node that holds `<<`. Both now use the merge-key message.
5. 3.6 also needs `AliasSite` from 3.3, so it now depends on 3.3 as well.
6. 3.4 lost its `(P)`, since it depends on 3.1.

**Plan shape:** 5 groups, 16 sub-tasks, and all 51 requirement IDs covered. Three tasks are marked `(P)`: 1.2, 3.2 and 3.3. A temporary refusal stops `set` writing through an alias or merge key between 2.1 and 4.1.

**Next:** to approve the design clarifications, re-run `/kiro-spec-tasks config-aliases`. It picks up the draft, reviews it again from scratch, and only then writes and asks for approval.