I've recorded your answer: a broken save never stops `watch`. It prints an error to stderr naming the file, records nothing, and reconciles normally once the files load again.

**Question 2: what `watch` prints after `watching <dir>`**

The contract says `watch` emits `set`/`remove` events when it reconciles. It doesn't say whether those events also go to stdout, or only into the recorded history.

- **(A) Nothing else on stdout (my recommendation).** stdout carries only the `watching <dir>` line, and the events can be seen with `troupe config history`. This keeps the only stdout promise in the contract simple to check. It also leaves room to print events in a later step if that turns out to be wanted. Errors from a broken save still go to stderr, as you decided.
- **(B) Print each event as it is recorded,** as a JSON Lines record in the same shape `history` uses.
- **(C) Something else.**

WAITING_FOR_DISCOVERY_INPUT