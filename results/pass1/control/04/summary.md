# Step 4 summary — control (pass1)

**Outcome:** done after 1 attempt(s); interventions: none
**Hidden tests:** 130/135 passed; new at this step 14/14 (discriminating: 14); arm flakes: 0
**Model pin:** ok (37 transcript assistant messages)
**Cost (estimate):** arm $1.23 · PO $0.16 · harness $0.00
**Time:** 452.5 s wall, 0.0 s waiting on the owner
**Quality:** mypy 44 errors · ruff 21 (arm no config) · mutation score crashed
**Research attempts:** {'denied_web_tools': 0, 'refused_hosts': []}

## Escalations
- none

## Significant PO answers
- 'Lineage is in and committed on `main` as `c3397d4`. All 29 tests pass. Every event in `troupe config history` now record' → Every command should reject it. The Lineage section says "A CLI command's actor comes from the `TROUPE_ACTOR` environment variable, `human:<id>` or `agent:<id>` (anything else → exit 2)". That rule co

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
