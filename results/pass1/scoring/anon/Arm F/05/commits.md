# Commits (21, newest first)

Each commit's short SHA and subject, then its message body.

## 62cb106 Test the override behaviours convergence found untested

Flow mapping-form and flow list-item conversions, a set through a ref-only
text include, and a multi-line override all worked but had no test
(Principle II); the D-44 and D-47 refusals now also check stderr names the
path (SC-404). Each new test was seen to fail on a deliberate break.


## e8ea51c Append step 5 convergence tasks: tests for four untested override behaviours

Convergence found the code correct but four CR-A behaviours without a test
(Principle II) and two refusal tests not checking the path in stderr
(SC-404). CR-B converged with nothing remaining.


## 637bfce Record two design details found while implementing overrides

Merged mappings keep their base so nested include sites stay visible, and a
converted include's key is found in its own file's YAML; both were decided in
code and belong next to research O-4 and O-5.


## 99fe04a Document set --in-include in the README

CR-B: say when to use the flag, that it leaves the including file alone, and
that it changes nothing else.


## cb57ac1 Test that --in-include changes nothing but new keys under includes

CR-B D-50: existing values, list appends, keys in list items, text includes
and refusals must come out the same with and without the flag; each case is
run on two fresh theatres and compared byte for byte, with history.


## 6c151d0 Give the verify tests' stand-in planner the in_include keyword

apply_set now passes in_include to plan_set (CR-B), so the monkeypatched
stand-in in test_verify.py must accept it; four tests had failed since the
flag was threaded through.


## af740d0 Write --in-include keys into the shared file by step 1's rule

When a new setting genuinely belongs to everyone sharing an included file,
set --in-include puts it there instead of in an override (CR-B). For a
section merged from a shared file and an override, the key goes into the
shared file's part. The including file is left untouched.


## 5f7ccbf Accept set --in-include and carry it to the placement decision

CR-B gives set an explicit way to put a new key into the shared file. The
flag is parsed only by set (other subcommands reject it, exit 2) and passed
down to override.place_new_key, the one place that will read it. Merged
mappings expose their shared part so the key can be laid out there.


## 78b4270 Document overrides in the README and mark step 1's new-key rule replaced

Keeps spec, docs and code in agreement for CR-A: the README explains $ref
overrides and where set now writes, and step 1's FR-022/FR-020 point to the
step 5 rules that replace and refine them.


## f0e30cc Test that list changes stay in the file holding the list

Overrides cannot address list items (CR-A FR-424), so appends and keys inside
list items must be written where the list is, whether that is the shared
file or an override.


## bb1f34d Refuse replacing a section whose keys come partly from a shared file

An override can add or change keys but not remove the included file's keys,
so replacing such a merged section could never read back as asked (CR-A
D-44). When every key is overridden, the override itself is replaced.
Overridden values change in the override, others where they live.


## 6851377 Write a new key under an included section as an override

CR-A: included files are shared between projects, so a new setting must not
change them. The new key goes into the file holding the include reference,
converting a one-line include to $ref form first (the contract's example is a
test verbatim). override.py holds the one placement decision; merged
mappings keep their base so nested include sites are still found, and
override writes are verified only at their own reference. The step 1 test
that encoded the old rule now expects the override.


## 91667a1 Test that every command reads overrides as the merged configuration

Covers CR-A's reading rules end to end: merge and replace, --sources per
file, import order without $ref, refusals that exit 4, and reconcile and
watch through $ref. Each test was checked to fail on the previous loader.


## bd1c916 Load mapping-form includes merged with their overrides

CR-A lets an include carry overrides ($ref plus sibling keys). The loader
builds the merged tree directly, each entry still read from the file it is
written in, so get, show, --sources, history and watch need no change.
Merged nodes remember their include site so later edits can find the
override text in the including file.


## 283ad8f Add step 5 task lists for CR-A and CR-B, tests first by user story

CR-B's flag is a mode of CR-A's placement function, so both lists are written
together: CR-A builds the merge and placement, CR-B threads --in-include into
it and proves the flag changes nothing else.


## a83fa90 Add step 5 CR-B plan: --in-include as a mode of the one placement function

The flag only changes where a new key goes, so it is read only by CR-A's
place_new_key; merged mappings keep their unmerged base so the key can be
laid out in the shared file with step 1's rules.


## c7595fa Match only override writes by include reference when verifying

Planning CR-B showed that identifying every include root by its reference
would refuse a write into a file included at two keys, which step 1 allows
and --in-include relies on. Only override writes need the reference identity.


## 2d319c9 Add step 5 CR-B spec: set --in-include writes new keys into the shared file

CR-A keeps new keys out of shared includes by default; CR-B gives users an
explicit way to put one there when it belongs to everyone. The spec restates
the In-include contract as the step 1 placement rule and records how the flag
treats existing values, merged sections and other subcommands.


## 60d0386 Add step 5 plan: merge overrides in the loader, place new keys by include site

The loader builds the merged tree so every reader works unchanged; a new
edit/override.py holds the one decision of where a new key goes and how a
scalar-form include becomes mapping form.


## 75b0bb8 Decide where a merged section's new keys go, and refuse unreachable overrides

Planning showed two cases the spec left open: a mapping with keys from both a
shared file and an override needs a "comes from" file (D-48: the override's,
so no shared file gains the key), and an override position that is itself an
include has no safe target (D-47: exit 3).


## 0aaad5a Add step 5 spec: new keys under shared includes become overrides

CR-A: included files are shared between projects, so adding a setting under
an included section must stop modifying them. The spec restates the Overrides
contract (mapping-form includes with $ref, deep merge, where new keys and
changed values are written), replaces step 1 FR-022, and records the open
points it decides (nested includes, list-item includes, refusals).

