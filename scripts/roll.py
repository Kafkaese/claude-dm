#!/usr/bin/env python3
"""Dice roller for Claude DM. Use it for every roll; never invent results.

Usage:
  python3 scripts/roll.py [options] ROLL [ROLL ...]

A ROLL is a dice expression, optionally prefixed with a label and a colon (or =).
Labels may contain spaces and dashes; quote them:
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
  --oracle PCT         yes/no oracle: each ROLL is a question, answered YES with PCT% odds.
                       Set PCT from established facts BEFORE rolling (90/70/50/30/10).
                       Rolls near the threshold add BUT; extreme rolls add AND.
  --table              each ROLL is a markdown file with a table whose first column holds
                       ranges (e.g. 1-20, 21–35, 36). The die size is the highest number;
                       the ranges must cover 1..max without gaps or overlaps.

A single kept d20 that rolls 20 or 1 is flagged NAT 20 / NAT 1. Check PF1e threat
ranges (e.g. 19-20) against the d20 value shown in brackets.
"""
from __future__ import annotations

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
    """A dice expression, oracle or table that can't be parsed or rolled."""
    pass


def roll_dice(rng: random.Random, count: int, sides: int, mod: str | None, mod_n: int) -> tuple[int, str, list[int]]:
    """Roll `count` dice with `sides` sides and apply a keep/drop modifier.

    Args:
        rng: the random source (secrets.SystemRandom in play, a seeded Random in tests).
        count: number of dice.
        sides: faces per die.
        mod: 'kh', 'kl', 'dh' or 'dl' (keep/drop highest/lowest), or None.
        mod_n: how many dice the modifier keeps or drops.

    Returns:
        (total of the kept dice, display string like '[6,(2),5]' with dropped dice in parentheses,
        the kept dice).
    """
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


def evaluate(expr: str, rng: random.Random) -> tuple[int, str, list[str]]:
    """Evaluate a dice expression such as '2d6+1d4-1' or '4d6dl1'.

    Returns:
        (total, detail string such as '[4,4]+[4]-1', flags such as ['NAT 20'] for a single kept d20).

    Raises:
        RollError: if the expression can't be parsed or asks for unreasonable dice.
    """
    compact = expr.replace(" ", "")
    if not compact:
        raise RollError("empty expression")
    pos, total = 0, 0
    parts: list[str] = []
    flags: list[str] = []
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


def oracle(pct: int, rng: random.Random) -> str:
    """Answer a yes/no question with `pct`% odds of YES.

    Within each side, the most extreme 10% add AND and the 20% nearest the threshold add BUT.
    Returns the display string, e.g. '(odds 30%) d% → [23] = **YES, BUT**'.
    """
    roll = rng.randint(1, 100)
    # Within each side: the most extreme 10% add AND, the 20% nearest the threshold add BUT.
    if roll <= pct:
        answer = "YES, AND" if roll <= pct * 0.1 else "YES, BUT" if roll > pct * 0.8 else "YES"
    else:
        no_range = 100 - pct
        answer = ("NO, AND" if roll > 100 - no_range * 0.1
                  else "NO, BUT" if roll <= pct + no_range * 0.2 else "NO")
    return f"(odds {pct}%) d% → [{roll}] = **{answer}**"


ROW_RANGE = re.compile(r"^(\d+)(?:\s*[-–]\s*(\d+))?$")


def roll_table(path_str: str, rng: random.Random) -> str:
    """Roll on a markdown table whose first column holds ranges (1-20, 21–35, 36, …).

    The die size is the highest number; ranges must cover 1..max without gaps or overlaps.
    Returns the display string with the rolled row's cells.

    Raises:
        RollError: if the file is missing or its ranges are malformed.
    """
    path = Path(path_str)
    if not path.is_absolute() and not path.exists():
        path = PROJECT / path_str
    if not path.is_file():
        raise RollError(f"no such table file: {path_str}")
    title, rows = path.stem, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# ") and title == path.stem:
            title = line[2:].strip()
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = ROW_RANGE.match(cells[0])
        if m:
            low = int(m.group(1))
            rows.append((low, int(m.group(2) or low), cells[1:]))
    if not rows:
        raise RollError(f"no ranged rows found in {path_str}")
    rows.sort()
    expected = 1
    for low, high, _ in rows:
        if low != expected or high < low:
            raise RollError(f"{path_str}: ranges must be contiguous from 1; problem at {low}-{high}")
        expected = high + 1
    die = expected - 1
    roll = rng.randint(1, die)
    entry = next(cells for low, high, cells in rows if low <= roll <= high)
    return f"Table {title}: d{die} → [{roll}] = **{' | '.join(entry)}**"


def append_log(campaign: str, lines: list[str], hidden: bool, note: str | None) -> None:
    """Append result lines to campaigns/<campaign>/dm/roll-log.md, marked [HIDDEN] if hidden.

    Raises:
        RollError: if the campaign folder doesn't exist.
    """
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


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the process exit code (0 on success, 1 on a roll error)."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("rolls", nargs="+")
    p.add_argument("-n", "--times", type=int, default=1)
    p.add_argument("-c", "--campaign")
    p.add_argument("-H", "--hidden", action="store_true")
    p.add_argument("--note")
    p.add_argument("--seed", type=int)
    p.add_argument("--oracle", type=int, metavar="PCT")
    p.add_argument("--table", action="store_true")
    args = p.parse_args(argv)

    rng = random.Random(args.seed) if args.seed is not None else secrets.SystemRandom()
    lines = []
    try:
        if args.oracle is not None:
            if not 1 <= args.oracle <= 99:
                raise RollError("oracle odds must be between 1 and 99")
            for question in args.rolls:
                lines.append(f"Oracle: {question.strip()} {oracle(args.oracle, rng)}")
            args.rolls = []
        if args.table:
            for table in args.rolls:
                lines += [roll_table(table, rng) for _ in range(args.times)]
            args.rolls = []
        for raw in args.rolls:
            label, sep, expr = raw.rpartition(":")
            if not sep and "=" in raw:  # also accept "Label=1d20+5"
                label, _, expr = raw.partition("=")
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
