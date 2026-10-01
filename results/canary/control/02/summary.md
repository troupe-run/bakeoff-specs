# Step 2 summary — control (canary)

**Outcome:** done after 1 attempt(s); interventions: none
**Hidden tests:** 105/109 passed; new at this step 8/8 (discriminating: 6); arm flakes: 0
**Model pin:** ok (43 transcript assistant messages)
**Cost (estimate):** arm $1.51 · PO $0.13 · harness $0.13
**Time:** 521.7 s wall, 0.0 s waiting on the owner
**Quality:** mypy 114 errors · ruff 18 (arm no config) · mutation score crashed
**Research attempts:** {'denied_web_tools': 0, 'refused_hosts': []}

## Escalations
- none

## Significant PO answers
- "I've added `troupe config watch`, and every command except `history` now picks up hand edits before it runs. It's commit" → Yes, print it as given. In the contract, `<dir>` is the argument passed to `--theatre <dir>` (General: Invocation), and Sync with files says `watch` prints `watching <dir>`. Your choice matches that.

## Owner gates
- none

## Possible missed approvals (PO said `continue`, the arm used approval wording)
- none

## N.a (discovery)
- stopped: discovery-stop (code at turn 1)
- code check: ok
- escalations: none

## Arm violations (A5: the attempt failed; never a harness fault)
- none

## Egress refusals
- none
