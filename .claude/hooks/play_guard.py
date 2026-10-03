#!/usr/bin/env python3
"""PreToolUse hook: during play (CLAUDE_DM_MODE=play, i.e. the web interface), the DM never edits the
combat state files or the game scripts by hand.

Hand edits skip the combat log, the undo snapshot and the rule checks, and a script edit can't be
tested from inside a session. Corrections go through the combat tools (combat_undo, combat_hp,
combat_condition); a suspected script bug is raised with the player out of character.
Exit code 2 blocks the call and tells Claude why.
"""
import json
import os
import re
import sys

event = json.load(sys.stdin)
if os.environ.get("CLAUDE_DM_MODE") == "play" and event.get("tool_name") in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
    path = str(event.get("tool_input", {}).get("file_path") or event.get("tool_input", {}).get("notebook_path") or "")
    norm = path.replace("\\", "/")
    if re.search(r"/dm/combat/[^/]+\.json$", norm):
        print("Blocked: the combat state only changes through the combat tools, so the log and undo stay right. "
              "Use combat_undo for the player's last command, or combat_hp / combat_condition / combat_act --override "
              "to fix a specific thing.", file=sys.stderr)
        sys.exit(2)
    if re.search(r"/scripts/[^/]+\.py$|/(dm_engine|web|play)\.py$|/\.claude/", norm):
        print("Blocked: the game's code and settings aren't edited during play (it can't be tested from here). "
              "If you think the script is wrong, tell the player out of character, note it in the session log, "
              "and go on with the script's result or the player's ruling.", file=sys.stderr)
        sys.exit(2)
