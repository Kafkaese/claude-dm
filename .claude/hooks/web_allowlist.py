#!/usr/bin/env python3
"""PreToolUse hook: restrict WebFetch/WebSearch to domains listed in library/**/sources.md.

Each sources.md has a "## Allowed domains" section with one "- domain" bullet per line.
Subdomains of a listed domain are allowed. Exit code 2 blocks the call and shows stderr to Claude.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from typing import NoReturn

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))


def load_allowlist() -> set[str]:
    """Collect the domains listed under '## Allowed domains' in every library/**/sources.md."""
    domains = set()
    for path in PROJECT.glob("library/**/sources.md"):
        in_section = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                in_section = line.lstrip("#").strip().lower() == "allowed domains"
            elif in_section and line.strip().startswith("- "):
                domains.add(line.strip()[2:].strip().lower())
    return domains


def is_allowed(host: str, allowlist: set[str]) -> bool:
    """Whether a host (port stripped) is an allowed domain or a subdomain of one."""
    host = host.lower().split(":")[0]
    return any(host == d or host.endswith("." + d) for d in allowlist)


def block(reason: str, allowlist: set[str]) -> NoReturn:
    """Explain the refusal on stderr and exit with code 2, which blocks the tool call."""
    listed = ", ".join(sorted(allowlist)) or "(none)"
    print(
        f"{reason} Allowed domains: {listed}. "
        "Use one of these, or ask the user to add a source to a library/**/sources.md file.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    """Read the hook event from stdin and block WebFetch/WebSearch calls outside the allowlist."""
    event = json.load(sys.stdin)
    tool, tool_input = event.get("tool_name"), event.get("tool_input", {})
    allowlist = load_allowlist()

    if tool == "WebFetch":
        host = urlparse(tool_input.get("url", "")).hostname or ""
        if not is_allowed(host, allowlist):
            block(f"WebFetch to '{host}' is not on the allowlist.", allowlist)
    elif tool == "WebSearch":
        requested = tool_input.get("allowed_domains") or []
        if not requested:
            block("WebSearch must set allowed_domains.", allowlist)
        bad = [d for d in requested if not is_allowed(d, allowlist)]
        if bad:
            block(f"WebSearch domains not on the allowlist: {', '.join(bad)}.", allowlist)


if __name__ == "__main__":
    main()
