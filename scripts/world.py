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
  status                   show pressure, budget use, today's cooldown and routes

Every roll goes to dm/roll-log.md as a hidden roll.
"""
import argparse
import json
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from roll import append_log, evaluate, roll_table  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
PRESSURE = {"calm": (10, 1), "lively": (20, 2), "relentless": (35, 3)}   # base chance %, session budget
CLASSES = ("hop", "trip", "journey", "night-safe", "night-camp", "skip")
ALWAYS_ROLL = ("journey", "night-camp")   # still roll when the session budget is spent twice over


class WorldError(ValueError):
    pass


def state_file(camp):
    dm = PROJECT / "campaigns" / camp / "dm"
    if not dm.is_dir():
        raise WorldError(f"no such campaign: {camp}")
    return dm / "world-state.json"


def load(camp):
    f = state_file(camp)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"pressure": "lively", "base": 20, "budget": 2, "interruptions": 0,
            "day": None, "day_events": 0, "routes": []}


def save(camp, st):
    state_file(camp).write_text(json.dumps(st, indent=1), encoding="utf-8")


def d100():
    total, _, _ = evaluate("1d100", secrets.SystemRandom())
    return total


def region_mod_from_table(path):
    m = re.search(r"Region modifier:\*?\*?\s*([+\-−±]?\s*\d+)", path.read_text(encoding="utf-8"))
    if not m:
        return 0
    return int(m.group(1).replace("−", "-").replace("±", "").replace(" ", ""))


def cmd_turn(args, st):
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
            res = roll_table(str(table), secrets.SystemRandom()) if table else "EVENT (no table given: pick a fitting one)"
            lines.append(f"{label}d% {roll} ≤ {chance}: EVENT → {res}")
        else:
            lines.append(f"{label}d% {roll} > {chance}: no event")
    head = f"{klass}: chance {chance}% ({how})"
    if notes:
        head += f"  [{'; '.join(notes)}]"
    return "\n".join([head] + lines), any_event


def main(argv=None):
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
    pl = sub.add_parser("planned"); pl.add_argument("text")
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
            out, _ = cmd_turn(args, st)
            try:
                append_log(args.campaign, [f"World turn: {l}" for l in out.splitlines()], True, None)
            except Exception:
                pass
        elif args.command == "planned":
            st["interruptions"] += 1
            out = f"planned event counted: {args.text} (interruptions {st['interruptions']}/{st['budget']})"
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
