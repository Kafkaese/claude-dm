#!/usr/bin/env python3
"""PreToolUse hook: every subagent call must wait for its result (run_in_background: false),
and gm-screen is blocked in play.py mode (CLAUDE_DM_MODE=play), where tool calls are hidden anyway.

Background agents show their work in the UI, and their late replies arrive when nobody is
waiting for them. Exit code 2 blocks the call and tells Claude how to retry.
"""
import json
import os
import sys

event = json.load(sys.stdin)
if event.get("tool_name") in ("Agent", "Task"):
    if os.environ.get("CLAUDE_DM_MODE") == "play" and event.get("tool_input", {}).get("subagent_type") == "gm-screen":
        print("Blocked: in play.py mode the player can't see tool calls, so don't use gm-screen. "
              "Do this yourself: roll with scripts/roll.py, use `scripts/combat.py do ...`, and read or "
              "write dm/ files directly (see .claude/agents/gm-screen.md for the task steps).", file=sys.stderr)
        sys.exit(2)
    if event.get("tool_input", {}).get("run_in_background") is not False:
        print("Blocked: in this project every agent call must wait for its result. "
              "Retry the same call with run_in_background: false.", file=sys.stderr)
        sys.exit(2)
