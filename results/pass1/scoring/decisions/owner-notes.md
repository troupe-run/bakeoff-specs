# Owner's cross-cutting notes (rating sitting, 2026-10-10)

Notes about behaviour shared by every arm, so it can't separate them in a topic's rating. Carry these into
the report's findings.

- **T34: every arm lets `config set` write a value that breaks schema validation.** The owner said that in
  reality this shouldn't happen: validation should prevent an invalid state before it is written to anything,
  including history.
- **T32: a mistyped or unknown key in `config history <key>`** prints nothing and exits 0 in every arm, with no
  hint that the key doesn't exist. (Raised by Claude; the owner didn't comment.)

## T44: a waiting command blocks with no time limit (all arms)

- Every arm makes a second command (or the watcher) wait on the `.troupe` lock indefinitely rather than timing out or failing.
- Owner: "having a system where a third process waits indefinitely isn't ok. May not matter for this bakeoff — we will need to support different setups."

## T60: get/show print values that don't read back the same (all arms)

- Every arm prints resolved values (`-.inf` as `-inf`, `1e3` as `1000.0`, `0x1F` as `31`, `~` as `null`). `-inf` is not YAML's spelling of infinity, so pasting `get` output back into `set` gives the string "-inf".
- Owner: "we should make sure we're printing out values that should be consumed back in in the same way - -.inf and -inf being different is a meaningful change (bug)".

## T57: replacing a section logs redundant removes, in an order that depends on how it was made (all arms)

- Every arm logs `set m = 0` plus one remove per child key. Owner: the ideal is a single atomic set that implicitly drops the children; the removes are superfluous.
- The removes are ordered by creation for a hand edit, and by file order for `config set`, so the same change reads differently depending on how it was made.

## T69: `set` writes YAML 1.1 lookalikes unquoted to the file (all arms)

- `config set flags.extra on` writes a bare `extra: on`, which YAML 1.1 readers (e.g. PyYAML's default) load as `true`. This is the file-side counterpart of the T60/T69 rule that output should read back as the same value.

## T72: environment-driven store settings (all arms ignore them)

- Every arm ignores eventsourcing environment variables (PERSISTENCE_MODULE, SQLITE_DBNAME, snapshotting), so this isn't rated.
- Owner, for troupe's own implementation: "we'll need to at least have a clear understanding of how this works, and how it may affect things if they're changed over time, or on different machines with push/pull."

## T75: TABs written raw inside single quotes (all arms)

- Every arm writes a TAB-containing value as `'a<TAB>b'`, so the TAB is invisible in the file. Per the owner's T33 point, invisible characters are better shown escaped (`"a\tb"`).

## T43: a `.troupe` that is a plain file is reported as a missing config (all arms)

- When `.troupe` is a regular file rather than a directory, every arm exits 4 with "no configuration file". None says `.troupe` itself is the problem, so the message points the wrong way.

## T49: hand edits between commands collapse into their net change (all arms)

- Hand edits are reconciled only on the next command, as a diff against the last recorded state. `timeout` 3 → 5 → 7 is recorded as 3 → 7, and a value changed and then restored (3 → 5 → 3) leaves no trace. History is not a full log of hand edits.

## T63: an empty `key:` or `null` can't be filled with a nested setting (all arms)

- `config set agents.reviewer.model haiku` on a bare `reviewer:` (or `reviewer: null`) exits 5 in every arm. Turning a null into a section loses nothing, so this arguably refuses a valid edit. A scalar parent (`coder: opus`) being refused is fine.

## T92: no identity is recorded as an anonymous human (all arms)

- With no TROUPE_ACTOR and no login name (or an empty USER), every arm's `set` succeeds and records `{"kind": "human", "id": null}`. Per the sheet, the owner's stated preference during the run was to fail. No arm does, and none records the actor as "unknown" either.

## T96: an edited folded paragraph re-wraps at its old width (all arms)

- When one paragraph of a `>` folded scalar changes, every arm re-wraps it at the width of its old lines, so a once-short paragraph becomes a tall column of one- or two-word lines. New paragraphs wrap at about 55 columns.

## T98: history can show a stale value until another command runs (all arms)

- `config history` never reconciles hand edits. After a hand edit of `retry` from 3 to 9, `history retry` still shows only `retry → 3` until a command like `get` records the edit. Under the owner's planned design, every command reconciles a meaningful file change into a set at start-up, so this can't happen.
- Owner: "running 'config history' is a command which first refreshes config in the same loop, so it wouldn't be stale either."

## T65: a mid-save empty file is recorded as deleting every key (all arms)

- While watch runs, an editor that empties the file and then rewrites it 0.3 s later causes every arm to record `remove` events for every key, then `set` events putting them back. That includes the route whose stated purpose was to wait for the file to settle. troupe's projection design should guard against this explicitly.
