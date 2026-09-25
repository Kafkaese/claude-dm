#!/usr/bin/env python3
"""Combat tracker for Claude DM: grid map, tokens, initiative, HP, conditions.

The state lives in campaigns/<campaign>/dm/combat/current.json. Never edit the map by hand;
let this script render it and do the geometry (PF1e 5-10-5 diagonals, reach, flanking).

Usage: python3 scripts/combat.py -c CAMPAIGN COMMAND [args]

Setup
  new MAPFILE | --blank WxH       start an encounter from a terrain map (see below)
  add TOKEN NAME --pos D4 --init 15 --hp 11 [--ac 16] [--side enemy|pc|ally]
      [--size 1|2|3|4] [--reach 5] [--speed 30] [--cr 1/2] [--hidden]
                                  TOKEN is 1-2 chars: PCs uppercase (V), others lowercase+digit (g1)
Play
  show [--dm]                     player view (paste verbatim) / DM view (never paste)
  next                            advance to the next turn (starts a new round when needed)
  move TOKEN POS                  move along the cheapest legal path, report feet used
  dist A B                        distance between two tokens (or squares) in feet
  threat TOKEN                    who threatens TOKEN, and who flanks it
  hp TOKEN DELTA                  e.g. hp g2 -7, hp V +5
  cond TOKEN add|remove TEXT      conditions, e.g. cond g2 add prone
  init TOKEN VALUE                change initiative (delay / ready)
  reveal TOKEN / hide TOKEN       toggle visibility to the players
  remove TOKEN                    take a token off the board (fled, dismissed)
  end                             finish the encounter: summary + XP, archive the state

Map files: one line per row, one character per square, no spaces between squares.
  .  floor      #  wall (blocks)     +  door        ^  difficult (rubble, brush)
  ~  water (difficult)  T  trees (difficult)  _  pit / chasm (blocks)  (space) outside (blocks)
Columns are lettered A-Z (max 26 wide), rows numbered from 1.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TERRAIN = {
    ".": ("floor", 1), "+": ("door", 1), "=": ("bridge", 1),
    "^": ("difficult", 2), "~": ("water", 2), "T": ("trees", 2),
    "#": ("wall", None), "_": ("pit", None), " ": ("outside", None),
}
XP_BY_CR = {"1/8": 50, "1/6": 65, "1/4": 100, "1/3": 135, "1/2": 200, "1": 400, "2": 600,
            "3": 800, "4": 1200, "5": 1600, "6": 2400, "7": 3200, "8": 4800, "9": 6400,
            "10": 9600, "11": 12800, "12": 19200, "13": 25600, "14": 38400, "15": 51200,
            "16": 76800, "17": 102400, "18": 153600, "19": 204800, "20": 307200}
FRIENDLY = {"pc", "ally"}


class CombatError(ValueError):
    pass


# ---------- state ----------

def state_path(campaign):
    dm = PROJECT / "campaigns" / campaign / "dm"
    if not dm.is_dir():
        raise CombatError(f"no such campaign: {campaign}")
    return dm / "combat" / "current.json"


def load(campaign):
    path = state_path(campaign)
    if not path.exists():
        raise CombatError("no active encounter; start one with 'new'")
    return json.loads(path.read_text(encoding="utf-8"))


def save(campaign, st):
    path = state_path(campaign)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, indent=1), encoding="utf-8")


def token(st, tok):
    for c in st["tokens"]:
        if c["token"] == tok:
            return c
    raise CombatError(f"no token '{tok}'")


# ---------- geometry ----------

def parse_pos(s, st=None):
    s = s.strip().upper()
    if len(s) < 2 or not s[0].isalpha() or not s[1:].isdigit():
        raise CombatError(f"bad square '{s}', expected e.g. D4")
    x, y = ord(s[0]) - ord("A"), int(s[1:]) - 1
    if st and not (0 <= x < st["w"] and 0 <= y < st["h"]):
        raise CombatError(f"square {s} is off the map")
    return x, y


def fmt_pos(x, y):
    return f"{chr(ord('A') + x)}{y + 1}"


def cells(c, at=None):
    x, y = at or (c["x"], c["y"])
    return [(x + i, y + j) for i in range(c["size"]) for j in range(c["size"])]


def sq_dist(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + min(dx, dy) // 2


def feet_between(c1, c2):
    return 5 * min(sq_dist(a, b) for a in cells(c1) for b in cells(c2))


def cost(st, x, y):
    if not (0 <= x < st["w"] and 0 <= y < st["h"]):
        return None
    return TERRAIN.get(st["grid"][y][x], ("?", 1))[1]


def label(c):
    return c["token"] + (" [HIDDEN]" if c.get("hidden") else "")


def active(c):
    return not c.get("removed") and c["hp"] > 0


def blocked_by_hostile(st, mover, x, y):
    for o in st["tokens"]:
        if o is mover or not active(o):
            continue
        if (o["side"] in FRIENDLY) != (mover["side"] in FRIENDLY) and (x, y) in cells(o):
            return True
    return False


def occupied(st, mover, x, y):
    return any(o is not mover and not o.get("removed") and (x, y) in cells(o) for o in st["tokens"])


def path_cost(st, mover, dest):
    """Cheapest legal move in feet (Dijkstra over (x, y, diagonal parity))."""
    import heapq
    start = (mover["x"], mover["y"])

    def footprint_ok(x, y, final):
        for cx, cy in cells(mover, (x, y)):
            if cost(st, cx, cy) is None or blocked_by_hostile(st, mover, cx, cy):
                return False
            if final and occupied(st, mover, cx, cy):
                return False
        return True

    def step_cost(x, y):
        return max(cost(st, cx, cy) for cx, cy in cells(mover, (x, y)))

    if not footprint_ok(*dest, final=True):
        raise CombatError(f"{fmt_pos(*dest)} is blocked or occupied")
    best = {(start, 0): 0}
    heap = [(0, start, 0)]
    while heap:
        feet, (x, y), parity = heapq.heappop(heap)
        if (x, y) == dest:
            return feet
        if feet > best.get(((x, y), parity), 1e9):
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not footprint_ok(nx, ny, final=False):
                    continue
                diag = dx != 0 and dy != 0
                if diag and (not footprint_ok(x + dx, y, False) or not footprint_ok(x, y + dy, False)):
                    continue  # can't cut a corner past walls or enemies
                mult = step_cost(nx, ny)
                if diag:
                    squares, npar = (3 if mult > 1 else (1 if parity == 0 else 2)), 1 - parity
                else:
                    squares, npar = mult, parity
                nf = feet + 5 * squares
                key = ((nx, ny), npar)
                if nf < best.get(key, 1e9):
                    best[key] = nf
                    heapq.heappush(heap, (nf, (nx, ny), npar))
    raise CombatError(f"no legal path to {fmt_pos(*dest)}")


def threatens(a, t):
    if not active(a) or a is t or a.get("no_threat"):
        return False
    if (a["side"] in FRIENDLY) == (t["side"] in FRIENDLY):
        return False
    reach = a.get("reach", 5)
    for p in cells(a):
        for q in cells(t):
            dx, dy = abs(p[0] - q[0]), abs(p[1] - q[1])
            if 5 * sq_dist(p, q) <= reach or (reach == 10 and dx == dy == 2):
                return True
    return False


def flanks(a, b, t):
    """PF1e: the line between attacker centres passes through opposite borders/corners of t."""
    s = t["size"]
    x0, y0, x1, y1 = t["x"], t["y"], t["x"] + s, t["y"] + s
    ax, ay = a["x"] + a["size"] / 2, a["y"] + a["size"] / 2
    bx, by = b["x"] + b["size"] / 2, b["y"] + b["size"] / 2
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
    if t0 >= t1:
        return False
    eps = 1e-9

    def edges(tt):
        px, py = ax + tt * dx, ay + tt * dy
        return {e for e, hit in (("L", abs(px - x0) < eps), ("R", abs(px - x1) < eps),
                                 ("T", abs(py - y0) < eps), ("B", abs(py - y1) < eps)) if hit}
    e0, e1 = edges(t0), edges(t1)
    return ("L" in e0 and "R" in e1) or ("R" in e0 and "L" in e1) or \
           ("T" in e0 and "B" in e1) or ("B" in e0 and "T" in e1)


# ---------- rendering ----------

def health(c):
    if c.get("removed"):
        return "gone"
    if c["hp"] <= 0:
        return "down"
    r = c["hp"] / max(c["max_hp"], 1)
    return ("unhurt" if r >= 1 else "scratched" if r > 0.75 else "hurt" if r > 0.5
            else "bloodied" if r > 0.25 else "barely standing")


def order(st):
    return sorted(st["tokens"], key=lambda c: -c["init"])


def render(st, dm=False):
    visible = [c for c in st["tokens"] if not c.get("removed") and (dm or not c.get("hidden"))]
    board = [list(row) for row in st["grid"]]
    for c in visible:
        if c["hp"] <= 0 and c["side"] not in FRIENDLY and not dm:
            mark = "x"
        else:
            mark = c["token"]
        for x, y in cells(c):
            board[y][x] = mark
    out = [f"Round {st['round']}" + (" (DM VIEW)" if dm else "")]
    out.append("    " + "".join(f"{chr(ord('A') + i):<3}" for i in range(st["w"])).rstrip())
    for y, row in enumerate(board):
        out.append(f"{y + 1:>2}  " + "".join(f"{cell:<3}" for cell in row).rstrip())
    used = {ch for row in st["grid"] for ch in row}
    legend = [f"{ch} {TERRAIN[ch][0]}" for ch in "#+^~T_=" if ch in used]
    if any(c["hp"] <= 0 and c["side"] not in FRIENDLY for c in visible) and not dm:
        legend.append("x fallen")
    if legend:
        out.append("    " + "   ".join(legend))
    out.append("")
    cur = st.get("turn")
    for c in order(st):
        if c.get("removed") or (c.get("hidden") and not dm):
            continue
        mark = "▶" if c["token"] == cur else " "
        if dm or c["side"] == "pc":
            hp = f"HP {c['hp']}/{c['max_hp']}"
        else:
            hp = health(c)
        extra = []
        if c.get("conditions"):
            extra.append(", ".join(c["conditions"]))
        if dm:
            extra += [f"AC {c['ac']}" if c.get("ac") else "", "hidden" if c.get("hidden") else "",
                      f"CR {c['cr']}" if c.get("cr") else ""]
        extra = "  ".join(e for e in extra if e)
        init = f"{c['init']:g}"
        out.append(f"{mark} {c['token']:<2} {c['name']:<18} {init:>4}  {hp:<16}{extra}".rstrip())
    return "\n".join(out)


# ---------- commands ----------

def cmd_new(args):
    path = state_path(args.campaign)
    if path.exists() and not args.force:
        raise CombatError("an encounter is already active; 'end' it first or pass --force")
    if args.blank:
        w, h = (int(v) for v in args.blank.lower().split("x"))
        grid = ["." * w for _ in range(h)]
    else:
        mp = Path(args.mapfile)
        if not mp.is_file():
            mp = PROJECT / args.mapfile
        if not mp.is_file():
            raise CombatError(f"no such map file: {args.mapfile}")
        lines = [l.rstrip("\n") for l in mp.read_text(encoding="utf-8").splitlines()]
        lines = [l for l in lines if l.strip() and not l.lstrip().startswith("//")]
        w = max(len(l) for l in lines)
        grid = [l.ljust(w) for l in lines]
        h = len(grid)
        bad = {ch for row in grid for ch in row} - set(TERRAIN)
        if bad:
            raise CombatError(f"unknown map characters: {''.join(sorted(bad))}")
    if not (1 <= w <= 26 and h >= 1):
        raise CombatError("map must be 1-26 columns wide")
    st = {"w": w, "h": h, "grid": grid, "tokens": [], "round": 1, "turn": None,
          "started": datetime.now().isoformat(timespec="minutes")}
    save(args.campaign, st)
    return render(st, dm=True)


def cmd_add(args, st):
    if len(args.token) > 2:
        raise CombatError("tokens are at most 2 characters")
    if any(c["token"] == args.token for c in st["tokens"]):
        raise CombatError(f"token '{args.token}' already exists")
    x, y = parse_pos(args.pos, st)
    c = {"token": args.token, "name": args.name, "side": args.side, "x": x, "y": y,
         "size": args.size, "reach": args.reach, "speed": args.speed, "init": args.init,
         "hp": args.hp, "max_hp": args.hp, "ac": args.ac, "cr": args.cr,
         "hidden": args.hidden, "conditions": []}
    for cx, cy in cells(c):
        if cost(st, cx, cy) is None or occupied(st, c, cx, cy):
            raise CombatError(f"{fmt_pos(cx, cy)} is blocked or occupied")
    st["tokens"].append(c)
    return f"Added {args.token} ({args.name}) at {fmt_pos(x, y)}"


def cmd_next(args, st):
    live = [c for c in order(st) if not c.get("removed") and (c["hp"] > 0 or c["side"] in FRIENDLY)]
    if not live:
        raise CombatError("no combatants")
    toks = [c["token"] for c in live]
    if st["turn"] in toks:
        i = toks.index(st["turn"]) + 1
        if i >= len(toks):
            i, st["round"] = 0, st["round"] + 1
    else:
        i = 0
    st["turn"] = toks[i]
    c = live[i]
    note = "" if c["hp"] > 0 else " (at 0 HP or below: disabled / dying)"
    return f"Round {st['round']}: {label(c)} ({c['name']}) acts{note}"


def cmd_move(args, st):
    c = token(st, args.token)
    dest = parse_pos(args.pos, st)
    feet = path_cost(st, c, dest)
    frm = fmt_pos(c["x"], c["y"])
    before = [label(o) for o in st["tokens"] if threatens(o, c)]
    c["x"], c["y"] = dest
    speed = c.get("speed") or 30
    warn = f"  EXCEEDS SPEED {speed} ft (double move needs {2 * speed} ft)" if feet > speed else ""
    msg = f"{c['token']} moves {frm} → {fmt_pos(*dest)}: {feet} ft{warn}"
    if before:
        msg += f"\n  Started threatened by {', '.join(before)}: leaving provokes AoO unless 5-ft step / withdraw."
    return msg


def resolve(st, ref):
    try:
        return token(st, ref)
    except CombatError:
        x, y = parse_pos(ref, st)
        return {"x": x, "y": y, "size": 1}


def cmd_dist(args, st):
    a, b = resolve(st, args.a), resolve(st, args.b)
    return f"{args.a} ↔ {args.b}: {feet_between(a, b)} ft"


def cmd_threat(args, st):
    t = token(st, args.token)
    th = [o for o in st["tokens"] if threatens(o, t)]
    if not th:
        return f"{t['token']} is not threatened"
    out = [f"{t['token']} threatened by: {', '.join(label(o) for o in th)}"]
    pairs = [(label(a), label(b)) for i, a in enumerate(th) for b in th[i + 1:] if flanks(a, b, t)]
    if pairs:
        out.append("Flanked by: " + "; ".join(f"{a} + {b}" for a, b in pairs) + " (+2 melee for each)")
    return "\n".join(out)


def cmd_hp(args, st):
    c = token(st, args.token)
    c["hp"] = min(c["max_hp"], c["hp"] + int(args.delta))
    state = health(c) if c["hp"] > 0 else ("disabled" if c["hp"] == 0 else "dying / down")
    return f"{c['token']}: HP {c['hp']}/{c['max_hp']} ({state})"


def cmd_cond(args, st):
    c = token(st, args.token)
    if args.action == "add":
        c["conditions"].append(args.text)
    elif args.text in c["conditions"]:
        c["conditions"].remove(args.text)
    else:
        raise CombatError(f"{c['token']} has no condition '{args.text}'")
    return f"{c['token']}: {', '.join(c['conditions']) or 'no conditions'}"


def cmd_init(args, st):
    token(st, args.token)["init"] = args.value
    return f"{args.token} initiative → {args.value:g}"


def cmd_flag(args, st):
    c = token(st, args.token)
    if args.command == "remove":
        c["removed"] = True
    else:
        c["hidden"] = args.command == "hide"
    return f"{c['token']}: {args.command}"


def cmd_end(args, st):
    defeated = [c for c in st["tokens"] if c["side"] not in FRIENDLY and (c["hp"] <= 0 or c.get("removed"))]
    xp = sum(XP_BY_CR.get(str(c.get("cr")), 0) for c in defeated)
    out = [f"Encounter over after {st['round']} round(s)."]
    for c in st["tokens"]:
        status = "removed" if c.get("removed") else f"HP {c['hp']}/{c['max_hp']}"
        cr = f", CR {c['cr']}" if c.get("cr") else ""
        out.append(f"  {c['token']} {c['name']}: {status}{cr}")
    out.append(f"XP from defeated/removed enemies with CR: {xp} (check removed ones: fled ≠ defeated unless overcome)")
    path = state_path(args.campaign)
    archive = path.parent / "archive" / f"{datetime.now():%Y%m%d-%H%M}.json"
    archive.parent.mkdir(exist_ok=True)
    path.rename(archive)
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Combat tracker for Claude DM.")
    p.add_argument("-c", "--campaign", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    n = sub.add_parser("new"); n.add_argument("mapfile", nargs="?"); n.add_argument("--blank"); n.add_argument("--force", action="store_true")
    a = sub.add_parser("add")
    a.add_argument("token"); a.add_argument("name"); a.add_argument("--pos", required=True)
    a.add_argument("--init", type=float, required=True); a.add_argument("--hp", type=int, required=True)
    a.add_argument("--ac", type=int); a.add_argument("--side", choices=["enemy", "pc", "ally"], default="enemy")
    a.add_argument("--size", type=int, default=1, choices=[1, 2, 3, 4]); a.add_argument("--reach", type=int, default=5)
    a.add_argument("--speed", type=int, default=30); a.add_argument("--cr"); a.add_argument("--hidden", action="store_true")
    s = sub.add_parser("show"); s.add_argument("--dm", action="store_true")
    sub.add_parser("next")
    m = sub.add_parser("move"); m.add_argument("token"); m.add_argument("pos")
    d = sub.add_parser("dist"); d.add_argument("a"); d.add_argument("b")
    t = sub.add_parser("threat"); t.add_argument("token")
    h = sub.add_parser("hp"); h.add_argument("token"); h.add_argument("delta")
    c = sub.add_parser("cond"); c.add_argument("token"); c.add_argument("action", choices=["add", "remove"]); c.add_argument("text")
    i = sub.add_parser("init"); i.add_argument("token"); i.add_argument("value", type=float)
    for name in ("reveal", "hide", "remove"):
        sub.add_parser(name).add_argument("token")
    sub.add_parser("end")
    args = p.parse_args(argv)

    handlers = {"add": cmd_add, "next": cmd_next, "move": cmd_move, "dist": cmd_dist,
                "threat": cmd_threat, "hp": cmd_hp, "cond": cmd_cond, "init": cmd_init,
                "reveal": cmd_flag, "hide": cmd_flag, "remove": cmd_flag, "end": cmd_end}
    try:
        if args.command == "new":
            if not args.mapfile and not args.blank:
                raise CombatError("give a MAPFILE or --blank WxH")
            print(cmd_new(args))
            return 0
        st = load(args.campaign)
        if args.command == "show":
            print(render(st, dm=args.dm))
            return 0
        result = handlers[args.command](args, st)
        if args.command != "end":
            save(args.campaign, st)
        print(result)
    except CombatError as e:
        print(f"combat error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
