# Commits (7, newest first)

Each commit's short SHA and subject, then its message body.

## 4ef5d76 Archive config-get-and-show and sync its specs into spec/specs


## 96eec83 Mark config-get-and-show commit task complete


## b9cb4e5 Mark config-get-and-show tasks complete after full test, type and lint run


## 0c7e4f0 Document get, show --sources and the step-3 decisions in the README


## 91b475b Split reading into get (one value) and show (anything, as YAML)

get keeps the step-1 show behaviour scripts rely on and points to
config show when it meets a collection. show now prints sections and
the whole configuration, and --sources names each scalar's file.
get reconciles first like show, so every read sees hand edits.


## c537813 Add a YAML renderer for show, with per-scalar source files

Walks the loaded node tree (not plain data) because only nodes know
which file each scalar came from and which strings are text includes.
Scalars reuse set's quoting and literal-block helpers so both commands
write values by one rule; tests read the output back to prove it.


## 663cef9 Plan get for values, show for anything (method change config-get-and-show)

Step 3 splits reading: get keeps step-1 scalar output, show prints
sections as YAML and --sources says which file each value comes from.

