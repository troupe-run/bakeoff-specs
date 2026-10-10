Q1: **Question 1: nested includes**

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
A1 (po): Option (A). The contract says the override goes in "the file that contains the include reference (the *including* file)". With nested includes, that is the file holding the reference to the include that the key's deepest existing ancestor comes from. In your example that is `agents/coder.yaml`, which gets the override `model: {$ref: file:models/base.yaml, temperature: 0.3}` written in block form. Follow the contract's definition. The change request explains why the rule exists, and the contract says what to do.

Q2: **Question 2: a `$ref` key whose value isn't an include**

The contract defines mapping form as "a mapping with a `$ref` key whose value is the include string". It doesn't say what happens when a mapping has a `$ref` key whose value isn't an include, for example `$ref: 5`, `$ref: agents/coder.yaml` (no `file:`), or `$ref: [a]`. Right now (steps 1–4), `$ref` is an ordinary key, and no existing test or spec gives it a special meaning.

- **(A) Exit 4, naming the file and the `$ref` path (my recommendation).** The user clearly meant an include and got it wrong. Refusing means `set` never writes an override against a mapping that isn't really an include. This is the conservative choice under TROUPE-002.
- **(B) Treat it as an ordinary mapping.** `$ref` stays a literal key like any other, so `show` prints it and `set` edits it normally. This is lenient, but a typo silently stops the include from working.
- **(C) Something else.**

WAITING_FOR_DISCOVERY_INPUT
A2 (runner): /spec-kitty.specify A second change request has arrived while you work on the first one:

## CR-B: but let me put it in the shared file when I mean to
Sometimes a new setting genuinely belongs in the shared file. Give `set` an explicit way to do that.

Contract sections added: In-include.

---

## In-include (from step 5, change request B)

- `set --in-include PATH VALUE` writes a new key into the included file instead (the step 1 rule).

---

Delivery: this request is done when its work is committed on the `main` branch of this repository — the `main` branch is what gets tested. Do not push and do not open pull requests.
