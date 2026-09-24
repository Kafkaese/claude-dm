#!/usr/bin/env python3
"""Dice roller for Claude DM. Use it for every roll; never invent results.

Usage:
  python3 scripts/roll.py [options] ROLL [ROLL ...]

A ROLL is a dice expression, optionally prefixed with a label and a colon:
  1d20+5                     d20 = 1d20, d% = 1d100
  "Goblin 1 init: 1d20+6"
  "Longsword: 1d8+4"
  4d6dl1                     drop lowest 1 (also dh = drop highest)
  2d20kh1                    keep highest 1 (also kl = keep lowest)
  2d6+1d4-1                  any mix of dice and numbers joined by + and -

Options:
  -n, --times N        roll each ROLL N times (e.g. -n 6 4d6dl1 for ability scores)
  -c, --campaign SLUG  append results to campaigns/SLUG/dm/roll-log.md
  -H, --hidden         mark as a hidden (GM screen) roll in the log
  --note TEXT          context for the log, e.g. "vs AC 16"
  --seed N             fixed seed (testing only)

A single kept d20 that rolls 20 or 1 is flagged NAT 20 / NAT 1. Check PF1e threat
ranges (e.g. 19-20) against the d20 value shown in brackets.
"""
import argparse
import random
import re
import secrets
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TERM = re.compile(r"([+-])?\s*(?:(\d*)d(\d+|%)(?:(kh|kl|dh|dl)(\d+))?|(\d+))", re.I)


class RollError(ValueError):
    pass


def roll_dice(rng, count, sides, mod, mod_n):
    dice = [rng.randint(1, sides) for _ in range(count)]
    order = sorted(range(count), key=lambda i: dice[i])  # indices, lowest first
    keep = set(range(count))
    if mod:
        mod = mod.lower()
        if mod_n > count:
            raise RollError(f"cannot {mod}{mod_n} from {count} dice")
        if mod == "kh":
            keep = set(order[count - mod_n:])
        elif mod == "kl":
            keep = set(order[:mod_n])
        elif mod == "dh":
            keep = set(order[: count - mod_n])
        elif mod == "dl":
            keep = set(order[mod_n:])
    total = sum(dice[i] for i in keep)
    shown = ",".join(str(d) if i in keep else f"({d})" for i, d in enumerate(dice))
    kept = [dice[i] for i in sorted(keep)]
    return total, f"[{shown}]", kept


def evaluate(expr, rng):
    compact = expr.replace(" ", "")
    if not compact:
        raise RollError("empty expression")
    pos, total, parts, flags = 0, 0, [], []
    for m in TERM.finditer(compact):
        if m.start() != pos:
            break
        pos = m.end()
        sign = -1 if m.group(1) == "-" else 1
        if m.start() > 0 and not m.group(1):
            raise RollError(f"missing + or - before '{m.group(0)}'")
        prefix = ("-" if sign < 0 else "+") if parts else ("-" if sign < 0 else "")
        if m.group(6):
            value, text = int(m.group(6)), m.group(6)
        else:
            count = int(m.group(2) or 1)
            sides = 100 if m.group(3) == "%" else int(m.group(3))
            if not (1 <= count <= 1000 and 2 <= sides <= 1000):
                raise RollError(f"unreasonable dice: {m.group(0)}")
            value, text, kept = roll_dice(rng, count, sides, m.group(4), int(m.group(5) or 0))
            if sides == 20 and len(kept) == 1 and kept[0] in (1, 20):
                flags.append(f"NAT {kept[0]}")
        total += sign * value
        parts.append(prefix + text)
    if pos != len(compact):
        raise RollError(f"can't parse '{expr}' at '{compact[pos:]}'")
    return total, "".join(parts), flags


def append_log(campaign, lines, hidden, note):
    dm_dir = PROJECT / "campaigns" / campaign / "dm"
    if not dm_dir.is_dir():
        raise RollError(f"no such campaign folder: {dm_dir}")
    log = dm_dir / "roll-log.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    tag = " [HIDDEN]" if hidden else ""
    suffix = f" ({note})" if note else ""
    with log.open("a", encoding="utf-8") as f:
        if log.stat().st_size == 0:
            f.write("# Roll Log (DM ONLY)\n\n")
        for line in lines:
            f.write(f"- {stamp}{tag} {line}{suffix}\n")


def main(argv=None):
    p = argparse.ArgumentParser(description="Dice roller for Claude DM.")
    p.add_argument("rolls", nargs="+")
    p.add_argument("-n", "--times", type=int, default=1)
    p.add_argument("-c", "--campaign")
    p.add_argument("-H", "--hidden", action="store_true")
    p.add_argument("--note")
    p.add_argument("--seed", type=int)
    args = p.parse_args(argv)

    rng = random.Random(args.seed) if args.seed is not None else secrets.SystemRandom()
    lines = []
    try:
        for raw in args.rolls:
            label, _, expr = raw.rpartition(":")
            label = label.strip()
            for i in range(args.times):
                total, detail, flags = evaluate(expr, rng)
                name = f"{label} #{i + 1}".strip() if args.times > 1 else label
                line = f"{expr.strip()} → {detail} = **{total}**"
                if flags:
                    line += " " + " ".join(flags)
                lines.append(f"{name}: {line}" if name else line)
        if args.campaign:
            append_log(args.campaign, lines, args.hidden, args.note)
    except RollError as e:
        print(f"roll error: {e}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
