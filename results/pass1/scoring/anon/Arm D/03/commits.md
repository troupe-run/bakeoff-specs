# Commits (1, newest first)

Each commit's short SHA and subject, then its message body.

## 363d949 Add config get; make show print sections as YAML, with --sources

get PATH prints a scalar (exit 5 pointing at show for collections); show [PATH]
prints a scalar like get, or a mapping/list as block-style YAML with includes
resolved and text includes as literal blocks; --sources annotates every scalar
line with the file it comes from, relative to the theatre directory.

