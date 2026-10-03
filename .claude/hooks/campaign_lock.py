#!/usr/bin/env python3
"""PreToolUse hook: when the interface locks the DM to one campaign (CLAUDE_DM_CAMPAIGN), its file
tools and shell commands may only touch that campaign's folder, campaigns/_template and the
shared library, never another campaign's files. Subagents inherit the lock.

Without the variable (e.g. working on the repo in the Claude Code UI) nothing is checked.
A guard rail against crossing campaigns by mistake, not a sandbox: shell commands are checked by
the paths they name. Exit code 2 blocks the call and tells Claude why.
"""
import json
import os
import re
import sys
from pathlib import Path

CAMP = os.environ.get("CLAUDE_DM_CAMPAIGN", "").strip()
REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2]).resolve()
ROOT = REPO / "campaigns"
ALLOWED = {CAMP, "_template", "README.md"}


def block(why: str) -> None:
    print(f"Blocked: this session plays only the campaign '{CAMP}'. {why} Use campaigns/{CAMP}/ "
          f"(or the shared library/); other campaigns are off limits.", file=sys.stderr)
    sys.exit(2)


def check_path(raw: str, what: str) -> None:
    """A file or folder path the tool works on: inside campaigns/, only the allowed entries."""
    if not raw:
        return
    p = Path(raw)
    p = (p if p.is_absolute() else Path.cwd() / p).resolve()
    if p == ROOT or p == REPO and what == "search":
        block(f"{'A search over the whole repository' if p == REPO else 'The campaigns folder'} reaches other campaigns.")
    try:
        rel = p.relative_to(ROOT)
    except ValueError:
        return
    if rel.parts and rel.parts[0] not in ALLOWED:
        block(f"'{raw}' belongs to another campaign.")


def check_command(cmd: str) -> None:
    """Shell commands: every campaigns/… path they name must be allowed; no bare campaigns folder
    and no recursive search from the repository root."""
    for m in re.finditer(r"campaigns(/([^/\s'\"*]*))?", cmd):
        name = m.group(2)
        if not name:
            block("A command on the campaigns folder as a whole reaches other campaigns.")
        if name not in ALLOWED:
            block(f"'campaigns/{name}' isn't this campaign.")
    recursive = re.search(r"\b(grep|rg|egrep)\b[^|;&]*\s-[a-zA-Z]*[rR]", cmd) or re.search(r"\bfind\b", cmd)
    if recursive and "library" not in cmd and f"campaigns/{CAMP}" not in cmd:
        block("A recursive search needs a path inside this campaign or the library.")


if CAMP:
    event = json.load(sys.stdin)
    tool, inp = event.get("tool_name", ""), event.get("tool_input", {}) or {}
    if tool in ("Read", "Write", "Edit", "MultiEdit"):
        check_path(inp.get("file_path", ""), "file")
    elif tool == "NotebookEdit":
        check_path(inp.get("notebook_path", ""), "file")
    elif tool == "Glob":   # the pattern is relative to `path` (default: the repository)
        base = inp.get("path") or ""
        if base:
            check_path(base, "search")
        pattern = str(inp.get("pattern", ""))
        full = str(Path(base) / pattern) if base else pattern
        if (Path(base or ".").resolve() == REPO) and pattern.startswith("**"):
            block("A search over the whole repository reaches other campaigns.")
        if "campaigns" in full:
            check_command(full[full.index("campaigns"):])
    elif tool == "Grep":   # searches `path` (default: the whole repository)
        check_path(inp.get("path") or str(REPO), "search")
        if "campaigns" in str(inp.get("glob") or ""):
            check_command(str(inp["glob"]))
    elif tool == "Bash":
        check_command(str(inp.get("command", "")))
