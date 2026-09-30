# Live probe

PAT copies: every PAT file the probe installed was removed at the end (15 file(s)).

## P1
```json
{
  "outcome": "ok",
  "session_id": "fe8a40e9-0fa9-4f2a-bfc6-4744ad59449a",
  "final_text": "ok",
  "cost_usd": 0.0376834,
  "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-001.stream.jsonl.gz",
  "init_model": "claude-opus-5-5",
  "transcript_models": [
    "claude-opus-5-5"
  ],
  "accepted_models_should_be": [
    "claude-opus-5-5"
  ],
  "layout": {
    "expected": "projects/-work-bakeoff-specs-control/fe8a40e9-0fa9-4f2a-bfc6-4744ad59449a.jsonl",
    "found": true
  },
  "found_at": [
    "projects/-work-bakeoff-specs-control/fe8a40e9-0fa9-4f2a-bfc6-4744ad59449a.jsonl"
  ],
  "stream_saved": {
    "saved": true,
    "path": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/results/probe/P1-stream.jsonl.gz"
  },
  "transcripts_published": {
    "copied": [
      "-work-bakeoff-specs-control/fe8a40e9-0fa9-4f2a-bfc6-4744ad59449a.jsonl.gz"
    ],
    "withheld": []
  },
  "auth_failures": {
    "no_credential": {
      "outcome": "auth_failed",
      "final_text": "Not logged in \u00b7 Please run /login",
      "retry_errors": [],
      "api_retry_events": [],
      "last_event": {
        "duration_api_ms": 0,
        "stop_reason": "stop_sequence",
        "session_id": "8d3a0427-83f3-4b17-9aac-0bf0d0ee534b",
        "total_cost_usd": 0,
        "usage": {
          "output_tokens_details": {
            "thinking_tokens": 0
          },
          "input_tokens": 0,
          "cache_creation_input_tokens": 0,
          "cache_read_input_tokens": 0,
          "output_tokens": 0,
          "server_tool_use": {
            "web_search_requests": 0,
            "web_fetch_requests": 0
          },
          "service_tier": "standard",
          "cache_creation": {
            "ephemeral_1h_input_tokens": 0,
            "ephemeral_5m_input_tokens": 0
          },
          "inference_geo": "",
          "iterations": [],
          "speed": "standard"
        },
        "modelUsage": {},
        "permission_denials": [],
        "terminal_reason": "api_error",
        "fast_mode_state": "off",
        "fast_mode_disabled_reason": "sdk_opt_in_required",
        "subagent_stats": {
          "spawned": 0,
          "requested": {
            "background": 0,
            "foreground": 0,
            "unset": 0
          },
          "started_in_background": 0,
          "max_depth": 0,
          "spawned_by_subagents": 0,
          "completed": 0,
          "failed": 0,
          "killed": {
            "parent": 0,
            "user": 0,
            "system": 0
          },
          "refused": {
            "depth_limit": 0,
            "concurrency_limit": 0,
            "budget": 0
          },
          "by_type": {}
        },
        "is_error": true,
        "num_turns": 1,
        "subtype": "success",
        "api_error_status": null,
        "result": "Not logged in \u00b7 Please run /login",
        "type": "result",
        "duration_ms": 72,
        "uuid": "ba439c05-3a65-49f1-a459-37b40401dba5",
        "queued_turn_count": 0,
        "result_index": 0
      },
      "stderr_tail": "",
      "shape": "Not logged in",
      "matches_shape": true
    },
    "bogus_token": {
      "outcome": "auth_failed",
      "final_text": "",
      "retry_errors": [
        "authentication_failed"
      ],
      "api_retry_events": [
        {
          "type": "system",
          "subtype": "api_retry",
          "attempt": 1,
          "max_retries": 4,
          "retry_delay_ms": 557,
          "error_status": 401,
          "error": "authentication_failed",
          "session_id": "86230a44-7984-4647-9aa9-4af9d2dc1e70",
          "uuid": "097eca63-734d-47e3-b609-763de79f796c"
        }
      ],
      "last_event": {
        "type": "system",
        "subtype": "api_retry",
        "attempt": 1,
        "max_retries": 4,
        "retry_delay_ms": 557,
        "error_status": 401,
        "error": "authentication_failed",
        "session_id": "86230a44-7984-4647-9aa
```
## P10
```json
{
  "config_dirs": {
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/home/.claude": {
      "files_with_token": [],
      "scan_findings": ""
    },
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/superpowers/home/.claude": {
      "files_with_token": [],
      "scan_findings": ""
    }
  },
  "results_scan": "pending: `runner probe` scans results/probe* after both halves"
}
```
## P11
```json
{
  "route": "unknown",
  "skill": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe/speckit/work/bakeoff-specs-speckit/.claude/skills/speckit-taskstoissues/SKILL.md"
}
```
## P2
```json
{
  "outcome": "ok",
  "session_id": "fe8a40e9-0fa9-4f2a-bfc6-4744ad59449a",
  "final_text": "I replied with \"ok\".",
  "cost_usd": 0.0699072,
  "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-002.stream.jsonl.gz",
  "ok": true
}
```
## P3
```json
{
  "outcome": "ok",
  "session_id": "44cba6d9-3017-4cf7-9b77-e7c44154d9b2",
  "final_text": "I started the subagent on the haiku model with the Agent tool, which is what this environment calls the Task tool. It replied: **sub-ok**",
  "cost_usd": 0.08968340000000001,
  "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-003.stream.jsonl.gz",
  "subagent_files": [
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/P3/-work-bakeoff-specs-control/44cba6d9-3017-4cf7-9b77-e7c44154d9b2/subagents/agent-ad056e0a0472fa314.jsonl.gz"
  ],
  "subagent_models": [
    "claude-opus-5-5"
  ],
  "pinned": true,
  "pin_report": {
    "ok": true,
    "assistant_messages": 3,
    "stream_assistant_messages": 2,
    "synthetic": 0,
    "truncated_lines": 0,
    "claude_code_versions": [
      "2.1.281"
    ],
    "no_evidence": false,
    "violations": [],
    "unverified_streams": []
  },
  "transcripts_published": {
    "copied": [
      "-work-bakeoff-specs-control/44cba6d9-3017-4cf7-9b77-e7c44154d9b2.jsonl.gz",
      "-work-bakeoff-specs-control/44cba6d9-3017-4cf7-9b77-e7c44154d9b2/subagents/agent-ad056e0a0472fa314.jsonl.gz"
    ],
    "withheld": []
  }
}
```
## P3b
```json
{
  "outcome": "ok",
  "session_id": "39a46dcc-b123-4b1a-96f1-2b68dbc2394c",
  "final_text": "The cheap agent replied: **\"cheap-ok.\"**",
  "cost_usd": 0.055732000000000004,
  "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-004.stream.jsonl.gz",
  "subagent_models": [
    "claude-haiku-4-5-20251001"
  ],
  "full_id_escaped_remap": true,
  "pin_report": {
    "ok": false,
    "assistant_messages": 4,
    "stream_assistant_messages": 2,
    "synthetic": 0,
    "truncated_lines": 0,
    "claude_code_versions": [
      "2.1.281"
    ],
    "no_evidence": false,
    "violations": [
      {
        "file": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/P3b/-work-bakeoff-specs-control/39a46dcc-b123-4b1a-96f1-2b68dbc2394c/subagents/agent-a6e29cf39c7d909ef.jsonl.gz",
        "line": 10,
        "where": "assistant",
        "model": "claude-haiku-4-5-20251001"
      },
      {
        "file": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/P3b/-work-bakeoff-specs-control/39a46dcc-b123-4b1a-96f1-2b68dbc2394c/subagents/agent-a6e29cf39c7d909ef.jsonl.gz",
        "line": 11,
        "where": "assistant",
        "model": "claude-haiku-4-5-20251001"
      },
      {
        "file": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-004.stream.jsonl.gz",
        "line": 10,
        "where": "result.modelUsage",
        "model": "claude-haiku-4-5"
      }
    ],
    "unverified_streams": []
  },
  "transcripts_published": {
    "copied": [
      "-work-bakeoff-specs-control/39a46dcc-b123-4b1a-96f1-2b68dbc2394c.jsonl.gz",
      "-work-bakeoff-specs-control/39a46dcc-b123-4b1a-96f1-2b68dbc2394c/subagents/agent-a6e29cf39c7d909ef.jsonl.gz"
    ],
    "withheld": []
  },
  "note": "a violation here confirms full IDs escape the alias remap (OD2, F-6)"
}
```
## P4
```json
{
  "outcome": "ok",
  "session_id": "9ddb0adb-ef6c-4713-8ed2-e6e266ebca2b",
  "final_text": "I can't use the AskUserQuestion tool here. It isn't among my available tools, and searching the deferred tools didn't find it either.\n\nSo I'll ask directly: **red or blue?**",
  "cost_usd": 0.039437,
  "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-005.stream.jsonl.gz",
  "permission_denials": [],
  "disallowed": [
    "WebSearch",
    "WebFetch",
    "AskUserQuestion"
  ]
}
```
## P5
```json
{
  "route": "plugin-dir",
  "bmad": "parked",
  "superpowers": {
    "subdirs": {
      "superpowers": ""
    },
    "route_a": {
      "ok": true,
      "commands": {
        "claude plugin marketplace add anthropics/claude-plugins-official": {
          "exit": 0,
          "seconds": 3.6,
          "output": "Adding marketplace\u2026SSH not configured, cloning via HTTPS: https://github.com/anthropics/claude-plugins-official.git\nRefreshing marketplace cache (timeout: 120s)\u2026\nCloning repository (timeout: 120s): https://github.com/anthropics/claude-plugins-official.git\nClone complete, validating marketplace\u2026\nCleaning up old marketplace cache\u2026\n\u2714 Successfully added marketplace: claude-plugins-official (declared in user settings)\n"
        },
        "claude plugin install superpowers@claude-plugins-official": {
          "exit": 0,
          "seconds": 4.0,
          "output": "Installing plugin \"superpowers@claude-plugins-official\"...\u2714 Successfully installed plugin: superpowers@claude-plugins-official (scope: user)\n"
        }
      }
    },
    "route_b": {
      "outcome": "ok",
      "session_id": "061d727d-bb72-495a-915b-93ec5b550bc5",
      "final_text": "- superpowers:brainstorming\n- superpowers:diagnosing-superpowers\n- superpowers:dispatching-parallel-agents\n- superpowers:executing-plans\n- superpowers:finishing-a-development-branch\n- superpowers:receiving-code-review\n- superpowers:requesting-code-review\n- superpowers:subagent-driven-development\n- superpowers:systematic-debugging\n- superpowers:test-driven-development\n- superpowers:using-git-worktrees\n- superpowers:using-superpowers\n- superpowers:verification-before-completion\n- superpowers:writing-plans\n- superpowers:writing-skills\n- dataviz\n- update-config\n- keybindings-help\n- code-review\n- simplify\n- fewer-permission-prompts\n- loop\n- schedule\n- claude-api\n- workflow-authoring\n- run\n- init\n- security-review",
      "cost_usd": 0.054807800000000004,
      "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/superpowers/evidence/turns/probe-a1-020.stream.jsonl.gz",
      "plugin_dirs": "/opt/plugins/superpowers",
      "loaded": {
        "superpowers": true
      },
      "init_plugins": [
        {
          "name": "superpowers",
          "path": "/opt/plugins/superpowers",
          "source": "superpowers@inline",
          "version": "6.4.2"
        },
        {
          "name": "agents-md",
          "path": "builtin",
          "source": "agents-md@builtin"
        }
      ],
      "init_skills": [
        "deep-research",
        "superpowers:brainstorming",
        "superpowers:diagnosing-superpowers",
        "superpowers:dispatching-parallel-agents",
        "superpowers:executing-plans",
        "superpowers:finishing-a-development-branch",
        "superpowers:receiving-code-review",
        "superpowers:requesting-code-review",
        "superpowers:subagent-driven-development",
        "superpowers:systematic-debugging",
        "superpowers:test-driven-development",
        "superpowers:using-git-worktrees",
        "superpowers:using-superpowers",
        "superpowers:verification-before-completion",
        "superpowers:writing-plans",
        "superpowers:writing-skills",
        "dataviz",
        "update-config",
        "verify",
        "debug",
        "code-review",
        "simplify",
        "batch",
        "fewer-permission-prompts",
        "doctor",
        "loop",
        "schedule",
        "claude-api",
        "workflow-authoring",
        "run",
        "run-skill-generator"
      ],
      "init_slash_commands": [
        "deep-research",
        "superpowers:brainstorming",
        "superpowers:diagnosing-superpowers",
        "superpowers:dispatching-parallel-agents",
        "superpowers:executing-plans",
        "superpowers:finishing-a-development-branch",
        "superpowers:receiving-code-review",
        "superpowers:requesting-code-review",
```
## P6
```json
{
  "command": true,
  "skill_as_slash": true,
  "command_turn": {
    "outcome": "ok",
    "session_id": "e81c2a01-ccda-4782-a39f-8aed6beb3ad7",
    "final_text": "hello-ok",
    "cost_usd": 0.0319518,
    "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-006.stream.jsonl.gz"
  },
  "skill_turn": {
    "outcome": "ok",
    "session_id": "75d99482-3bac-4d97-ba28-eed92310c714",
    "final_text": "greet-ok",
    "cost_usd": 0.0322158,
    "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-007.stream.jsonl.gz"
  }
}
```
## P7
```json
{
  "control_not_isolated": {
    "outcome": "ok",
    "session_id": "4cae3b78-fea8-4cc5-88dd-355ec1c681b0",
    "final_text": "PINEAPPLE",
    "cost_usd": 0.0331158,
    "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-008.stream.jsonl.gz",
    "said_pineapple": true
  },
  "setting_sources_empty": {
    "outcome": "ok",
    "session_id": "eef18734-436b-40b3-ae51-c42b021c7ecb",
    "final_text": "Hi! What do you want to work on in `bakeoff-specs-control`?",
    "cost_usd": 0.0107586,
    "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-009.stream.jsonl.gz",
    "init_tools": [
      "Glob",
      "Grep",
      "Read"
    ],
    "tools": {
      "missing": [],
      "extra": [],
      "disallowed_present": [],
      "confirmed": true
    },
    "said_pineapple": false
  },
  "po": {
    "outcome": "ok",
    "session_id": "60ccebfb-f282-43a4-b092-338d0c0b3c5f",
    "final_text": "Hi! What are you working on today?",
    "cost_usd": 0.0010874,
    "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-010.stream.jsonl.gz",
    "init_tools": [
      "Glob",
      "Grep",
      "Read"
    ],
    "said_pineapple": false,
    "env_keys": [
      "ANTHROPIC_DEFAULT_HAIKU_MODEL",
      "ANTHROPIC_DEFAULT_OPUS_MODEL",
      "ANTHROPIC_DEFAULT_SONNET_MODEL",
      "BK_DISALLOWED",
      "BK_ISOLATED",
      "BK_MODEL",
      "BK_PERMISSION_MODE",
      "BK_TOOLS",
      "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
      "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
      "CLAUDE_CODE_MAX_RETRIES",
      "CLAUDE_CODE_SAFE_MODE",
      "CLAUDE_CODE_SUBAGENT_MODEL",
      "CLAUDE_CONFIG_DIR",
      "DISABLE_AUTOUPDATER",
      "OPENSPEC_TELEMETRY"
    ]
  },
  "teammate": {
    "outcome": "ok",
    "session_id": "65d6fff9-8b10-4035-a02b-aa963d037ef8",
    "final_text": "Hi! What can I help you with?",
    "cost_usd": 0.0313518,
    "stream": "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-model/control/evidence/turns/probe-a1-011.stream.jsonl.gz",
    "init_tools": [
      "Task",
      "Bash",
      "CronCreate",
      "CronDelete",
      "CronList",
      "Edit",
      "EnterWorktree",
      "ExitWorktree",
      "ListAgents",
      "NotebookEdit",
      "Read",
      "RemoteTrigger",
      "ReportFindings",
      "ScheduleWakeup",
      "SendMessage",
      "Skill",
      "TaskStop",
      "ToolSearch",
      "Workflow",
      "Write"
    ],
    "said_pineapple": false,
    "env_keys": [
      "ANTHROPIC_DEFAULT_HAIKU_MODEL",
      "ANTHROPIC_DEFAULT_OPUS_MODEL",
      "ANTHROPIC_DEFAULT_SONNET_MODEL",
      "BK_DISALLOWED",
      "BK_ISOLATED",
      "BK_MODEL",
      "BK_PERMISSION_MODE",
      "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
      "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
      "CLAUDE_CODE_MAX_RETRIES",
      "CLAUDE_CODE_SAFE_MODE",
      "CLAUDE_CODE_SUBAGENT_MODEL",
      "CLAUDE_CONFIG_DIR",
      "DISABLE_AUTOUPDATER",
      "OPENSPEC_TELEMETRY",
      "PYTHONDONTWRITEBYTECODE"
    ]
  },
  "isolated_ignored_claude_md": true
}
```
## P8
```json
{
  "run": {
    "hosts": [
      "api.anthropic.com"
    ],
    "outside_run_common": []
  },
  "P5-run-superpowers": {
    "hosts": [
      "api.anthropic.com"
    ],
    "outside_run_common": []
  }
}
```
## P9
```json
{
  "help": {
    "bd create --help": {
      "output": "criteria\n      --allow-empty-description   Allow empty description input from stdin or file\n      --append-notes string       Append to existing notes (with newline separator)\n  -a, --assignee string           Assignee\n      --body-file string          Read description from file (use - for stdin)\n      --context string            Additional context for the issue\n      --defer string              Defer until date (issue hidden from bd ready until then). Same formats as --due\n      --deps strings              Dependencies as 'type:id' or bare 'id'. Bare 'id', 'depends-on:id', and 'blocked-by:id' all make THIS issue depend on id; 'blocks:id' reverses direction (id depends on this issue). E.g. 'blocked-by:bd-20,discovered-from:bd-15'\n  -d, --description string        Issue description\n      --design string             Design notes\n      --design-file string        Read design from file (use - for stdin)\n      --dry-run                   Preview what would be created without actually creating\n      --due string                Due date/time. Formats: +6h, +1d, +2w, tomorrow, next monday, 2025-01-15\n      --ephemeral                 Create as ephemeral (short-lived, subject to TTL compaction)\n  -e, --estimate int              Time estimate in minutes (e.g., 60 for 1 hour)\n      --event-actor string        Entity URI who caused this event (requires --type=event)\n      --event-category string     Event category (e.g., patrol.muted, agent.started) (requires --type=event)\n      --event-payload string      Event-specific JSON data (requires --type=event)\n      --event-target string       Entity URI or bead ID affected (requires --type=event)\n      --external-ref string       External reference (e.g., 'gh-9', 'jira-ABC', Linear URL)\n  -f, --file string               Create multiple issues from markdown file\n      --force                     Force creation even if prefix doesn't match database prefix\n      --graph string              Create a graph of issues with dependencies from JSON plan file\n  -h, --help                      help for create\n      --id string                 Explicit issue ID (e.g., 'bd-42' for partitioning)\n  -l, --labels strings            Labels (comma-separated)\n      --metadata string           Set custom metadata (JSON string or @file.json to read from file)\n      --mol-type string           Molecule type: swarm (multi-agent), patrol (recurring ops), work (default)\n      --no-history                Skip Dolt commit history without making GC-eligible (for permanent agent beads)\n      --no-inherit-labels         Don't inherit labels from parent issue\n      --notes string              Additional notes\n      --parent string             Parent issue ID for hierarchical child (e.g., 'bd-a3f8e9')\n  -p, --priority string           Priority (0-4 or P0-P4, 0=highest) (default \"2\")\n      --repo string               Target repository for issue (overrides auto-routing)\n      --silent                    Output only the issue ID (for scripting)\n      --skills string             Required skills for this issue\n      --spec-id string            Link to specification document\n  -s, --status string             Initial status\n      --stdin                     Read description from stdin (alias for --body-file -)\n      --storage-class string      Storage class: versioned, unversioned, or ephemeral (default: storage-class.<type> config, else versioned)\n      --title string              Issue title (alternative to positional argument)\n  -t, --type string               Issue type (bug|feature|task|epic|chore|decision|spike|story|milestone); custom types require types.custom config; aliases: enhancement/feat\u2192feature, dec/adr\u2192decision (default \"task\")\n      --validate                  Validate description contains required sections for issue type\n      --waits-for string          Spawner issue ID to wait for (creates waits-for de
```
## P9-write
```json
{
  "ccsdd": {
    "pass1": {
      "slug": "troupe-run/bakeoff-specs-ccsdd-pass1",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-ccsdd-pass1/issues/1\n",
      "may_have_open_issue": false
    },
    "disc": {
      "slug": "troupe-run/bakeoff-specs-ccsdd-pass1-disc",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-ccsdd-pass1-disc/issues/1\n",
      "may_have_open_issue": false
    }
  },
  "control": {
    "pass1": {
      "slug": "troupe-run/bakeoff-specs-control-pass1",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-control-pass1/issues/1\n",
      "may_have_open_issue": false
    },
    "disc": {
      "slug": "troupe-run/bakeoff-specs-control-pass1-disc",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-control-pass1-disc/issues/1\n",
      "may_have_open_issue": false
    }
  },
  "openspec": {
    "pass1": {
      "slug": "troupe-run/bakeoff-specs-openspec-pass1",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-openspec-pass1/issues/1\n",
      "may_have_open_issue": false
    },
    "disc": {
      "slug": "troupe-run/bakeoff-specs-openspec-pass1-disc",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-openspec-pass1-disc/issues/1\n",
      "may_have_open_issue": false
    }
  },
  "speckit": {
    "pass1": {
      "slug": "troupe-run/bakeoff-specs-speckit-pass1",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-speckit-pass1/issues/1\n",
      "may_have_open_issue": false
    },
    "disc": {
      "slug": "troupe-run/bakeoff-specs-speckit-pass1-disc",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-speckit-pass1-disc/issues/1\n",
      "may_have_open_issue": false
    }
  },
  "superpowers": {
    "pass1": {
      "slug": "troupe-run/bakeoff-specs-superpowers-pass1",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-superpowers-pass1/issues/1\n",
      "may_have_open_issue": false
    },
    "disc": {
      "slug": "troupe-run/bakeoff-specs-superpowers-pass1-disc",
      "created": 1,
      "closed": true,
      "create_output": "https://github.com/troupe-run/bakeoff-specs-superpowers-pass1-disc/issues/1\n",
      "may_have_open_issue": false
    }
  }
}
```
## PAT-cleanup
```json
{
  "removed": [
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-disc/ccsdd/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-disc/control/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-disc/openspec/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-disc/speckit/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-disc/superpowers/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-pass1/ccsdd/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-pass1/control/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-pass1/openspec/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-pass1/speckit/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe-write-pass1/superpowers/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe/ccsdd/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe/control/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe/openspec/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe/speckit/home/.config/gh/hosts.yml",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/state/probe/superpowers/home/.config/gh/hosts.yml"
  ],
  "remaining": []
}
```
## results_scan
```json
{
  "dirs": [
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/results/probe",
    "/Users/martin/Projects/troupe/bakeoff-specs.wt-t25/results/probe-offline"
  ],
  "count": 0,
  "findings": ""
}
```

## Corrections to apply (owner)

- `pins.toml accepted_models` = P1's `transcript_models` (and `init_model`).
- P1: replace the reconstructed parser fixture with `results/probe/P1-stream.jsonl.gz` (only if `stream_saved.saved`).
- P1: if `layout.found` is false, the fake's transcript layout is wrong: fix it to `found_at`.
- P1: any `hard_linked` entry: Claude Code hard-links transcripts — the transcript readers need the owner's decision.
- P1c: any case with `matches_shape` false and an outcome other than `auth_failed`: add its text's prefix (from `final_text`, `last_event`, `api_retry_events` or `stderr_tail`) to `session.AUTH_FAILURE_SHAPES` (with its source); `bogus_token_on_disk` must be empty.
- If P2.ok is false: OD19 (resume across containers) needs the owner's decision.
- If P3 shows a non-pinned subagent model: OD2 needs the owner's decision before superpowers runs.
- P3b: expected violation — confirms the setup check; no action if `common.no-foreign-model-ids` exists.
- P4: record what 2.1.281 does with a disallowed AskUserQuestion (OD11).
- P5: route A failures or `route_b.loaded` false → fix the arm's `[setup] plugins` (subdir) before it runs.
- If P6.skill_as_slash is false: `commands.invocation` must send skills as `Use the <name> skill.` instead.
- If P7.isolated_ignored_claude_md is false: stop — the PO and teammate are not isolated.
- If P7 PO or teammate said PINEAPPLE: stop — that role is not isolated.
- P7: if `control_not_isolated.said_pineapple` is false, the PINEAPPLE checks prove nothing — re-run P7.
- P8: any `outside_run_common` host: listed for the owner (allow it in pins, or leave it refused).
- P9: correct `[setup]` / checklist ids to the real flags; record telemetry per tool in each checklist OV.
- P9 offline failures: note which setups fetch at setup time (pinned by the manifest comparison only).
- P9 `manifest_not_created`: manifest paths setup never creates — owner decides (observation only).
- P9 `issues_access`: the existing read-only check's verdict (it runs `runs`), kept beside the write test.
- If any write test failed: that arm's token lacks issue write access — fix the PAT before any arm runs.
- P9-write: any repo with `may_have_open_issue` true (an uncertain create, or a close that failed or never ran): look for an open issue titled "test issue - please ignore" (number in `created` when known) and close it by hand; the tracker snapshot already ignores it.
- P10: any file listed → stop; the owner decides before any arm runs.
- P11: `mcp` → apply Task 12 Step 5 if OD24 = B; `gh` → nothing to add.
