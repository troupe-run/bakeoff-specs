I've written the implementation plan and its design documents and committed them on `main` (`a12810d`). The plan passes the constitution check on every principle and technical constraint, both before and after design. Nothing is implemented yet.

**Main design decisions:**
- **Reading files:** `ruamel.yaml` is used only to read each file into a tree of nodes with their exact positions in the text. A probe confirmed the positions are exact, including in files with CRLF line endings. Its own output is never used to write files, because it can reformat comments and quoting.
- **Value types:** the tool works out plain values' types itself under the YAML 1.2 core schema. The probe showed ruamel reads `1_000` as an integer, which the core schema doesn't allow.
- **Writing (`set`):**
  - Each change is a small text replacement in the one file that holds the value.
  - Before anything is written, the changed text is re-read in memory. If it doesn't load, or doesn't read back as the requested value, `set` exits 3 and nothing changes.
  - The file is then replaced in one atomic step.
- **History:** events come from comparing every value before and after a `set`. That way a file included in two places produces events at both paths, and earlier hand edits never show up as `set` events.
- **Event store:** an `eventsourcing` record per theatre, kept in `.troupe/troupe-events.sqlite`. A history line's `seq` comes straight from the stored event order, so it never repeats or restarts.
- **Command line:** built with `argparse`, which already exits 2 on usage errors. All exit codes are defined in one module.

**Generated files** in `specs/001-config-load-show-set/`:
- `plan.md`
- `research.md` (12 decisions, each with reasons and alternatives)
- `data-model.md`
- `contracts/cli.md`
- `quickstart.md`

No extension hooks are registered. The next step is `/speckit-tasks`.