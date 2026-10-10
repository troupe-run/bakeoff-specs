CR-B is implemented and committed on `main` as `3f073d6`. All 52 tests pass, including a new one for the flag.

`troupe config set --in-include PATH VALUE` writes a new key into the included file itself, following the step 1 rule, instead of adding it as an override:
- **Scalar-form include** (`coder: file:agents/coder.yaml`): the key goes into `coder.yaml`, and the reference in the including file is left unchanged.
- **Mapping-form include, or a mapping where an override merges into included content**: the key goes into the included file's mapping, not next to `$ref`. To make that possible, each merged node now keeps a link to the included mapping underneath it.
- **Existing values**: the flag makes no difference. An overridden value still changes the override, and one that isn't is changed in the file it comes from.

The README's usage line and include notes now mention the flag.

**Decision for you:** if the same file is included in two places in one theatre, `--in-include` is refused with exit 3 ("write-back would disturb …"), because the new key would show up under both. That's the same safety check that already blocks changing a shared file's existing values. I kept it, since the contract says to use the step 1 rule. If you'd rather `--in-include` skip the check, since writing to the shared file is then deliberate, it's a small change.