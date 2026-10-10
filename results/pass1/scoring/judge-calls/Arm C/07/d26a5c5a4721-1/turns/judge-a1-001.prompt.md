You are a judge in a blind comparison of software development methods. You are judging Arm X at step 7; you do not know which method it used and must not guess.

Part: test_names (dimension: code_quality).

Score it 0-4 against these anchored levels:
0: Names do not describe behaviour (test_1, test_set, test_it_works), or most checked names claim something their body does not assert.
1: More than a quarter of checked names overclaim (the body would still pass if the named claim were false) or describe a different behaviour from the one asserted; or most names only repeat the function under test.
2: Most names describe the asserted behaviour, but two or more overclaim (e.g. 'preserves comments' while asserting only the new value) or are too vague to tell what failed.
3: No checked name overclaims; every one describes a behaviour its body asserts, but one or two are vague or say less than the body checks.
4: Every checked name states a specific behaviour (the condition and the expected result) and the body asserts exactly that, at the level claimed (a byte-for-byte claim is checked byte for byte); the names alone read as a spec of the step.

Your lens (failure triager): CI reports one of these tests failed and gives you only its name. For each checked test, would you know what behaviour broke without opening the body? Then open the body: was your guess right? The checked tests: every test this step added or changed, in diff order, up to the first 30.

Your inputs (read-only; use Read, Glob and Grep):
- /judge/repo/

Cite at least one file path with line, commit, or transcript line for your score.

Reply with exactly one JSON object and nothing else:
{"score": <integer 0-4>, "evidence": ["<path:line, commit sha or transcript line>", ...], "notes": "<one or two sentences>"}

Your previous reply could not be used (not JSON: Extra data: line 2 column 1 (char 291)). Reply with one JSON object only.