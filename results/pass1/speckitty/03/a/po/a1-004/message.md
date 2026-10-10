The plan for `get`/`show` is done and committed on `feat/troupe-config-get-show` (commits `d6375aa` and `55c2b7a`). No code has been written yet, so the tests, type checks and lint haven't been run for this work.

**Quoting decision (D‑11), now also in the spec:** in `show`'s YAML output, a string goes unquoted only if three readers all get back exactly the same string: troupe's own YAML 1.2 core resolver, ruamel in YAML 1.2 mode and ruamel in YAML 1.1 mode. Everything else is double-quoted.

**Why:** the contract names a YAML version only for parsing `VALUE`, not for `show`'s output. That output is meant to be read and reused, possibly by tools that follow YAML 1.1. A few extra quotes can't change a value, but a reader turning `yes` into `true` would (TROUPE‑002).

I checked this against the real ruamel loader, and quoting needs more than the YAML 1.1 cases. Even in YAML 1.2 mode, ruamel reads `1_000` as an integer and `2001-12-14` as a date, and refuses `<<` and `=`. So unquoted strings are decided by reading each one back with all three readers, not from a fixed list.

**Design, as you confirmed it:**
- **`get`:** the old single-value `show` code, moved to `commands/get.py`. For a mapping or list it exits 5 with `troupe: agents is a mapping, not a scalar; use 'troupe config show agents'`. `get --sources` is a usage error (exit 2).
- **`show`:** a new `render.py` turns the configuration into lines, each tagged with its source file or none. `show` joins them and adds ` # from <file>` only with `--sources`, so the two outputs can't drift apart.
- **Quoting:** the read-back checks live in `yamlcore.py`, still the only module that uses ruamel. No new dependencies.
- **Tests:** the existing single-value `show` tests move to `test_get.py`. A new `test_show.py` reads the output back with the real ruamel library.

**Implementation concerns for the tasks step:**
- **IC‑01:** `get` and the command-line options.
- **IC‑02:** the quoting checks in `yamlcore`.
- **IC‑03:** the renderer and `show`.
- **IC‑04:** the contract, help text and docstrings.

Files are in `kitty-specs/troupe-config-get-show-01M4075F/`:
- `plan.md`
- `research.md`
- `data-model.md`
- `contracts/cli-get-show.md`
- `quickstart.md`

The new contract replaces only the step‑1 `show PATH` row.

**Branch:** current, planning base and merge target are all `feat/troupe-config-get-show`. The finished work goes onto `main` by a local merge, with no push and no PR.

Next step is `/spec-kitty.tasks`.