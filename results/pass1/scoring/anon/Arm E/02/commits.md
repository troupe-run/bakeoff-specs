# Commits (1, newest first)

Each commit's short SHA and subject, then its message body.

## 1f533bf Add troupe config watch; reconcile hand edits before every command but history

Commands serialise on .troupe/events.lock so a set's write-back is recorded
before watch can observe it, and so produces no further events.

