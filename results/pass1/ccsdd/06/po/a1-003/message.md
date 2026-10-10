## Generated Requirements Summary
The requirements are written as 10 numbered requirements, all in EARS form:
- **Reading (1–3):** anchors, aliases and merge keys now load, which replaces the old exit 4 (decision H). `get`, `show`, `show --sources`, `history`, reconcile and `watch` all see the resolved configuration. Broken forms still exit 4: an undefined alias, an alias inside its own anchor, or an anchor on a key.
- **Setting at an anchor (4):** the change is made at the anchor and shows up at every alias, with history events for every affected path. The anchor stays when its value is replaced.
- **Refusal (5):** a path reached through an alias, including the alias's own key, exits 3. stderr names the file, PATH and `*name`, and mentions `--expand-alias`.
- **`--expand-alias` (6–8):** it takes no value and combines with `--reason` and `--in-include`. It writes a block-style copy with `# expanded from *<name> by troupe`, then sets the value in the copy. Nested aliases are expanded outermost first. It refuses with exit 3 when the alias is inside a flow collection or the key's line already has a comment.
- **Merge keys and safety (9–10):** troupe never writes `<<`, so any write through a merge key exits 3. Every write is checked by reading it back and is written atomically.

**One change from the brief:** merge keys now load, instead of staying exit 4. The contract names them, so files that use them are now covered, and reading them can't change a byte. Writes through them are still refused.

## Document Status
- `.kiro/specs/config-aliases/requirements.md` now includes the contract text from issue #2 and 17 choices with cautious defaults for you to review.
- `spec.json` is at phase `requirements-generated`.
- `roadmap.md` now has the corrected merge-key note.
- Committed on `main` as `7e9eb73`.

## Review Gate
Passed in two passes. The first fixed a contradiction: a no-change `set` through an alias now exits 3 in all cases (choice 17). It also fixed two sentences that weren't in EARS form.

## Next Steps
The decisions most worth your attention are choices 1, 2, 5, 6, 9 and 17. Once you approve:
```
/kiro-spec-design config-aliases
```
Use `-y` to approve the requirements and go straight to design. `/kiro-validate-gap config-aliases` is optional.