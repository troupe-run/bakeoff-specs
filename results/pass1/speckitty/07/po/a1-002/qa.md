Q1: **Question 1 of ~3: includes inside a remote file**

Suppose the local file contains `team: https://cfg.example.com/team.yaml`, and the fetched `team.yaml` contains its own include strings, for example `prompt: file:prompts/sys.md` or `extra: https://other.example.com/x.yaml`. The contract doesn't say what those mean.

- **(A) Recommended:** a `file:` string in remote content is resolved relative to the remote URL, so it becomes `https://cfg.example.com/prompts/sys.md` and is fetched from the same server. Nested `https://` includes are allowed. A cycle of URLs exits 4, just like a file cycle today. Everything reached this way is remote, so it's read-only. This matches how relative `file:` paths already work: relative to the file that contains them.
- **(B)** Remote content may contain `https://` includes, but a `file:` include inside it exits 4. A shared file pointing at "a path on your disk" has no clear meaning.
- **(C)** Remote content may contain no includes at all; any include string in it exits 4. This is the strictest and simplest option.
- **(D)** Something else.

Either way, I'll treat values from remote content as read-only, and `--in-include` under a remote include will exit 3.

WAITING_FOR_DISCOVERY_INPUT
A1 (po): The contract defines remote includes as strings starting `https://` or `http://`, "fetched when the configuration loads" (Remote includes and schema). It doesn't say how a relative `file:` include inside fetched content resolves, or whether fetched content may contain further includes. This is out of contract, so it's your choice. In the spec, say which option you chose and why.