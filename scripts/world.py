#!/usr/bin/env python3
"""World turns for Claude DM: the random-event part of the living world, as deterministic code.

Implements the frequency rules of library/general/table-rules/living-world.md (section 5):
transition classes, the region modifier, the settlement cooldown, repeated routes, and the
session budget. Scheduled events, clocks and reaction triggers stay with the DM (dm/world.md).
State: campaigns/<campaign>/dm/world-state.json (DM only).

Usage: python3 scripts/world.py -c CAMPAIGN COMMAND [args]

  config --pressure calm|lively|relentless [--base N] [--budget N]
                           set world pressure (base event chance and session budget)
  session                  start of a session: reset the interruption count
  day "9 Arodus"           a new in-game day: resets the settlement cooldown and today's routes
  turn CLASS [--table dm/tables/<region>.md] [--region-mod N] [--route "inn>market"] [--settlement]
       [--weeks N]         one world turn. CLASS: hop, trip, journey, night-safe, night-camp, skip.
                           Works out the chance, applies cooldown and budget, rolls d%, and on an
                           event rolls on the table (whose "Region modifier" line is used if
                           --region-mod isn't given)
  planned "TEXT"           count a planned proactive event (agenda, clock, trigger) as an interruption

turn and planned take --note "TEXT": what else was checked or fired (a clock, a trigger, a track
change). Both write their line to the live log's "World turns" section themselves (the session
being played: dm/session-log/session-NN.md) and keep its header's interruption count and routes
current, so the DM doesn't log world turns by hand.
  status                   show pressure, budget use, today's cooldown and routes

Every roll goes to dm/roll-log.md as a hidden roll.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from roll import append_log, evaluate, roll_table  # noqa: E402
from typing import Any

WorldState = dict[str, Any]   # the contents of dm/world-state.json

PROJECT = Path(__file__).resolve().parents[1]
PRESSURE = {"calm": (10, 1), "lively": (20, 2), "relentless": (35, 3)}   # base chance %, session budget
CLASSES = ("hop", "trip", "journey", "night-safe", "night-camp", "skip")
RNG: Any = None   # tests set a seeded random.Random here; play uses secrets.SystemRandom
ALWAYS_ROLL = ("journey", "night-camp")   # still roll when the session budget is spent twice over


class WorldError(ValueError):
    """A world-turn command that can't run (missing campaign, table, …)."""
    pass


def state_file(camp: str) -> Path:
    """The path of the campaign's world-state.json.

    Raises:
        WorldError: if the campaign folder doesn't exist.
    """
    dm = PROJECT / "campaigns" / camp / "dm"
    if not dm.is_dir():
        raise WorldError(f"no such campaign: {camp}")
    return dm / "world-state.json"


def load(camp: str) -> WorldState:
    """Load the world state, or return lively defaults if the campaign has none yet."""
    f = state_file(camp)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"pressure": "lively", "base": 20, "budget": 2, "interruptions": 0,
            "day": None, "day_events": 0, "routes": []}


def save(camp: str, st: WorldState) -> None:
    """Write the world state back to dm/world-state.json."""
    state_file(camp).write_text(json.dumps(st, indent=1), encoding="utf-8")


def d100() -> int:
    """Roll a d%, with the same random source as roll.py."""
    total, _, _ = evaluate("1d100", RNG or secrets.SystemRandom())
    return total


def region_mod_from_table(path: Path) -> int:
    """Read the '**Region modifier:** +10%' line from an event table (0 if there is none)."""
    m = re.search(r"Region modifier:\*?\*?\s*([+\-−±]?\s*\d+)", path.read_text(encoding="utf-8"))
    if not m:
        return 0
    return int(m.group(1).replace("−", "-").replace("±", "").replace(" ", ""))


def cmd_turn(args: argparse.Namespace, st: WorldState) -> tuple[str, bool]:
    """Run one world turn: work out the event chance for the transition class, apply the
    repeated-route rule, settlement cooldown and session budget, roll, and roll the table on an event.

    Returns:
        (the report for the DM, whether any event happened). Updates `st` in place.
    """
    klass = args.klass
    notes = []
    if args.route:
        if args.route in st["routes"]:
            if klass == "trip":
                notes.append(f"repeated route '{args.route}' today: counts as a hop")
                klass = "hop"
        else:
            st["routes"].append(args.route)
    if klass == "hop":
        return "hop: no random event roll. Check only what's due now (scheduled events, clocks, triggers).", False
    table = None
    if args.table:
        table = Path(args.table) if Path(args.table).is_absolute() else PROJECT / args.table
        if not table.exists():
            table = PROJECT / "campaigns" / args.campaign / args.table
        if not table.exists():
            raise WorldError(f"no such table: {args.table}")
    mod = args.region_mod if args.region_mod is not None else (region_mod_from_table(table) if table else 0)
    base = st["base"]
    if klass == "trip":
        chance, how = base // 2 + mod, f"base {base} ÷ 2, region {mod:+d}"
    elif klass == "night-safe":
        chance, how = base // 2 - 10, f"base {base} ÷ 2, safe lodging -10"
    elif klass in ("journey", "night-camp"):
        chance, how = base + mod, f"base {base}, region {mod:+d}"
    else:  # skip
        chance, how = base, f"base {base}, per week"
    # settlement cooldown
    cap = 2 if st.get("pressure") == "relentless" else 1
    if args.settlement and st["day_events"] >= cap:
        return (f"{klass}: no roll. The settlement cooldown is reached ({st['day_events']} random event(s) "
                f"today, max {cap}).", False)
    # session budget
    used, budget = st["interruptions"], st["budget"]
    if used >= 2 * budget and klass not in ALWAYS_ROLL:
        return (f"{klass}: no roll. The session budget is spent twice over ({used}/{budget}). "
                f"Earned consequences still happen, preferably at the destination.", False)
    if used >= budget:
        chance //= 2
        how += f", halved (budget {used}/{budget})"
    chance = max(0, min(100, chance))
    lines, any_event = [], False
    for w in range(max(1, args.weeks if klass == "skip" else 1)):
        roll = d100()
        label = f"week {w + 1}: " if klass == "skip" and args.weeks > 1 else ""
        if roll <= chance:
            any_event = True
            st["interruptions"] += 1
            if args.settlement:
                st["day_events"] += 1
            res = roll_table(str(table), RNG or secrets.SystemRandom()) if table else "EVENT (no table given: pick a fitting one)"
            lines.append(f"{label}d% {roll} ≤ {chance}: EVENT → {res}")
        else:
            lines.append(f"{label}d% {roll} > {chance}: no event")
    head = f"{klass}: chance {chance}% ({how})"
    if notes:
        head += f"  [{'; '.join(notes)}]"
    return "\n".join([head] + lines), any_event


def live_log(camp: str) -> Path | None:
    """The live log of the session being played (session NN = "Sessions played" + 1), if it exists."""
    md = PROJECT / "campaigns" / camp / "campaign.md"
    played = re.search(r"\*\*Sessions played:\*\*\s*(\d+)", md.read_text(encoding="utf-8")) if md.exists() else None
    nn = (int(played.group(1)) if played else 0) + 1
    path = PROJECT / "campaigns" / camp / "dm" / "session-log" / f"session-{nn:02d}.md"
    return path if path.exists() else None


def log_world(camp: str, line: str, st: WorldState, event: bool = False) -> bool:
    """Append one line to the live log's "World turns" section (replacing the template's empty bullet)
    and update the header's interruptions and routes. Returns whether a live log was found."""
    path = live_log(camp)
    if not path:
        return False
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## World turns[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if m:
        body = m.group(1).rstrip("\n")
        body = re.sub(r"\n-\s*$", "", body) if re.search(r"\n-\s*$", body) else body
        text = text[:m.start(1)] + body + f"\n- {line}\n\n" + text[m.end(1):]
    else:
        text = text.rstrip("\n") + f"\n\n## World turns\n- {line}\n"
    text = re.sub(r"(\*\*Interruptions:\*\*\s*)\d+\s*/\s*budget\s*\S+",
                  lambda x: f"{x.group(1)}{st['interruptions']} / budget {st['budget']}", text, count=1)
    if event and st.get("day"):
        text = re.sub(r"(\*\*Last random event:\*\*)[^\n·]*", lambda x: f"{x.group(1)} {st['day']} ", text, count=1)
    if st.get("routes"):
        text = re.sub(r"(\*\*Routes made today:\*\*)[^\n·]*", lambda x: f"{x.group(1)} {', '.join(st['routes'])}", text, count=1)
    path.write_text(text, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the process exit code."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", "--campaign", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    cf = sub.add_parser("config"); cf.add_argument("--pressure", choices=list(PRESSURE), required=True)
    cf.add_argument("--base", type=int); cf.add_argument("--budget", type=int)
    sub.add_parser("session")
    dy = sub.add_parser("day"); dy.add_argument("name")
    tu = sub.add_parser("turn"); tu.add_argument("klass", choices=CLASSES)
    tu.add_argument("--table"); tu.add_argument("--region-mod", type=int); tu.add_argument("--route")
    tu.add_argument("--settlement", action="store_true"); tu.add_argument("--weeks", type=int, default=1)
    tu.add_argument("--note", help="what else was checked or fired (clock, trigger, track change)")
    pl = sub.add_parser("planned"); pl.add_argument("text"); pl.add_argument("--note")
    sub.add_parser("status")
    args = p.parse_args(argv)
    try:
        st = load(args.campaign)
        if args.command == "config":
            base, budget = PRESSURE[args.pressure]
            st.update(pressure=args.pressure, base=args.base or base, budget=args.budget or budget)
            out = f"world pressure {st['pressure']}: base {st['base']}%, session budget {st['budget']}"
        elif args.command == "session":
            st["interruptions"] = 0
            out = f"new session: interruptions 0/{st['budget']}"
        elif args.command == "day":
            st.update(day=args.name, day_events=0, routes=[])
            out = f"new day: {args.name} (cooldown and routes reset)"
        elif args.command == "turn":
            out, event = cmd_turn(args, st)
            try:
                append_log(args.campaign, [f"World turn: {l}" for l in out.splitlines()], True, None)
            except Exception:
                pass
            day = f"{st['day']}, " if st.get("day") else ""
            what = "hop (no roll)" if out.startswith("hop:") else " · ".join(out.splitlines())
            if log_world(args.campaign, f"{day}{what}" + (f" · {args.note}" if args.note else ""), st, event):
                out += "\n(logged in the live log's World turns)"
        elif args.command == "planned":
            st["interruptions"] += 1
            out = f"planned event counted: {args.text} (interruptions {st['interruptions']}/{st['budget']})"
            day = f"{st['day']}, " if st.get("day") else ""
            if log_world(args.campaign, f"{day}planned: {args.text}" + (f" · {args.note}" if args.note else ""), st):
                out += "\n(logged in the live log's World turns)"
        else:
            out = (f"pressure {st['pressure']} (base {st['base']}%), interruptions {st['interruptions']}/{st['budget']}, "
                   f"day {st.get('day')}: {st['day_events']} random event(s), routes: {', '.join(st['routes']) or 'none'}")
        save(args.campaign, st)
        print(out)
    except WorldError as e:
        print(f"world error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
