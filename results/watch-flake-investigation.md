# Investigation: intermittent failure of `test_watch_picks_up_an_edit_to_an_included_file`

Worktree/branch: `watch-flake`. Method: superpowers:systematic-debugging (reproduce, instrument, single
hypothesis, fix cause, verify). Machine: macOS (Darwin 27), watchfiles (notify / FSEvents backend).

## 1. Reproduction (baseline, unmodified reference)

Scratch harness (not committed): a parametrised copy of the test body run N times in one pytest session,
logging spawn->readiness and edit->observed timings per run.

| Condition | Runs | Failures | Rate |
|---|---|---|---|
| idle machine | 300 | 4 | 1.3% |

Every failure has `final == []` measured *after* the 5 s wait — the edit was never recorded at all, not
recorded late. So the reconcile never ran for that edit (the watcher does not reconcile except on an
event). This already makes hypothesis 3 (slow commit / lock contention past 5 s) unlikely: a delayed
commit would show up in the post-wait read.

## 2. Instrumentation

Temporary (not committed) stderr tracing in `cmd_watch`: wall-clock stamp at the readiness print, every
batch yielded by `watchfiles.watch` (with paths), and after each reconcile; the scratch test stamps the edit.

Second instrumented run: 300 runs, 4 failures (1.3%, same rate). In **every** failure:

- the edit is written ~0.5 ms after `ready-print` (the harness reacts to the readiness line immediately);
- no batch ever contains `.troupe/coder.yaml` — the edit is never delivered, then or later;
- the watcher is demonstrably live afterwards: from ~200 ms on it delivers a `.troupe/state/lock` event for
  each `history` poll (filtered as irrelevant, correctly), for the full 5 s.

Typical failure (paths shortened):
```
DBG 1790640045.9105 ready-print
edit  1790640045.9109                      <- 0.4 ms later
DBG 1790640046.1147 batch [(1, '/.troupe/state/lock')]
DBG 1790640046.3351 batch []
... lock events only, every ~0.25 s, until the 5 s deadline
```
Typical pass: the same 0.5 ms gap, but the first batch contains `.troupe/coder.yaml` and a reconcile follows
within ~50-130 ms.

Reading of the code: `cmd_watch` prints `watching <dir>` *before* calling `watchfiles.watch(...)`, which is
a generator — the Rust `RustNotify` (and on macOS the FSEvents stream) is only constructed on the first
`next()`, i.e. after the readiness line has been flushed. An edit landing in that gap may or may not be
seen, depending on whether fseventsd assigns its event id before or after the stream's
`kFSEventStreamEventIdSinceNow` start point. Mostly it is (the pass case), sometimes not (the 1.3%).

Hypotheses at this point:
- H1 (readiness printed before the OS watch is registered): supported by the code and the trace.
- H2 (edit coalesced with startup events and filtered): refuted — the event never arrives in any batch, so
  no filter saw it. `_is_relevant` only drops `/state/` and `.troupe-tmp-` paths.
- H3 (history/reconcile lock contention delays commit past 5 s): refuted — no reconcile ever starts in a
  failing run, and the post-deadline read is still empty.
- H4 (same mtime/size so the backend misses it): refuted as a primary cause — FSEvents is event-based, not
  a stat poller; and "opus"->"sonnet" changes the size anyway.

## 3. Discriminating experiment (unmodified reference)

Same scratch test, but sleeping 300 ms between seeing the readiness line and making the edit: **0 / 300**
failures (vs 8 / 600 without the delay). The only variable is how soon after `watching` the edit lands, so
the loss is confined to the window just after the readiness line — H1. (This delay is a diagnostic only; it
is *not* the fix. Adding a sleep to the hidden test would weaken the contract's "once it is watching"
guarantee and hide the same defect in a candidate.)

## 4. Root cause

The reference announced readiness before it was watching. `print("watching …")` preceded the first
`next()` of `watchfiles.watch`, which is where the OS watch is actually registered. A change made in that
gap — exactly what a client that trusts the readiness line does — is lost permanently (the watcher only
reconciles on an event, and no event is ever generated for it).

The hidden test is correct: it relies on precisely the guarantee the contract states ("Once it is
watching, it prints one line `watching <dir>`"). The instrument was measuring a real reference bug, not a
harness race; the harness needs no change.

## 5. Fix (reference/src/troupe_ref/cli.py, `cmd_watch`)

Register -> reconcile -> announce:

1. enter the `fs_watch` generator; its first batch (guaranteed within `rust_timeout`=200 ms by
   `yield_on_timeout=True`) arrives only after the notifier has been constructed and is watching;
2. on that first batch, reconcile unconditionally — this also closes the smaller, previously invisible gap
   between `main()`'s reconcile-first and the watch registration (an edit there produced no event after
   the watch started, so it would have waited for the next unrelated edit);
3. only then print `watching <dir>`.

After that, behaviour is unchanged (reconcile on any relevant batch). Readiness latency moves from a median
of ~150 ms to ~210 ms after spawn (max 0.5 s over 300 runs) — far inside the harness's 20 s readiness budget.

## 6. Before / after: the affected test (scratch loop, 300 runs per cell)

| Reference | idle | moderate CPU load (5x `yes` on 10 cores) |
|---|---|---|
| before (main) | 4/300 and 4/300 (1.3%) | 7/300 (2.3%) |
| after (fix)   | **0/300** | **0/300** |

Pooled: 15/900 failures before vs 0/600 after (Fisher exact p ~ 0.0006).

## 7. Other watcher tests (step 2 and step 4 files)

All 6 `with Watching(...)` uses (5 in step 2, 1 in step 4) were checked for the same mechanism (a file change made right after readiness whose
detection the test depends on):

| Test | Exposed? | Why |
|---|---|---|
| step2 `test_watch_picks_up_an_edit_to_an_included_file` | **yes** | the observed flake (sections 1-6) |
| step2 `test_include_added_by_hand_is_followed` | **yes** | identical shape: hand edit immediately after readiness, then `wait_for` 5 s. Measured in section 8 |
| step2 `test_comment_only_edit_while_watching_records_nothing` | vacuous, not flaky | a missed event makes it pass for the wrong reason (the "no event" assertion was never exercised by a reconcile). The fix removes the vacuity: the edit is now always observed |
| step2 `test_set_while_watching_records_its_change_exactly_once` | no | `set` reconciles and writes itself; a missed watcher event cannot produce the failure it asserts against |
| step2 `test_watch_exits_0_on_sigterm` | no | no file change |
| step4 `test_set_while_watching_is_attributed_to_the_cli_not_the_file` | no | as for the step2 `set` test; a missed event can only make it pass. Its own race (write-back vs reconcile attribution) is guarded by the theatre lock and is unrelated |

No harness change is needed; `Watching`'s readiness wait is correct per contract.

## 8. Before / after: the sibling test `test_include_added_by_hand_is_followed` (idle, 300 runs each)

| Reference | Failures |
|---|---|
| before (main) | 2/300 (0.7%) |
| after (fix)   | **0/300** |

Same mechanism confirmed: this test was also a latent fairness defect, just rarer.

## 9. Verification after the fix

- Two watcher files (`test_step2_sync.py`, `test_step4_lineage.py`) at `--step 4`, **20x in a row: 20/20
  runs, 22/22 tests each, 0 failures**.
- `uv run python harness/validate_suites.py` -> **Result: PASS** (all positive/negative steps; watcher runs
  5/5 with 0 not passing).
- The scratch loop harness was removed from `tests/hidden` (never committed).

## 10. Proposed contract wording (for the controller; contract NOT edited)

The current text — "Once it is watching, it prints one line `watching <dir>` to stdout and flushes" — does
imply the right thing, but a reasonable implementer can read "once it is watching" as "once it has called
the watch API", which is exactly the reference's bug. Because a candidate that prints early will fail the
hidden watcher tests ~1-2% of the time, the obligation should be explicit so such a failure is attributable
to the candidate, not to an ambiguous spec. Proposed replacement for the first bullet's second sentence:

> Once it is watching, it prints one line `watching <dir>` to stdout and flushes. The line is a promise:
> it is printed only after `watch` is able to observe changes, so any change made after the line appears
> is reconciled within 2 seconds. Changes made before the line appears are reconciled too.

(The last sentence is optional; the reference now satisfies it via the reconcile-before-announce step,
but no hidden test depends on it.)
