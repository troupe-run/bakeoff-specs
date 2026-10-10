# Commits (5, newest first)

Each commit's short SHA and subject, then its message body.

## 9143f74 Archive config-sync-with-files and sync its specs into spec/specs

Adds the config-sync main spec, folds the config-cli and config-history deltas
into their main specs (the import requirement is replaced, not just reworded,
because hand edits are now recorded), and points the README at the archived
design.


## 260b57d Mark config-sync-with-files tasks complete after full test, type and lint run


## 4384a4c Add troupe config watch: reconcile hand edits as they happen

watch polls the config file and every file it includes by content (no new
dependency, same behaviour on Linux and macOS, catches save-by-rename), and
reconciles once a change has read the same on two polls, so an editor's
truncate-then-write is not recorded as removing everything. The ready line is
printed only after the baseline is taken from the loader's own texts, so no
later edit can be missed. Load failures while watching are reported once and
retried; SIGINT/SIGTERM finish any reconcile in progress and exit 0.


## 401e8f9 Reconcile hand edits before show and set, under a per-theatre lock

Hand edits made while nothing was running are now recorded as set/remove
events by the next show or set; history still only reports what is recorded.
Reconcile shares set's leaf diff (leaves.diff_leaves), so both record the same
events for the same effect. Commands take an flock on .troupe/ itself (no new
file, so an unloadable theatre still gets no state) and set holds it until its
events are saved, so no reconcile can see its write-back first.


## 20902ac Plan config sync with files: reconcile, watch, no re-pickup of write-backs (method change config-sync-with-files)

