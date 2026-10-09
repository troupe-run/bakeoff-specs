# Decision review: behaviour context, 1–5 ratings, chat rating — plan

**Approved by the owner on 2026-10-09:** "go ahead" (20:14), "required is fine", "Show behaviour, not code".
Execution: native, on main, with one whole-branch review by a fresh agent at the end.

**Spec:** `docs/superpowers/specs/2026-10-05-scoring-design.md` §8 (decision review). This plan amends §8.

## Why

The owner could not assess the routes on the rating sheet. Each route was one line of text with no example of what it
does. They also want to see every arm's version before rating any one, a finer scale, and to rate in chat.

## Decisions

- **D1. Scale.** The ratings become `1`–`5` plus `n/a`. The previous good/acceptable/poor/out_of_scope scale is
  replaced, which is allowed because nothing had been rated yet. The anchors are written on the sheet:
  - 5: what you'd want;
  - 4: sound, with a minor cost;
  - 3: works, with a real cost or risk;
  - 2: wrong for some realistic case;
  - 1: wrong or harmful;
  - n/a: not a real choice, or does not matter.

  The scores are 0, .25, .5, .75 and 1 (`weights.toml` `rating_1`..`rating_5`), and `n/a` is excluded. The import
  accepts `n/a`, `na` and `-1` (the owner's own suggestion). **The reason becomes optional.**
- **D2. Arm letters.** The aligner prompt forbids labels and letters in its text fields. `parse_topics` rejects text
  that names a label (the parse-retry path). The leak check scans the rating sheet as well as `anon/`.
- **D3. Context stage** (`decisions-context`), between align and sheet. It makes two judge calls per topic:
  1. **Plan.** The inputs are the topic (route text only, no labels) and the scenario step specs. It replies
     `{"runnable": bool, "files": {path: text}, "commands": [[argv after "troupe"]], "show": [paths]}`.
  2. **The harness runs the commands.** They run in each label's final-step code, using
     `hidden.prepare` + `hidden.run_script` (tester sandbox, arm uid, no network), in a fresh theatre per label.
     The output is captured and scrubbed.
  3. **Write.** The inputs are the topic and the results, grouped by route. It replies
     `{"stakes", "examples": [{"input", "before", "results": {route_no: text}, "observed"}], "in_practice", "tradeoff"}`.

  The output goes to `decisions/context/<topic id>.json` and is resumable: a failure is recorded and shown as "no
  context". The code runs at each arm's **final** step, and the sheet says so.
- **D4. Sheet layout.** Every topic shows the question, then the context (stakes, the comparison with every route
  side by side, the trade-off), then the routes with `rating:` and `reason:`.
- **D5. Chat rating.** `python -m runner.scoring.rate <pass> show <T>` prints one topic, and `... set <T> "<r1> <r2> …"
  ["comment"]` writes it into `rating-sheet.md`. The sheet stays the record.

## Tasks

1. D1 scale (decisions, scales, weights.toml, aggregate, sheet text, spec note) with tests.
2. D2 letter guard (prompt, parse_topics, leakcheck over the sheet) with tests.
3. D3 context stage (`runner/scoring/context.py`, cli stage, estimate) with tests using FakeJudge and a fake runner.
4. D4 sheet rendering with context, with tests.
5. D5 rate helper with tests.
6. Run book update. Re-run align → context (show the owner 2–3 topics first) → sheet → leak-check.
