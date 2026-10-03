#!/usr/bin/env python3
"""PreToolUse hook: every subagent call must wait for its result (run_in_background: false).

Background agents show their work in the UI, and their late replies arrive when nobody is
waiting for them. Exit code 2 blocks the call and tells Claude how to retry.
"""
import json
import sys

event = json.load(sys.stdin)
if event.get("tool_name") in ("Agent", "Task"):
    if event.get("tool_input", {}).get("run_in_background") is not False:
        print("Blocked: in this project every agent call must wait for its result. "
              "Retry the same call with run_in_background: false.", file=sys.stderr)
        sys.exit(2)
