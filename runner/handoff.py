"""Step handoffs: what each arm is sent. The text is the brief verbatim, then each contract section it names
verbatim, then one delivery sentence (`scenario.toml [messages] delivery`) — byte-identical for every arm at
every step (review F-1, OD4). The only per-arm part is the method's entry wrapper (`entry_message`, OD5)."""
from __future__ import annotations
import re, tomllib
from runner import config
from runner.config import Arm

_SCEN = tomllib.loads((config.CONFIG_DIR / "scenario.toml").read_text())
MESSAGES: dict[str, str] = _SCEN["messages"]
STEP5: dict = _SCEN["step5"]
STEP6: dict[str, str] = _SCEN["step6"]

_LAST = re.compile(r"^Contract sections (in force|added): (.+)\.\s*$", re.M)
_FROM = re.compile(r"\(from step (\d)")
_ONLY = re.compile(r"\(step 1 and 2\)")
_CRB = re.compile(r"\(from step 5, change request B\)")   # sections CR-B introduces (step 5, OD6 B)


def norm(name: str) -> str:
    return name.replace("`", "").split("(")[0].strip()


def contract_sections(text: str) -> dict[str, str]:
    parts = re.split(r"(?m)^(?=## )", text)
    return {norm(p.splitlines()[0][3:]): p.rstrip("\n") for p in parts if p.startswith("## ")}


def named(brief: str) -> tuple[str, list[str]]:
    """Every section named by the brief's `Contract sections …` line(s), in order. Step 5 has one line per change
    request (Overrides under CR-A, In-include under CR-B), so CR-B's answer is not handed over with CR-A."""
    ms = list(_LAST.finditer(brief))
    return ms[-1].group(1), [n.strip() for m in ms for n in m.group(2).split(";")]


def _sections(brief: str, contract: str) -> str:
    secs = contract_sections(contract)
    return "\n\n".join(secs[norm(n)] for n in named(brief)[1])


def _deliver(body: str) -> str:
    return f"{body.rstrip()}\n\n---\n\n{MESSAGES['delivery']}\n"


def compose(step: int, brief: str, contract: str) -> str:
    return _deliver(f"{brief.rstrip()}\n\n---\n\n{_sections(brief, contract)}")


def step5(brief: str, contract: str) -> list[str]:
    """OD6: "one-message" (A) = the whole brief as one handoff; "two-requests" (B) = CR-A with the Overrides
    section first, then CR-B with the In-include section, sent at `STEP5["cr_b_after_turn"]`."""
    if STEP5["delivery"] == "one-message":
        return [compose(5, brief, contract)]
    parts = re.split(r"(?m)^(?=## )", brief)
    cr_a = next(p for p in parts if p.startswith("## CR-A")).rstrip()   # each part ends with its own contract line
    cr_b = next(p for p in parts if p.startswith("## CR-B")).rstrip()
    first = _deliver(f"{STEP5['title_a']}\n\n{cr_a}\n\n---\n\n{_sections(cr_a, contract)}")
    second = _deliver(f"{STEP5['cr_b_intro']}\n\n{cr_b}\n\n---\n\n{_sections(cr_b, contract)}")
    return [first, second]


def issue_body(brief: str) -> str:
    return _LAST.sub("", brief).rstrip() + "\n"


def bug_message(ref: str, contract: str) -> str:
    return _deliver(f"A bug has been reported in our tracker: {ref}. Please handle it.\n\n"
                    f"Contract sections added: Aliases.\n\n---\n\n{contract_sections(contract)['Aliases']}")


def in_force(step: int, contract: str, after_crb: bool = False) -> str:
    """Every contract section in force at `step` (for the PO). At step 5 a CR-B section (In-include) is in force
    only once CR-B has been delivered to the arm (`after_crb`, from drive state); the default is the
    conservative view, so the PO cannot pre-announce CR-B's answer while the arm works on CR-A."""
    keep = []
    for sec in contract_sections(contract).values():
        head = sec.splitlines()[0]
        m = _FROM.search(head)          # checked first: the step-3 heading also quotes "(step 1 and 2)"
        ok = int(m.group(1)) <= step if m else bool(_ONLY.search(head)) and step <= 2
        if ok and step == 5 and _CRB.search(head) and not after_crb:
            ok = False
        if ok:
            keep.append(sec)
    return "\n\n".join(keep) + "\n"


def entry_message(arm: Arm, step: int, text: str) -> str:
    # str.replace, never format: handoff text contains braces (YAML, JSON Schema).
    return (arm.bug_entry if step == 6 else arm.entry).replace("{handoff}", text)
