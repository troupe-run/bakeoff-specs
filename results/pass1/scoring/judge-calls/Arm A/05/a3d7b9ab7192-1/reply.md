```json
{"score": 2, "evidence": ["/judge/questions.md:15-19", "/judge/questions.md:26", "/judge/questions.md:73-75", "/judge/questions.md:83", "/judge/questions.md:135-136", "/judge/questions.md:140-142", "/judge/questions.md:155-163"]}
```

Roughly half of Arm X's questions answered a real gap in the contract, and the other half were already settled by the contract.

**Worth asking (out of contract, Arm X's choice):** bad `$ref` values, `$ref` in a `set` PATH, replacing a whole include, a flag with no include, flag parsing, an include's own string over its overrides (exit 3) and two conflicting writes to one shared spot (Q10, fourth case).

**Within reach:** the comment position (the contract's example), nested includes and removals (the Overrides definition and CR-A), and choices 12–13 (In-include says "the step 1 rule"). In Q9 and Q10 Arm X proposed refusing writes to shared middle and shared files. The owner answered that from the existing placement rules: "No contract rule refuses this write".