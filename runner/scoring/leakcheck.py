"""Leak check over a written `anon/` tree (final review I2): every file, contents AND path, `repo/` and `diff.patch`
included, searched for every arm's name, alias, tool folder and CLI in every separator form.

Deliberately independent of anonymise's regexes: a plain case-insensitive substring search, where a short word (under 6
characters) counts only at a word boundary and a preceding JSON/transcript escape (backslash-n, -t, -r, -quote) is a
boundary too (R26(b)). The banned words come from the arms' config (`anonymise.banned_words`, the same source the
scrubber is built from), so a leak the scrubber's patterns miss is still found here."""
from __future__ import annotations
import re
from pathlib import Path
from runner import config
from runner.scoring import anonymise

# Forms the config does not spell but that identify an arm (CLI names, the repo family, the tracker's database).
EXTRA_WORDS = ("specify_cli", "specify cli", "bakeoff-specs-", "bakeoff_specs_", "dolt", "bead", "bd")
SHORT = 6


def forms(word: str) -> set[str]:
    parts = re.split(r"[-_ ]+", word.lower())
    return {sep.join(parts) for sep in ("", "-", "_", " ")}


def hits(low: str, word: str) -> bool:
    """`word` (lower case) occurs in `low` (lower-cased text): anywhere when it is 6+ characters, else at a word
    boundary, where a preceding backslash-n, -t, -r or -quote counts as a boundary."""
    start = 0
    while (i := low.find(word, start)) != -1:
        start = i + 1
        if len(word) >= SHORT:
            return True
        before = low[i - 1] if i else " "
        esc = i >= 2 and low[i - 2] == "\\" and before in "ntr\""
        after = low[i + len(word)] if i + len(word) < len(low) else " "
        if (not before.isalnum() or esc) and not after.isalnum():
            return True
    return False


def words(arms: list[str]) -> list[str]:
    """Every banned form for the pass's arms and every configured arm (a file may name a method this pass did not
    run). `control` is an ordinary English word and is not banned."""
    configured = [f.stem for f in config.ARMS_DIR.glob("*.toml")]
    return sorted({f for a in {*arms, *configured} for w in anonymise.banned_words(a) for f in forms(w)
                   if f and f != "control"} | set(EXTRA_WORDS))


def check(anon: Path, arms: list[str]) -> list[tuple[str, str]]:
    """(path relative to `anon`, word) for every banned word found in a file's relative path or its contents (read
    as UTF-8 with replacement, so a binary is searched too). Sorted; empty means clean."""
    ws = words(arms)
    out: set[tuple[str, str]] = set()
    for f in sorted(anon.rglob("*")):
        if f.is_symlink() or not f.is_file():
            continue
        rel = f.relative_to(anon).as_posix()
        low = rel.lower() + "\n" + f.read_bytes().decode("utf-8", errors="replace").lower()
        out.update((rel, w) for w in ws if hits(low, w))
    return sorted(out)


# ---- text the owner reads blind (the rating sheet, its context) ----------------------------------------------------
# An arm's letter tells the owner which route belongs to which arm, so they could follow one arm from topic to topic
# (the 2026-10-09 sheet had ~25: "A pins ruamel", "C fixed chained includes", "C and F: a total deadline"). The
# article "A" is English, so for it only a following word that reads as an arm's action counts; "(B)" and "option B"
# are an option's own name, not an arm.
_A_VERBS = ("and", "or", "also", "first", "then", "later", "only", "pins", "reworked", "fixed", "started", "added",
            "dropped", "kept", "took", "chose", "uses", "used", "refuses", "refused", "re-renders", "copies", "was",
            "had", "has", "did", "does", "checks", "writes", "wrote")


def label_refs(text: str, labels: list[str]) -> list[str]:
    """The places in `text` that name one of `labels` ("Arm A".."Arm F"): "Arm C", or the bare letter used as an
    arm's name. Each hit is returned with a little context; empty means clean."""
    letters = sorted({l.split()[-1] for l in labels if re.fullmatch(r"Arm [A-Z]", l)})
    if not letters:
        return []
    others = "".join(x for x in letters if x != "A")
    pats = [r"\bArms?\s+[A-Z](?:\s*(?:,|and|or|&)\s*[A-Z])*\b"]
    if others:
        pats.append(rf"(?<![\w./'-])(?<!option )(?<!Option )[{others}](?![\w./')-])")
    if "A" in letters:
        pats.append(rf"(?<![\w./'-])A(?=:|\s+(?:{'|'.join(map(re.escape, _A_VERBS))})\b)")
    out = []
    for m in re.finditer("|".join(f"(?:{p})" for p in pats), text):
        out.append(text[max(0, m.start() - 20):m.end() + 20].replace("\n", " "))
    return out


def check_text(text: str, arms: list[str], labels: list[str]) -> list[str]:
    """Every banned arm word (as `check`) and every label reference in `text`: a line each, empty means clean."""
    low = text.lower()
    return ([f"arm word {w!r}" for w in words(arms) if hits(low, w)]
            + [f"arm label: …{c}…" for c in label_refs(text, labels)])
