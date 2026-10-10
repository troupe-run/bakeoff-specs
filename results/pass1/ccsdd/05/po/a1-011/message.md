Everything you approved is now implemented and committed on `main`, ending at `a8eb266`; nothing was pushed. On the final state:
- the full suite passes (3303 tests);
- mypy and ruff are clean;
- requirements 4.8 and 11.1–11.5 are each named by tests.

**Behaviour now**
- **Files included at more than one place:** every write goes to the shared file and appears at every place that file is included. History records one event per changed path. An outer override at a place still wins there. This covers:
  - changing an existing value (rule 1);
  - `--in-include`;
  - a new key in a list item;
  - list appends and removals;
  - replacing a shared text include.
- **One VALUE asking for the same shared location at two places:** agreeing values are written once; conflicting values exit 3, naming PATH and the shared file, and nothing changes. This is recorded as choice 18 and Decision 12, with the reason that no single write can satisfy both and refusing cannot lose data.
- **An include's own string over an include that has overrides:** refused with exit 3 (choice 16, Decision 10), as you approved.
- **Safety:** the read-back check is still an exact comparison. The expected result at other places is computed only from the files before the write, never from what was written. A change at a place PATH doesn't reach is refused. A permanent test pins that this computation matches what the loader builds.

**Limits worth knowing**
- **Conflicts in practice only arise with text includes.** For YAML files, one VALUE can only reach two places of a shared file by replacing the includes themselves, and that is refused earlier by rule 4. The YAML agree and conflict logic is therefore covered by unit tests only.
- **One case gives a vaguer message.** If a text include is kept at one place and changed at the other, it still exits 3 with nothing changed, but the message is the general "differs from the intended configuration", not the conflict message.
- **Earlier tests rewritten:** two step-1 tests that expected "file included twice → refused" now expect the write. The concurrency test now gets its refusal another way.
- **Spec note:** config-set-writeback 14.2 has a note saying a file being included twice no longer causes a refusal by itself.