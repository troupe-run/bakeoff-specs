# Pass 1: what carries forward into troupe

Written 2026-10-11, when pass 1 closed. It collects the decisions, the owner's design preferences, and the open
questions from scoring and rating, so the troupe build can start from them. The evidence is in `scoring/`:
- `report.md` and `scores.json` hold the results;
- `decisions/ratings.json` and `reslice-ratings.json` hold every rating and the reason for it;
- `decisions/owner-notes.md` lists the issues every arm shared.

The public write-up is https://troupe.run/blog/2026-10-10-methodology-bake-off/.

## Decision: build troupe with OpenSpec

OpenSpec scored 81.7 and came first in all 21 weighting and judge variants (range 80.4–83.0). The other five arms are
within noise of each other. We use it until troupe can build itself.

Adjustments, each from something pass 1 showed:
- **The archive step:** it stops at an interactive question, which stalls an unattended run. Answer it up front.
- **Lint and types:** run the linter and type checker in the pipeline. OpenSpec's lint findings grew from 8 to 34
  under our ruleset, though 31 were unsorted imports.
- **Asking before building:** every arm sometimes decided a design point, built on it, and only mentioned it in the
  end-of-step summary. Troupe's own approval gates must catch these before code lands on them.
- **The issue tracker:** no method writes back to it. In step 6, every GitHub arm fixed the bug and left the issue
  open, with no comment and no link. Add a step that closes the loop.
- **Watch for:** code size (cc-sdd wrote 5× the control's source) and Superpowers-style skipping of the workflow.

## Storage and history

- **Events come first** (T90). Record the event, update the read model, then sync the file from it. A failed
  record must never leave a changed file with no event.
- **The config file is a projection** (see memory `troupe-config-file-is-a-projection`). Every command, `history`
  included, reconciles a meaningful hand edit into a `set` before it does anything else (T98). So history can't
  be stale.
- **State is text that git can merge.** That rules out SQLite and other binary stores.
- **Store settings need a clear model** (T72): how they behave when changed over time, on different machines, and
  across push/pull.
- **Validate before writing anything** (T34). That includes history: an invalid value never reaches the file or
  the log.
- **Replacing a section is one atomic event** (T57). For example, `set m = 0` implicitly drops m's children. There
  are no trailing removes, and the order doesn't depend on how the change was made. Drop-then-set risks an
  inconsistent state after a crash.
- **Writes are atomic.** Write to a temp file in the same directory, fsync it, keep the permissions, then replace
  the original.
- **Every event names its actor.** Fail when there's no identity. If something really is unknown, record an
  explicit `unknown`, never a null or a missing field (T92, legacy-via).
- **Guard against mid-save files** (T65). An editor's momentary empty file must not be recorded as deleting
  every key.
- **Decide on hand-edit granularity** (T49). At present, edits between commands collapse to their net change, and
  3 → 5 → 3 leaves no trace. Decide whether that's acceptable.

## Round-trip fidelity

- **Output reads back unchanged** (T60, show-quoting). Anything `get` or `show` prints must mean the same value
  when you paste it back. `-inf` vs `-.inf` is a bug. Quote anything a YAML 1.1 or 1.2 reader would misread.
- **The file follows the same rule** (T69, nonstring-keys). Don't write bare `on`, `yes`, `null:` or `1e3:` keys
  that other readers take as non-strings.
- **Invisible characters are shown escaped** (T33, T75), for example `"a\tb"`.
- **History is strict JSON Lines.** Bare `Infinity` and `NaN` aren't allowed (nonfinite-history).
- **A tag belongs on the map itself** (T61), not on its first key/value.
- **Keep the file beyond its values:** the BOM, comments, comment columns and layout. New lines copy the line
  ending of the line above. A value and its comment move together.
- **Don't drift between file and screen.** If the file holds a quoted line, `show` shouldn't print a block, and
  the reverse.

## Errors and refusals

- **Refuse rather than guess,** consistently. Silent comment loss is worse than a refusal.
- **Messages name both the problem and the fix,** and point at the real cause. A `.troupe` that is a file is not
  "no configuration file" (T43).
- **Say so when nothing matches.** An unknown key in `history <key>` should give a hint, not print nothing and
  exit 0 (T32).
- **Don't refuse obvious requests.** Addressing `.0` under a missing parent creates a list (digit-segments). A
  null parent can become a section (T63). Setting an identical value is a no-op, not an error
  (include-root-replace).
- **Load errors:** duplicate keys are a load error.

## Concurrency

- **No indefinite, silent waits on a lock** (T44). Time out, or say what you're waiting for. Different setups
  will need this, even if the bake-off didn't.
  - Waiting on another process: 2.
  - Being able to deadlock on your own nested lock: 1.
- **Prefer a lock that leaves no extra state file behind.**

## Command line

- **Global flags go anywhere** (T78), before or after the subcommand. Rated: anywhere 5, before only 4, after
  only 3.
- **Dash-leading values follow convention:** they need `--`. Consistency beats cleverness.
- **Show paths in a friendly full form** (T84), for example `~/Projects/theatre`, not `.` and not the bare
  absolute path.

## Testing and code quality

- **Use property or fuzz tests over unusual file shapes.** Production issues come from the edge cases.
- **Test names say what broke,** and each test checks one behaviour.
- **Less code is generally better,** but not so terse that it becomes obtuse.

## For pass 2

- **Carry the scoring changes forward:**
  - lint per KLOC, with safe fixes weighted 0.1;
  - types split from lint;
  - raw time and cost against the median;
  - judges see commit messages;
  - code size worth 2 points;
  - the final weights.
- **Apply the `test_names` rubric fixes.**
- **Write every rubric before the run,** not after step 5.
- **Score discovery and scored runs together.** Spec Kit asked all its real questions in the discovery runs.
  Superpowers and the control never stopped in discovery.
- **Ask the second-pass questions:** does OpenSpec's lead hold on a different task, and is its lint drift real?

## Still open

- **Multi-human collaboration** between local troupe installs: the git push/pull idea isn't decided.
- **Work tracking:** GitHub Issues or a git-native tracker. Pass 1 shows that whichever we pick needs write-back.
- **Naming:** "the house" and "house rules" are suggested, not agreed.

## Owner admin

- **Bake-off GitHub tokens:** revoke `pass1`, `pass1-disc` and `canary`, and delete the `bakeoff-gh-*` keychain
  items.
- **Arm repos:** they stay private until you decide otherwise.
- **The troupe.run product repo:** publish it before sharing the site, since "Watch on GitHub" 404s until it exists.
