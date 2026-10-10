**Question 1: nested includes. Which file gets the override?**

**What I found.** The contract says the override goes in "the file that contains the include reference (the *including* file)". That is clear when there is one level of include. It is less clear when includes are nested. For example:

```yaml
# .troupe/troupe.yml
team: file:agents/team.yaml
# agents/team.yaml
coder: file:coder.yaml
# agents/coder.yaml
model: gpt
```

Take `set team.coder.temperature 0.3`. The deepest existing ancestor, `team.coder`, comes from `agents/coder.yaml`. The include reference for that file is in `agents/team.yaml`, and that file is itself an included (shared) file.

**Options**

- **(A) Nearest including file (literal contract reading).** `agents/team.yaml` becomes `coder:` / `  $ref: file:coder.yaml` / `  temperature: 0.3`. This matches the contract word for word. It also matches the list rule ("written in the file that holds the list"), and an override never has to reach through an intermediate file. The downside: `agents/team.yaml`, a shared file, is modified.
- **(B) Outermost file that isn't included (the root file).** `troupe.yml` becomes `team:` / `  $ref: file:agents/team.yaml` / `  coder:` / `    temperature: 0.3`, and the deep merge applies it. No included file is ever modified for a new key. However, this goes beyond the contract's wording, and it has no answer when a list sits between the root file and the ancestor. The list rule would then send the write back into a shared file anyway.
- **(C) Something else:** tell me.

**My recommendation is (A).** It is what the contract says, it is consistent with the list rule, and it keeps the rule to a single principle: the override goes in the file that wrote the include. I'd record the choice and its reason in the spec.

WAITING_FOR_DISCOVERY_INPUT