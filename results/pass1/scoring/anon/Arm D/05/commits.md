# Commits (2, newest first)

Each commit's short SHA and subject, then its message body.

## f219b7e Add set --in-include to write a new key into the included file


## 26aa408 Write new keys under included sections as overrides in the including file

Includes may now be written in mapping form ($ref plus overrides, deep-merged).
A new key under content from an included file goes into the including file as
an override, converting a scalar-form include to mapping form; existing values
still change where they live, and list items stay in the file holding the list.

