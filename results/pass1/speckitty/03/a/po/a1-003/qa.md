Q1: I checked the current code (`src/troupe/commands/show.py`, `src/troupe/tree.py`) and the step‑1 contract. The new contract is clear apart from one case.

**Question: what should `show PATH --sources` print when PATH is a single value?**

The contract says `show` on a scalar prints the value the way `get` does, which isn't YAML. It also says `--sources` "prints the same YAML" with `# from <file>` comments. Together, those don't say what `show model.temperature --sources` should print.

- **(A) Recommended: print the value as a one-value YAML document with the source comment.**
  - `0.2  # from .troupe/troupe.yml`
  - A text include prints as a literal block whose header line carries the comment, e.g. `|  # from prompts/sys.md`, then the text.
  - The output still answers "where does this come from?", and the YAML stays valid.
- **(B) Print exactly what `get` prints and ignore `--sources` for scalars.**
  - Simpler, but you lose the source information in exactly the case where you asked for it.
- **(C) Something else.** Tell me what you want.

Unless you say otherwise, I'll make these choices myself, since the contract leaves them open, and record them in the spec:

- **Valid YAML:** the YAML output always reads back to exactly the same values.
  - Keys keep their file order.
  - Strings are quoted only when they'd otherwise read back as something else (`"true"`, `"0.2"`).
  - Empty sections print as `{}` / `[]`.
- **Text-include line endings and chomping:** text includes are always literal blocks, as the contract says, and the trailing-newline marker (`|-`, `|`, `|+`) matches the file exactly. A CRLF file therefore appears with plain line breaks in `show`; `get` still prints the exact bytes.
- **Which lines get `# from`:** only lines that hold a value get a comment. A line that only opens a section (`agents:`) and an empty `{}`/`[]` get none.
- **`get` error text:** for a section, the message names the path and points to `config show`, e.g. `tools is a list, not a scalar; use 'troupe config show tools'`.
- **Unchanged behaviour:** a path that doesn't exist exits 5 for both commands. Both commands still pick up hand edits first, as every command except `history` already does.

WAITING_FOR_DISCOVERY_INPUT
A1 (owner): The contract doesn't define `--sources` for a scalar PATH: `show` on a scalar prints it like `get`, while `--sources` is defined as "the same YAML" with `# from <file>` comments (get and show, from step 3). Treat it as out of contract: your choice — state which you chose and why.

Q2: I chose option (A) and committed the spec on `feat/troupe-config-get-show` (commit `99242aa`). Nothing has been implemented yet, and nothing is on `main` yet; that happens after the plan, tasks and implementation phases.

**The out-of-contract case (recorded as D‑1 in the spec and in the decision record):** `show PATH --sources` on a single value prints it as a one-value YAML document with the comment.
- A plain value prints as `0.2 # from .troupe/troupe.yml`.
- A text include prints its literal-block header line with the comment (`|- # from prompts/sys.md`), then the text indented below it.
- Without `--sources`, `show` on a value prints exactly what `get` prints, as the contract requires.

**Why:** `--sources` exists to say where a value comes from, so ignoring it would drop exactly what was asked for. A one-value YAML document is still "the same YAML" for a one-value result, and it reads back as valid YAML.

**Other open points:** the spec records them as D‑2 to D‑10, using the defaults I proposed last turn. Two details are new since then:
- The comment is separated from the value by exactly one space.
- A file outside the theatre directory is named with leading `../`; includes are allowed to point there.

One more case is new: a text include whose content a literal block can't hold falls back to a double-quoted string, so `show` still prints valid YAML.

**What's committed:**
- `kitty-specs/troupe-config-get-show-01M4075F/spec.md`: 14 functional requirements, 3 non-functional requirements, 4 constraints and 3 user stories.
- `checklists/requirements.md`: every item passes.
- The decision record and `meta.json`.

The decision check reports nothing open and no `[NEEDS CLARIFICATION]` markers remain.

**Loose ends:**
- The plan step has already been started, which confirms Spec Kitty accepted the spec. It created a `plan.md` placeholder and left `status.events.jsonl` with uncommitted changes; the plan phase will commit both.
- No code changed yet, so the tests, type checks and lint haven't been run for this work.

Next step is `/spec-kitty.plan`.
A2 (po): /spec-kitty.plan