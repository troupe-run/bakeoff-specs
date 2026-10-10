# Commits (3, newest first)

Each commit's short SHA and subject, then its message body.

## 3c4bd64 Record decisions: --in-include keeps the disturbance check; nearest include gets the override

Adds DECISIONS.md and a test that set --in-include exits 3, leaving every
file untouched, when the included file is also included elsewhere.


## 3f073d6 Add set --in-include: write a new key into the included file itself

With the flag a new key under included content follows the step 1 rule
instead of becoming an override; under a mapping-form include or a merged
mapping it goes into the included side.


## 5acd7df Keep shared includes shared: write new keys under an include as overrides

Includes may now be written in mapping form ({$ref: file:…, …}); the other
keys are overrides deep-merged into the included content. A new key whose
deepest existing ancestor comes from an included file is added as an override
in the including file, converting a scalar-form include to mapping form
(keeping the key line's comment). Appending list items and new keys inside list
items still write the file holding the list. Overrides on a non-YAML include
exit 4.

