I've opened the second question as decision `01M4AF5NM3WP8S5TWK2BCMHEPE`.

**Question 2: remote content that changes on the server**

**What happens today:**
- Before every command, troupe reconciles: each resolved leaf that differs from the recorded history becomes one event. These events are attributed to "unknown actor, via file".
- `watch` compares the bytes of the local files a load read every 0.25 s. It reconciles only when one of them changes.

With remote includes, a shared team file can change on the server while nobody touches the theatre. The contract says it is "fetched when the configuration loads" and says nothing about history or `watch`.

**Options:**
- **(A) Record it like a hand edit (my recommendation).** The next command's reconcile fetches the URL and records every leaf that changed, with the same "unknown actor, via file" attribution, naming the include URL as the source. `watch` keeps polling local files only. Remote changes are recorded at the next reconcile it does, or the next command. Fetching every 0.25 s is never done.
- **(B) `watch` also polls the URLs**, on a slower fixed interval (say every 30 s), so remote changes are recorded close to when they happen. This adds steady network traffic and timing behaviour that is hard to test.
- **(C) Keep remote leaves out of history.** History would then no longer match what `get`/`show` return, which breaks the step-3 rule that history explains the current configuration.
- **(D) Something else.**

**My recommendation is (A).** It keeps history complete and honest, adds no polling, and reuses the existing reconcile rule unchanged.

The other gaps the contract leaves open are, as I see it, engineering choices. Unless you object, I'll record each one in the spec with its reason:
- **Fetch timeout:** 10 s. A timeout or any non-2xx response counts as a failed fetch, so exit 4.
- **Relative `file:` includes inside a remote file:** these resolve against the URL's directory and are fetched. They never read the local disk.
- **`--in-include` on a new key whose include is remote:** exit 3, naming the include string, because remote includes are read-only.
- **`!literal` on anything but a string:** exit 4.
- **Every other tag:** still exit 4, as in step 6.

Reply A–D or give your own answer, and flag any of the choices above you'd decide differently.

WAITING_FOR_DISCOVERY_INPUT