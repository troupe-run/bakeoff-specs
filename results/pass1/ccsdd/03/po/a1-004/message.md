I've changed the requirements so that every text include is printed as a literal block, with no exception. The revision is committed on `main` as commit `54634ed`, and the requirements are still unapproved.

## What changed
- **4.4**: a text include is always printed as a literal block (`|`), whatever its text.
- **4.5**: if a literal block can't reproduce a text include exactly, such as a file with CRLF line endings, it is still a literal block. Its content lines are the file's exact text, CRLF line breaks included. The double-quoted fallback now applies only to other multi-line strings, which are not text includes and which the contract doesn't cover.
- **Choice 3** in the Boundary Context now says the same and gives the reason.

## Knock-on changes you should check
Two criteria had to change so they don't conflict with the new 4.5:
- **4.1, "reads back exactly"**: a YAML reader turns CRLF into LF, so a CRLF text include can't read back character for character. I added one exception: a text include that a literal block can't reproduce is excused from the read-back promise. The output still shows the file's exact text, and nothing is changed to make it fit.
- **4.6, "non-printable characters only as escapes"**: this now applies outside text includes. Inside a text include, such characters appear unescaped.

## Approval
Do you approve the requirements as revised? Once you do, the next step is:
```
/kiro-spec-design config-get-show
```