## Status
The design is written to `.kiro/specs/config-get-show/design.md`, with its decision log in `research.md`, and committed on `main` as commit `2f54cd2`. `spec.json` now shows phase `design-generated`; the design is not yet approved.

## Discovery
I used the light discovery process, since this extends an existing CLI and adds no new dependency.

## Key findings
- **`show` needs a refactor first.** The quoting and literal-block rules `show` needs already exist in the `set` code. But an existing test forbids core modules from importing that code, and those functions reject some strings with "write refused". So the design moves the parts that don't write files into a new core module, `troupe/config/yaml_style.py`. `set` keeps using them under the same names, and its byte-exact tests must still pass unchanged. This move is the riskiest step and is planned as a separate first task.
- **`--sources` needs no loader change.** The loaded configuration already records which file every value came from, and for a text include that is the included file. The new YAML writer builds each output line together with the file of the value it holds. Removing the comments therefore gives exactly the plain output (5.5) without extra work.
- **Literal-block indentation, settled by experiment.** Content must sit 2 columns past the key or dash that owns the block (`- k: |` puts the content under `k`). This is how the design reads the wording of 4.4; reading it more literally would print YAML that doesn't load back correctly. The same experiment confirmed that CRLF content reads back as LF, which is the case 4.5 exempts.

## Review gate
Passed:
- Every requirement ID (1.1–6.8) is traced to a component.
- The boundary sections are filled in.
- Every component has a file path.

## Next action
Review and approve the design, then:
```
/kiro-validate-design config-get-show   # optional
/kiro-spec-tasks config-get-show
```