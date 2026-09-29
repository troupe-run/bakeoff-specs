#!/usr/bin/env python3
# runner/images/dryrun/fake_claude.py — installed as /usr/local/bin/claude in bakeoff-arm-dryrun.
# Speaks just enough of Claude Code 2.1.281's CLI: -p PROMPT, --model, --resume, --output-format stream-json.
# Directives in the prompt (lines starting "FAKE:") drive failure modes for the runner's own tests.
#
# Directive precedence (preflight M8 — binding on Task 24's scripted roles):
#   A prompt carrying ANY `FAKE:` directive is handled by the directive path below, for EVERY role
#   (arm, po, teammate, setup, probe). A later role layer may only script turns whose prompt carries no
#   `FAKE:` line; it must plug in at `respond()` behind the `if directives` guard, never ahead of it.
#   This keeps the runner's own session tests (test_session_docker.py) valid once roles exist.
#   A PO session's prompt is fixed ("Read /po/protocol.md ..."), so `/po/message.md` (the arm's message the PO
#   is deciding on) is appended to the prompt before directives are parsed (Task 13; test_po_docker.py).
#
# Scripted roles (Task 24, the dry run; only for a prompt with no `FAKE:` line). State lives in
# $CLAUDE_CONFIG_DIR/fake-state.json, keyed by session, so it goes wherever the runner's snapshots take the home:
#   PO        the prompt names /po/protocol.md: a protocol-v2 decision on /po/message.md, answering from /po/po-brief.md.
#   teammate  the prompt starts "You are a developer on this project making a quick change": the scripted
#             TROUPE_THEATRE edit of src/troupe_ref/cli.py; replies with that file name.
#   arm       anything else. The step comes from the message ("# Step N"; "A second change request" = 5; "A bug has
#             been reported" = 6); a resumed session keeps its step. Behaviour follows the n-th SUCCESSFUL turn of
#             the session: 1 asks (step 1) or asks for approval; 2 commits the step (step 1 copies the reference
#             from /opt/reference; every step pins src/troupe_ref/step.py's default to that step, the way a real arm
#             implements step N and no more — the arm's CLI never gets TROUPE_REF_STEP from the tester); 3+ reports
#             the step complete. `FAKE_VARIANT` (the arm config's env): "broken" pins step 2 to step 1; "edge" makes
#             the first turn of a step-1 session an API 529 and the first turn of a step-2 session commit its work,
#             leave its evidence and then hang (a turn timeout). `FAKE_SUBAGENT_MODEL` adds a subagent transcript.
# FAKE_REFERENCE_DIR and FAKE_PO_DIR are host-test overrides of /opt/reference and /po; the image never sets them.
import json, os, re, shutil, subprocess, sys, time, uuid
from pathlib import Path

REFERENCE = Path(os.environ.get("FAKE_REFERENCE_DIR", "/opt/reference"))
PO_DIR = Path(os.environ.get("FAKE_PO_DIR", "/po"))
TEAMMATE_OPENING = "You are a developer on this project making a quick change"
FLOAT_Q = "Should `config show` print floats exactly as written in the file?"
FLOAT_NEEDLE = "print floats exactly as written"
APPROVED = "Approved: consistent with the contract."
# The brief's `sed 's/…/…/'` edit, done in Python so it behaves the same with GNU and BSD sed.
THEATRE_OLD = 'sp.add_argument("--theatre", default=".")'
THEATRE_NEW = 'sp.add_argument("--theatre", default=__import__("os").environ.get("TROUPE_THEATRE") or ".")'
EDGE_SLEEP = float(os.environ.get("FAKE_EDGE_SLEEP", "120"))

def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default

def emit(**o):
    print(json.dumps(o), flush=True)

def parse_directives(prompt):
    return dict(l[5:].split("=", 1) if "=" in l else (l[5:], "1") for l in prompt.splitlines() if l.startswith("FAKE:"))

# ---- roles (pure parts) ----------------------------------------------------------------------------------------

def role_of(prompt):
    if "/po/protocol.md" in prompt:
        return "po"
    if prompt.lstrip().startswith(TEAMMATE_OPENING):
        return "teammate"
    return "arm"

def step_of(message):
    m = re.search(r"(?m)^# Step (\d)\b", message)
    if m:
        return int(m.group(1))
    if "A second change request" in message:
        return 5
    if "A bug has been reported" in message:
        return 6
    return None

def _escalated_answer(brief, needle):
    """The brief's escalated answer to a question containing `needle`, or None."""
    part = brief.split("## Escalated answers", 1)
    if len(part) < 2:
        return None
    for m in re.finditer(r"(?m)^- \*\*Q:\*\* (.*?) \*\*A:\*\* (.*?)(?: _\([^()]*\)_)?\s*$", part[1]):
        if needle in m.group(1).lower():
            return m.group(2).strip()
    return None

def po_decision(message, brief):
    base = {"kind": "continue", "answers": [], "reply": "Please continue.", "approved": None, "command": None,
            "arguments": "", "significant": False}
    low = message.lower()
    if FLOAT_NEEDLE in low:
        known = _escalated_answer(brief, FLOAT_NEEDLE)
        entry = ({"question": FLOAT_Q, "reply": known, "escalate": False, "cited": "Escalated answers"} if known else
                 {"question": FLOAT_Q, "reply": None, "escalate": True, "cited": None})
        return {**base, "kind": "question", "answers": [entry], "reply": None, "significant": not known}
    if "do you approve" in low:
        return {**base, "kind": "approval", "reply": APPROVED, "approved": True}
    m = re.search(r"run (/[\w.:-]+)\s*$", message.strip())
    if m:
        return {**base, "kind": "next_command", "reply": None, "command": m.group(1)}
    if "is complete" in low:
        return {**base, "kind": "step_done", "reply": None}
    return base

# ---- roles (effects) --------------------------------------------------------------------------------------------

def _state_file():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", "/tmp")) / "fake-state.json"

def load_state():
    f = _state_file()
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return {"sessions": {}}

def save_state(st):
    f = _state_file(); f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(st)); os.replace(tmp, f)

def _git(*a):
    subprocess.run(["git", "-c", "safe.directory=*", *a], check=True, capture_output=True)

STEP_LINE = re.compile(r'(?m)^STEP = .*$')

def commit_step(n, variant):
    """The arm's work for step n, committed on the current branch (main)."""
    if n == 1:
        for name in ("pyproject.toml", "uv.lock"):
            shutil.copy2(REFERENCE / name, name)
        for name in ("src", "tests"):
            shutil.rmtree(name, ignore_errors=True)
            shutil.copytree(REFERENCE / name, name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    line = f'STEP = int(os.environ.get("TROUPE_REF_STEP", "{n}"))'
    if variant == "broken" and n == 2:
        line = 'STEP = min(int(os.environ.get("TROUPE_REF_STEP", "7")), 1)'
    f = Path("src/troupe_ref/step.py")
    if f.exists():
        f.write_text(STEP_LINE.sub(line, f.read_text(), count=1))
    _git("add", "-A")
    _git("commit", "-q", "--allow-empty", "-m", f"Step {n}")

def arm_turn(sid, message):
    """(text, special) for an arm turn; special is None, "529" or "hang" (edge variant)."""
    variant = os.environ.get("FAKE_VARIANT", "")
    st = load_state()
    s = st["sessions"].setdefault(sid, {"step": step_of(message) or 1, "ok_turns": 0, "errored": False})
    if variant == "edge" and s["step"] == 1 and s["ok_turns"] == 0 and not s["errored"]:
        s["errored"] = True; save_state(st)
        return "API Error: 529 overloaded", "529"
    if variant == "edge" and s["step"] == 2 and s["ok_turns"] == 0 and not s.get("hung"):
        commit_step(2, variant)                  # the work lands, then the turn never ends (a turn timeout)
        s["hung"] = True; save_state(st)
        return "Implementing step 2 as briefed.", "hang"
    s["ok_turns"] += 1
    k, n = s["ok_turns"], s["step"]
    save_state(st)
    if k == 1:
        return (f"Before I start: s{FLOAT_Q[1:]}" if n == 1 else f"Plan: implement step {n} as briefed. Do you approve?"), None
    if k == 2:
        commit_step(n, variant)
        return ("Done with the core; next, run /dry-next" if n == 3 else f"Step {n} is complete."), None
    lead = message.strip().split()[0] if message.strip() else ""
    if lead == "/dry-next":
        return "Step 3 is complete.", None
    if lead == "/dry-close":
        return f"Closed. Step {n} is complete.", None
    return f"Step {n} is complete.", None

def teammate_turn():
    f = Path("src/troupe_ref/cli.py")
    if f.exists():
        f.write_text(f.read_text().replace(THEATRE_OLD, THEATRE_NEW))
    return "src/troupe_ref/cli.py"

def respond(prompt, directives, sid, role):
    """(reply text, special). Directives win for every role (M8); the role layer comes after them."""
    if directives:
        if "ls_inbox" in directives:
            return " ".join(sorted(os.listdir("/inbox"))), None
        return directives.get("reply", "OK"), None
    if role == "po":
        msg = (PO_DIR / "message.md").read_text() if (PO_DIR / "message.md").exists() else ""
        brief = (PO_DIR / "po-brief.md").read_text() if (PO_DIR / "po-brief.md").exists() else ""
        return json.dumps(po_decision(msg, brief)), None
    if role == "teammate":
        return teammate_turn(), None
    return arm_turn(sid, prompt)

def main():
    if "--version" in sys.argv:
        print("2.1.281 (Claude Code)"); return 0
    if "--model" not in sys.argv:
        # Controller ruling: the runner always passes the pinned model; a missing --model is a runner bug,
        # so the fake refuses rather than silently standing in for Claude Code's default.
        sys.stderr.write("fake claude: --model is required (the runner must pass the pinned model)\n")
        return 2
    prompt = arg("-p", "")
    role = role_of(prompt)
    fd = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR")
    token = os.read(int(fd), 4096).decode() if fd else ""
    model = arg("--model")
    sid = arg("--resume") or str(uuid.uuid4())
    po_message = PO_DIR / "message.md"         # Task 13: a PO session's directives come from the arm's message
    if po_message.exists():
        prompt += "\n" + po_message.read_text()
    directives = parse_directives(prompt)
    emit(type="system", subtype="init", session_id=sid, model=directives.get("init_model", model),
         claude_code_version=directives.get("cc_version", "2.1.281"),
         tools=["Bash", "Read", "Edit", "Write", "Task"], cwd=os.getcwd())
    if "stderr" in directives:
        sys.stderr.write("e" * int(directives["stderr"])); sys.stderr.flush()
    if "not_logged_in" in directives:  # the no-token shape, verbatim from spike FINDINGS Evidence 2
        emit(type="result", subtype="success", is_error=True, result="Not logged in · Please run /login",
             session_id=sid, total_cost_usd=0, num_turns=1, duration_api_ms=0)
        return 1
    if "auth_fail" in directives:
        emit(type="system", subtype="api_retry", attempt=1, max_retries=4, error="authentication_failed")
        time.sleep(3600)
    if "sh" in directives:            # a shell command in the session's cwd: a scripted edit (Task 16's teammate)
        subprocess.run(directives["sh"], shell=True, check=False)
    text, special = respond(prompt, directives, sid, role)
    if "bigline" in directives:
        emit(type="assistant", session_id=sid, message={"model": model, "content": [{"type": "text", "text": "x" * int(directives["bigline"])}]})
    # Transcript, where Claude Code keeps it (probe P1 verifies): $CLAUDE_CONFIG_DIR/projects/<cwd slug>/<session>.jsonl
    proj = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / os.getcwd().replace("/", "-")
    proj.mkdir(parents=True, exist_ok=True)
    msg = {"type": "assistant", "sessionId": sid,
           "message": {"model": directives.get("model", model), "content": [{"type": "text", "text": text}]}}
    with open(proj / f"{sid}.jsonl", "a") as fh:
        fh.write(json.dumps({"type": "user", "sessionId": sid, "message": {"content": prompt}}) + "\n")
        fh.write(json.dumps(msg) + "\n")
    sub_model = directives.get("subagent_model") or os.environ.get("FAKE_SUBAGENT_MODEL")
    if sub_model:
        sub = proj / sid / "subagents"; sub.mkdir(parents=True, exist_ok=True)
        with open(sub / "agent-1.jsonl", "a") as fh:
            fh.write(json.dumps({"type": "assistant", "message": {"model": sub_model, "content": []}}) + "\n")
    if "sleep" in directives:          # after the transcript is written, as Claude Code writes as it goes
        time.sleep(float(directives["sleep"]))
    if "persist_token" in directives:
        (Path(os.environ["CLAUDE_CONFIG_DIR"]) / ".credentials.json").write_text(json.dumps({"t": token.strip()}))
    emit(type="assistant", session_id=sid, message=msg["message"])
    if special == "hang":              # edge: the evidence is out, the turn never finishes (runner: turn timeout)
        time.sleep(EDGE_SLEEP)
        return 0
    if special == "529":               # edge: a transient API error (review C-4), retried in place by the runner
        emit(type="result", subtype="success", is_error=True, result=text, session_id=sid, total_cost_usd=0.0,
             usage={"input_tokens": 1, "output_tokens": 1}, modelUsage={model: {"inputTokens": 1, "outputTokens": 1}})
        return 1
    if "no_result" in directives:
        return 0
    if "api_error" in directives:
        emit(type="result", subtype="success", is_error=True, result=directives["api_error"], session_id=sid)
        return 1
    emit(type="result", subtype="success", is_error="is_error" in directives, result=text, session_id=sid,
         total_cost_usd=0.0, usage={"input_tokens": 1, "output_tokens": 1},
         modelUsage={directives.get("model", model): {"inputTokens": 1, "outputTokens": 1}},
         permission_denials=[], token_seen=bool(token.strip()), model_arg=model)
    return 0

if __name__ == "__main__":
    sys.exit(main())
