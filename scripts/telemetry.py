#!/usr/bin/env python3
"""telemetry.py: summarize how the DM's exchanges went (from .play/telemetry.jsonl).

  python3 scripts/telemetry.py                 the last session
  python3 scripts/telemetry.py --all           everything recorded
  python3 scripts/telemetry.py --session ID    one session
  python3 scripts/telemetry.py --since 2026-10-01
  python3 scripts/telemetry.py --details       also print the raw error lines (may contain spoilers)

The engine (web.py / play.py) writes one line per exchange: what kind it was (a player message,
an engine-driven combat step, a slash command), how long it took, the model turns, tokens and
cost, and every tool call with its errors. This summary only prints aggregates, and masks token
ids, squares and numbers in error messages, so it's spoiler-free unless --details is given.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
LOG = PROJECT / ".play" / "telemetry.jsonl"


def load(path: Path) -> list[dict[str, Any]]:
    """All telemetry records (bad lines are skipped)."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def mask(text: str) -> str:
    """An error message with the specifics masked, so similar errors group together and nothing
    secret shows: quoted names, squares (D4), tokens (g1, C), and numbers."""
    t = re.sub(r"(?<!\w)'[^'\n]*'(?!\w)|\"[^\"\n]*\"", "'…'", text)   # quoted names, not apostrophes
    t = re.sub(r"\b[A-Z]\d{1,2}\b", "SQ", t)
    t = re.sub(r"\b[a-z]{1,2}\d\b", "TOK", t)
    t = re.sub(r"\b[A-Z]\b", "TOK", t)
    t = re.sub(r"-?\d+", "N", t)
    return t[:140]


def combat_command(call: str) -> str | None:
    """The combat.py subcommand(s) of a Bash call, e.g. 'attack' or 'do: next+attack'."""
    m = re.search(r"combat\.py\s+(?:-c\s+\S+\s+)?(\w[\w-]*)(.*)", call)
    if not m:
        return None
    if m.group(1) == "do":
        subs = re.findall(r'"(\w[\w-]*)', m.group(2))
        return "do: " + "+".join(subs[:6])
    return m.group(1)


def game_command(name: str, call: str) -> str | None:
    """The game command of a tool call: a combat.py subcommand run through Bash, or a dm MCP tool
    (mcp__dm__combat_attack → 'combat_attack'; a batch → 'combat_batch: move+attack')."""
    if name == "Bash":
        return combat_command(call)
    if not name.startswith("mcp__dm__"):
        return None
    tool = name[len("mcp__dm__"):]
    if tool == "combat_batch":
        try:
            acts = json.loads(call).get("actions", [])
            return "combat_batch: " + "+".join(a.get("tool", "?").replace("combat_", "") for a in acts[:6])
        except ValueError:
            return tool   # the call text is truncated in the log for long batches
    return tool


def pct(values: list[float], q: float) -> float:
    """The q-quantile (0..1) of a list, nearest-rank."""
    v = sorted(values)
    return v[min(len(v) - 1, int(q * len(v)))] if v else 0.0


def summarize(recs: list[dict[str, Any]], details: bool) -> str:
    """The report text."""
    if not recs:
        return "No telemetry recorded yet (it's written by web.py / play.py)."
    out = []
    sessions = {r.get("session") for r in recs}
    out.append(f"{len(recs)} exchanges, {len(sessions)} session(s), {recs[0]['ts']} → {recs[-1]['ts']}")
    cost = sum(r.get("total_cost_usd") or 0 for r in recs)
    if cost:
        out.append(f"API-equivalent cost: ${cost:.2f} (on a subscription this is usage, not a bill)")

    out.append(f"\n{'By kind':<22} count  median s  p90 s  model turns  tool calls  tool errors  output chars")
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_kind[r.get("kind", "?")].append(r)
    for kind, rs in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        secs = [r.get("seconds", 0) for r in rs]
        turns = [r.get("num_turns", 0) for r in rs if "num_turns" in r]
        calls = [r.get("tool_calls", 0) for r in rs]
        errs = sum(r.get("tool_errors", 0) for r in rs)
        chars = [r.get("chars_out", 0) for r in rs]
        out.append(f"  {kind:<20} {len(rs):>5}  {statistics.median(secs):>7.0f}  {pct(secs, .9):>5.0f}"
                   f"  {statistics.mean(turns) if turns else 0:>11.1f}  {statistics.mean(calls):>10.1f}"
                   f"  {errs:>11}  {statistics.mean(chars):>12.0f}")

    tools: Counter[str] = Counter()
    combat: Counter[str] = Counter()
    combat_err: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    raw: list[str] = []
    for r in recs:
        for t in r.get("tools", []):
            tools[t.get("name", "?")] += 1
            cc = game_command(t.get("name", ""), t.get("call", ""))
            if cc:
                combat[cc.split(":")[0]] += 1
            if t.get("error"):
                errors[f"{t.get('name')}{' ' + cc if cc else ''}: {mask(t['error'])}"] += 1
                if cc:
                    combat_err[cc.split(":")[0]] += 1
                raw.append(f"{r['ts']} {r.get('kind')}: {t.get('call', '')[:160]}\n      → {t['error']}")
    out.append("\nTools: " + ", ".join(f"{k} {v}" for k, v in tools.most_common()))
    if combat:
        out.append("Game commands: " + ", ".join(f"{k} {v}" + (f" ({combat_err[k]} failed)" if combat_err[k] else "")
                                         for k, v in combat.most_common()))
    total_calls = sum(tools.values())
    total_err = sum(errors.values())
    out.append(f"\nTool errors: {total_err} of {total_calls} calls" + (f" ({100 * total_err / total_calls:.0f}%)" if total_calls else ""))
    for msg, n in errors.most_common(15):
        out.append(f"  {n:>3}× {msg}")

    combat_steps = by_kind.get("combat-step", []) + by_kind.get("go-signal", [])
    if combat_steps:
        multi = [r for r in combat_steps if r.get("tool_calls", 0) > 1]
        out.append(f"\nCombat steps needing more than one tool call: {len(multi)} of {len(combat_steps)} "
                   f"(ideal: one combat_batch call)")
    slow = sorted(recs, key=lambda r: -r.get("seconds", 0))[:5]
    out.append("\nSlowest exchanges:")
    for r in slow:
        out.append(f"  {r.get('seconds', 0):>5.0f} s  {r['ts']}  {r.get('kind')}: {r.get('tool_calls', 0)} tool calls, "
                   f"{r.get('num_turns', '?')} model turns")
    if details and raw:
        out.append("\nRaw errors (DM-ONLY, may contain spoilers):")
        out += ["  " + x for x in raw]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the process exit code."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--session")
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--details", action="store_true", help="print the raw error lines (may contain spoilers)")
    ap.add_argument("--file", default=str(LOG))
    args = ap.parse_args(argv)
    recs = load(Path(args.file))
    if args.since:
        recs = [r for r in recs if r.get("ts", "") >= args.since]
    if args.session:
        recs = [r for r in recs if r.get("session") == args.session]
    elif not args.all and not args.since and recs:
        last = recs[-1].get("session")
        recs = [r for r in recs if r.get("session") == last]
    print(summarize(recs, args.details))
    return 0


if __name__ == "__main__":
    sys.exit(main())
