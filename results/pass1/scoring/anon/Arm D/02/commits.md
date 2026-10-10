# Commits (1, newest first)

Each commit's short SHA and subject, then its message body.

## 7708ad1 Add config watch and reconcile hand edits on every command

Every command except history reconciles the event-sourced projection with
the files first. watch polls the loaded files and reconciles on change. A
flock on .troupe serialises load-reconcile-write so set's write-back is
never picked up as a new change.

