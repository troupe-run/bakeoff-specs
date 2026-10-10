You are writing the context the owner reads before rating the routes in /judge/topic.json, in a blind comparison of implementations. The owner wants results, not code: what you type, what happens. Example of the style: "`config set note -h` -> shows help, sets nothing; `config set note -hello` -> stores \"-hello\"".

Nothing could be run for this topic. Explain in plain words what each route means in practice for someone using or maintaining the software, without code; set examples to [] unless a concrete illustration helps, and then mark it "observed": false.

Never name an implementation, arm, method or tool, and never use letters for arms; refer to routes by number. Keep each result to one or two short lines; show a file's relevant lines when its content is the point. Do not rate the routes.

Reply with exactly one JSON object and nothing else:
{"stakes": "<one or two sentences: what is at stake for a user>", "examples": [{"input": "<what is typed, e.g. `config set retry -1e3`>", "before": "<the starting file, if it matters, else empty>", "results": {"1": "<route 1 result>", "2": "..."}, "observed": true}], "in_practice": "<plain words, when examples alone do not show it; else empty>", "tradeoff": "<one line: what each route costs>"}