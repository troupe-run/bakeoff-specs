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
import json, os, sys, time, uuid
from pathlib import Path

def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default

def emit(**o):
    print(json.dumps(o), flush=True)

def parse_directives(prompt):
    return dict(l[5:].split("=", 1) if "=" in l else (l[5:], "1") for l in prompt.splitlines() if l.startswith("FAKE:"))

def respond(prompt, directives):
    """The reply text for this turn. Directives win for every role (M8); Task 24's role layer goes after this."""
    if directives:
        if "ls_inbox" in directives:
            return " ".join(sorted(os.listdir("/inbox")))
        return directives.get("reply", "OK")
    return "OK"

def main():
    if "--version" in sys.argv:
        print("2.1.281 (Claude Code)"); return 0
    if "--model" not in sys.argv:
        # Controller ruling: the runner always passes the pinned model; a missing --model is a runner bug,
        # so the fake refuses rather than silently standing in for Claude Code's default.
        sys.stderr.write("fake claude: --model is required (the runner must pass the pinned model)\n")
        return 2
    prompt = arg("-p", "")
    fd = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR")
    token = os.read(int(fd), 4096).decode() if fd else ""
    model = arg("--model")
    sid = arg("--resume") or str(uuid.uuid4())
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
    text = respond(prompt, directives)
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

sys.exit(main())
