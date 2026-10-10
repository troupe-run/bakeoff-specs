# Commits (9, newest first)

Each commit's short SHA and subject, then its message body.

## 9699529 Give literal blocks an indentation indicator after spaces-only lines

A text starting with a spaces-only line made show print YAML that does not
parse, and made set refuse the value: YAML takes a literal block's
indentation from its first non-blank line and rejects a leading line
indented further. Also test a file included under two keys.


## 8cfe423 Append convergence tasks for step 3

Convergence found that show prints unparseable YAML for text that starts
with a whitespace-only line, and that the same-file-included-twice edge
case has no test.


## adf65bb Document get and show; mark step 1's show PATH replaced

Keeps the README and the earlier specs and contracts in agreement with the
commands as they now behave (Principle VI).


## cc5775a Test that show --sources names each value's file

When a value is surprising, users need to know which file to open. The
view already carries each scalar's file; these tests pin the comments for
the main file, nested and text includes, files outside .troupe/, scalars,
and theatres reached through a symlink.


## 5bcb6b7 Make config show print sections and the whole configuration as YAML

Users want to read the effective configuration without opening and merging
every included file. show now renders any node from the located tree, with
includes resolved and text includes as literal blocks; scalars still print
exactly as get prints them.


## 0c9e74b Add troupe config get, taking over step 1's show

Step 3 makes show print whole sections, so the scalar printer every script
relies on moves to get unchanged. A mapping or list now points the user to
config show. Step 1's show tests move with it.


## a853539 Add step 3 task list

Orders the work so get takes over step 1's show (and its tests) before
show is replaced, keeping the suite green at every commit.


## eadad43 Add step 3 plan and design artifacts

Plans get as step 1's show plus a hint, and a new show rendered from the
located tree so each scalar keeps its source file for --sources. Revises
spec D-22 to use resolved paths, matching how the loader identifies files.


## b4d3d3d Add step 3 spec: get for values, show for anything

Step 3 splits show: get keeps step 1's scalar output, show prints sections
as YAML and can annotate each value with its source file. The spec records
the layout and --sources choices the contract leaves open (D-20..D-26).

