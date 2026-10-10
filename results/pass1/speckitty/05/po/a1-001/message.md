**Question 1: nested includes**

Suppose a shared file includes another shared file:

```yaml
# .troupe/troupe.yml
coder: file:agents/coder.yaml
# agents/coder.yaml
model: file:models/base.yaml
# agents/models/base.yaml
name: gpt
```

Running `set coder.model.temperature 0.3` adds a new key whose deepest existing ancestor (`coder.model`) comes from `base.yaml`. The contract says the override goes in "the file that contains the include reference". Read literally, that's `agents/coder.yaml`, which is itself a shared file.

- **(A) Follow the contract literally (my recommendation).** The override goes in the file holding the nearest include reference (`coder.yaml`), which becomes `model: {$ref: file:models/base.yaml, temperature: 0.3}` in block form. This is predictable and matches the wording. It still modifies a shared file, but one level up.
- **(B) Root file only.** Never touch any included file: the override goes in `troupe.yml` as `coder: {$ref: …, model: {temperature: 0.3}}`. This better matches "shared files stay shared", but it goes beyond what the contract says.
- **(C) Something else.**

Which do you want?

WAITING_FOR_DISCOVERY_INPUT