A bug has been reported in our tracker: troupe-run/bakeoff-specs-speckit-pass1#2. Please handle it.

Contract sections added: Aliases.

---

## Aliases (from step 6)

- Setting a path whose value is defined at an anchor (`&name`) changes it at the anchor, and so everywhere
  the alias is used.
- Setting a path reached **through an alias** (`*name`) → exit 3; stderr mentions `--expand-alias`.
- `set --expand-alias PATH VALUE` replaces that alias with a block-style copy of the anchored node, puts the
  end-of-line comment `# expanded from *<name> by troupe` on the key's line (two spaces before `#`), and then
  sets the value in the copy. Nothing else changes; other aliases still refer to the anchor.
- Merge keys (`<<`) are never written.

---

Delivery: this request is done when its work is committed on the `main` branch of this repository — the `main` branch is what gets tested. Do not push and do not open pull requests.
