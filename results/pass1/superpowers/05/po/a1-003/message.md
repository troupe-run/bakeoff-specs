CR-B is done and committed on `main` as `f219b7e`, with no push and no PR. All 94 tests pass, including 3 new ones.

`troupe config set --in-include PATH VALUE` writes a new key into the included file, the way it worked before CR-A. The include reference in the including file is left as it is. The flag can go before or after `PATH VALUE`.

- **Mapping-form includes** (`$ref` plus overrides): a new key goes into the included file, not into the overrides. That holds even when the overrides already contain part of the path.
- **Existing values** still change where they are set: in the override if there is one, otherwise in the file they come from. The flag only affects where new keys go.
- **No include involved:** the flag makes no difference.

The change is a flag in `src/troupe/cli.py` and one branch in `Writer.add_entries` in `src/troupe/writer.py`. The README and decision 29 in `docs/decisions.md` describe it.