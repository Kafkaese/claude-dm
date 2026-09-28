#!/usr/bin/env python3
"""Combat tracker for Claude DM: grid map, tokens, initiative, HP, conditions.

The state lives in campaigns/<campaign>/dm/combat/current.json. Never edit the map by hand;
let this script render it and do the geometry (PF1e 5-10-5 diagonals, reach, flanking).

Usage: python3 scripts/combat.py -c CAMPAIGN COMMAND [args]

Setup
  new MAPFILE | --blank WxH       start an encounter from a terrain map (see below)
  add TOKEN NAME --pos D4 --init 15 --hp 11 [--ac 16] [--side enemy|pc|ally]
      [--size 1|2|3|4] [--reach 5] [--speed 30] [--cr 1/2] [--hidden] [--ref STATBLOCK.md]
      [--dr 5]                    hardness or damage reduction subtracted from every hit
      [--con 14]                  PCs and allies: Constitution score, so the log shows "dead" at -Con
                                  TOKEN is 1-2 chars: PCs uppercase (V), others lowercase+digit (g1)
Play
  show [--dm]                     player view (paste verbatim) / DM view (never paste)
  next                            advance to the next turn (starts a new round when needed)
  move TOKEN POS                  move along the cheapest legal path, report feet used
  dist A B                        distance between two tokens (or squares) in feet
  threat TOKEN                    who threatens TOKEN, and who flanks it
  attack ATT TGT --roll "1d20+9" --dmg "1d8+5" [--crit 19] [--mult 3] [--name slam] [--nonlethal]
                                  NPC attack: rolls d20, confirms threats, rolls damage only on a hit,
                                  applies the target's hardness/DR, updates HP, logs the result
  attack ATT TGT --total 17 --damage 9 [--nat 20|1] [--confirm 18] [--name rapier]
                                  PC attack with the player's reported numbers, against the hidden AC
       both: [--no-crit] (mercy: treat a crit as a normal hit)  [--ac N] (override)
  log "TEXT"                      add a player-safe line to the combat log
  events                          print combat log lines not shown yet (Claude Code UI mode)
  hp TOKEN DELTA                  e.g. hp g2 -7, hp V +5
  cond TOKEN add|remove TEXT      conditions, e.g. cond g2 add prone
  init TOKEN VALUE                change initiative (delay / ready)
  reveal TOKEN / hide TOKEN       toggle visibility to the players
  remove TOKEN                    take a token off the board (fled, dismissed)
  end                             finish the encounter: summary + XP, archive the state
  do "CMD" ["CMD" ...]            run several commands in one call, e.g.
                                  do "move g1 D4" "hp V -6" "next" "show"
  image [on|off]                  render the player view as players/combat-map.png (needs Pillow);
                                  'on' re-renders after every change, for a live VS Code tab

Map files: one line per row, one character per square, no spaces between squares.
  .  floor      #  wall (blocks)     +  door        ^  difficult (rubble, brush)
  ~  water (difficult)  T  trees (difficult)  _  pit / chasm (blocks)  (space) outside (blocks)
Columns are lettered A-Z (max 26 wide), rows numbered from 1.
Tokens: a PC uses the first letter of its name (Corin -> C); others lowercase + digit (g1, s1).

The combat log (events) is what the player sees about attacks, damage and conditions. play.py prints
new lines after every turn. The numbers shown: attack totals (against AC only for PCs and allies),
damage per hit (and what hardness/DR absorbed), PC/ally HP, enemy health in words.
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
                      f"CR {c['cr']}" if c.get("cr") else "", f"ref {c['ref']}" if c.get("ref") else ""]
        extra = "  ".join(e for e in extra if e)
        init = f"{c['init']:g}"
        out.append(f"{mark} {c['token']:<2} {c['name']:<18} {init:>4}  {hp:<16}{extra}".rstrip())
    return "\n".join(out)


# ---------- image ----------

CELL, LABEL, PANEL = 56, 30, 360
COLORS = {
    "bg": (38, 38, 44), "floor": (236, 226, 203), "grid": (178, 165, 140),
    "wall": (72, 72, 80), "wall_edge": (50, 50, 56), "pit": (14, 14, 18), "outside": (38, 38, 44),
    "difficult": (214, 196, 160), "hatch": (150, 118, 78), "water": (112, 164, 206),
    "wave": (170, 205, 232), "trees": (122, 160, 102), "tree": (70, 112, 64),
    "door": (140, 94, 50), "bridge": (176, 134, 88), "plank": (140, 100, 60),
    "pc": (58, 108, 200), "ally": (66, 148, 92), "enemy": (188, 58, 52), "fallen": (130, 130, 130),
    "ring": (242, 190, 40), "text": (235, 235, 235), "dim": (160, 160, 168),
}
FONT_PATHS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]


def font(size):
    from PIL import ImageFont
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def image_path(campaign):
    return PROJECT / "campaigns" / campaign / "players" / "combat-map.png"


def draw_square(d, ch, x0, y0):
    c, x1, y1 = COLORS, x0 + CELL, y0 + CELL
    base = {"#": "wall", "_": "pit", " ": "outside", "^": "difficult", "~": "water",
            "T": "trees", "=": "bridge"}.get(ch, "floor")
    d.rectangle([x0, y0, x1, y1], fill=c[base])
    if ch == "^":
        for k in range(-CELL, CELL, 12):
            d.line([x0 + k, y1, x0 + k + CELL, y0], fill=c["hatch"], width=2)
    elif ch == "~":
        for k in range(10, CELL, 14):
            d.arc([x0 + 6, y0 + k - 6, x0 + 26, y0 + k + 4], 200, 340, fill=c["wave"], width=2)
            d.arc([x0 + 28, y0 + k - 6, x0 + 48, y0 + k + 4], 200, 340, fill=c["wave"], width=2)
    elif ch == "T":
        for cx, cy, r in ((18, 20, 11), (38, 34, 13), (20, 42, 8)):
            d.ellipse([x0 + cx - r, y0 + cy - r, x0 + cx + r, y0 + cy + r], fill=c["tree"])
    elif ch == "+":
        d.rectangle([x0 + 6, y0 + CELL // 2 - 6, x1 - 6, y0 + CELL // 2 + 6], fill=c["door"])
    elif ch == "=":
        for k in range(0, CELL, 11):
            d.line([x0, y0 + k, x1, y0 + k], fill=c["plank"], width=2)
    elif ch == "#":
        d.rectangle([x0, y0, x1, y1], outline=c["wall_edge"], width=2)
    if base not in ("wall", "pit", "outside"):
        d.rectangle([x0, y0, x1, y1], outline=c["grid"], width=1)


_TILES = {}


def tile(ch):
    """One square as its own image, so patterns can't bleed into neighbours."""
    if ch not in _TILES:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (CELL + 1, CELL + 1), COLORS["bg"])
        draw_square(ImageDraw.Draw(im), ch, 0, 0)
        _TILES[ch] = im
    return _TILES[ch]


TERRAIN_NAMES = {"#": "wall", "+": "door", "^": "difficult", "~": "water", "T": "trees", "_": "pit", "=": "bridge"}


def render_image(st, path, panel=True):
    """The player view as a PNG. panel=False draws only the map (transparent margins, no round
    title, no initiative panel or legend), for interfaces that show those themselves."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise CombatError("image rendering needs Pillow: python3 -m pip install --user pillow")
    c = COLORS
    map_w, map_h = st["w"] * CELL, st["h"] * CELL
    shown = [t for t in order(st) if not t.get("removed") and not t.get("hidden")]
    f_lab, f_tok, f_txt, f_head = font(15), font(20), font(16), font(22)
    if not panel:
        top = 30
        img = Image.new("RGBA", (LABEL + map_w + 6, top + map_h + 6), (0, 0, 0, 0))
    else:
        top = 76
        panel_h = 70 + 34 * len(shown) + 140
        img = Image.new("RGB", (LABEL + map_w + 20 + PANEL, max(map_h + 20, panel_h) + 76), c["bg"])
    d = ImageDraw.Draw(img)
    if panel:
        d.text((LABEL, 12), f"Round {st['round']}", font=f_head, fill=c["text"])
    for i in range(st["w"]):
        d.text((LABEL + i * CELL + CELL // 2, top - 12), chr(ord("A") + i), font=f_lab, fill=c["dim"], anchor="mm")
    for j in range(st["h"]):
        d.text((LABEL // 2, top + j * CELL + CELL // 2), str(j + 1), font=f_lab, fill=c["dim"], anchor="mm")
    for j, row in enumerate(st["grid"]):
        for i, ch in enumerate(row):
            img.paste(tile(ch), (LABEL + i * CELL, top + j * CELL))
    for t in shown:
        x0, y0 = LABEL + t["x"] * CELL, top + t["y"] * CELL
        span = t["size"] * CELL
        box = [x0 + 6, y0 + 6, x0 + span - 6, y0 + span - 6]
        fallen = t["hp"] <= 0 and t["side"] not in FRIENDLY
        if t["token"] == st.get("turn"):
            d.ellipse([box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4], outline=c["ring"], width=5)
        d.ellipse(box, fill=c["fallen"] if fallen else c[t["side"]], outline=(255, 255, 255), width=3)
        if fallen:
            d.line([box[0] + 10, box[1] + 10, box[2] - 10, box[3] - 10], fill=(60, 60, 60), width=4)
            d.line([box[0] + 10, box[3] - 10, box[2] - 10, box[1] + 10], fill=(60, 60, 60), width=4)
        else:
            d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), t["token"], font=f_tok,
                   fill=(255, 255, 255), anchor="mm")
    if not panel:
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        return path
    # initiative panel
    px, py = LABEL + map_w + 20, top
    d.text((px, 12), "Initiative", font=f_head, fill=c["text"])
    for t in shown:
        cur = t["token"] == st.get("turn")
        if cur:
            d.rounded_rectangle([px - 4, py - 2, px + PANEL - 16, py + 28], radius=6, fill=(62, 62, 72))
            d.polygon([(px + 2, py + 6), (px + 2, py + 22), (px + 12, py + 14)], fill=c["ring"])
        fallen = t["hp"] <= 0 and t["side"] not in FRIENDLY
        d.ellipse([px + 18, py + 4, px + 38, py + 24], fill=c["fallen"] if fallen else c[t["side"]])
        d.text((px + 46, py + 14), f"{t['token']}  {t['name']}"[:22], font=f_txt, fill=c["text"], anchor="lm")
        hp = f"{t['hp']}/{t['max_hp']}" if t["side"] == "pc" else health(t)
        d.text((px + 225, py + 14), f"{t['init']:g}", font=f_txt, fill=c["dim"], anchor="rm")
        d.text((px + 237, py + 14), hp, font=f_txt, fill=c["text"], anchor="lm")
        if t.get("conditions"):
            py += 22
            d.text((px + 46, py + 14), ", ".join(t["conditions"])[:34], font=f_lab, fill=c["ring"], anchor="lm")
        py += 34
    # terrain legend
    used = {ch for row in st["grid"] for ch in row}
    py += 16
    for ch, name in TERRAIN_NAMES.items():
        if ch in used:
            img.paste(tile(ch).resize((22, 22)), (px + 18, py))
            d.text((px + 48, py + 11), name, font=f_lab, fill=c["dim"], anchor="lm")
            py += 28
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def maybe_image(args, st):
    if st.get("image"):
        render_image(st, image_path(args.campaign))


# ---------- combat log ----------

def event(st, text):
    st.setdefault("events", []).append({"round": st.get("round", 1), "text": text})


def who(c):
    return c["name"]


def status(c):
    if c["side"] in FRIENDLY:
        s = f"{c['hp']}/{c['max_hp']} HP"
        if c["hp"] == 0:
            s += ", disabled"
        elif c.get("con") and c["hp"] <= -c["con"]:
            s += ", dead"
        elif c["hp"] < 0:
            s += ", dying"
        return s
    return health(c)


def apply_damage(c, dmg, nonlethal=False):
    """Apply damage after hardness/DR. Returns (dealt, absorbed)."""
    dr = c.get("dr") or 0
    dealt = max(0, dmg - dr)
    absorbed = dmg - dealt
    if nonlethal:
        c["nonlethal"] = c.get("nonlethal", 0) + dealt
    else:
        c["hp"] -= dealt
    return dealt, absorbed


def _roll(expr):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import secrets
    from roll import evaluate
    total, detail, flags = evaluate(expr, secrets.SystemRandom())
    return total, detail, flags


def _natural(detail):
    """The d20 face from a roll.py detail string like '[17]+9'."""
    import re
    m = re.match(r"\[(\d+)\]", detail)
    return int(m.group(1)) if m else None


def cmd_attack(args, st):
    out = _attack(args, st)
    try:  # keep the roll log complete
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from roll import append_log
        append_log(args.campaign, [f"Combat: {l}" for l in out.splitlines()], True, None)
    except Exception:
        pass
    return out


def _attack(args, st):
    a, t = token(st, args.attacker), token(st, args.target)
    ac = args.ac if args.ac is not None else t.get("ac")
    if ac is None:
        raise CombatError(f"{t['token']} has no AC; pass --ac")
    weapon = f" ({args.name})" if args.name else ""
    reveal_note = ""
    if a.get("hidden"):
        a["hidden"] = False
        reveal_note = f"{who(a)} bursts from hiding! "
    dm, crit = [], False
    if args.roll:  # NPC attack: roll everything
        total, detail, _ = _roll(args.roll)
        nat = _natural(detail)
        dm.append(f"attack {args.roll} → {detail} = {total} vs AC {ac}")
        hit = nat != 1 and (nat == 20 or total >= ac)
        if hit and nat is not None and nat >= args.crit and not args.no_crit:
            ctotal, cdetail, _ = _roll(args.roll)
            cnat = _natural(cdetail)
            crit = cnat != 1 and (cnat == 20 or ctotal >= ac)
            dm.append(f"confirm → {cdetail} = {ctotal}: {'crit' if crit else 'no crit'}")
        shown_total = total
    else:          # PC attack: the player's numbers
        if args.total is None:
            raise CombatError("give --roll for an NPC attack, or --total for a PC attack")
        shown_total, nat = args.total, args.nat
        hit = nat != 1 and (nat == 20 or args.total >= ac)
        if hit and args.confirm is not None and not args.no_crit:
            crit = args.confirm >= ac
            dm.append(f"confirm {args.confirm} vs AC {ac}: {'crit' if crit else 'no crit'}")
        dm.append(f"attack {args.total} vs AC {ac}")
    vs = f" vs AC {ac}" if t["side"] in FRIENDLY else ""
    line = f"{reveal_note}{who(a)}{weapon} → {who(t)}: {shown_total}{vs}"
    if nat == 20:
        line += " (natural 20)"
    elif nat == 1:
        line += " (natural 1)"
    if not hit:
        event(st, line + " — miss")
        return "\n".join(dm + [f"MISS. Log: {line} — miss"])
    if args.dmg:
        times = args.mult if crit else 1
        dmg, parts = 0, []
        for _ in range(times):
            d, ddetail, _ = _roll(args.dmg)
            dmg += d
            parts.append(ddetail)
        dm.append(f"damage {args.dmg} x{times} → {' + '.join(parts)} = {dmg}")
    elif args.damage is not None:
        dmg = args.damage
    else:
        raise CombatError("give --dmg (NPC) or --damage (PC) for the damage")
    dealt, absorbed = apply_damage(t, dmg, args.nonlethal)
    kind = " nonlethal" if args.nonlethal else ""
    res = f" — {'critical hit' if crit else 'hit'}, {dmg}{kind} damage"
    if absorbed:
        res += f" ({absorbed} absorbed, {dealt} gets through)" if dealt else " (all of it absorbed)"
    res += f" [{who(t)}: {status(t)}]"
    event(st, line + res)
    return "\n".join(dm + [f"HIT. HP {t['hp']}/{t['max_hp']}. Log: {line}{res}"])


def cmd_log(args, st):
    event(st, args.text)
    return f"Logged: {args.text}"


def cmd_events(args, st):
    evs = st.get("events", [])
    start = 0 if args.all else st.get("events_shown", 0)
    st["events_shown"] = len(evs)
    lines = [f"R{e['round']}: {e['text']}" for e in evs[start:]]
    return "\n".join(lines) if lines else "(no new combat log lines)"


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
         "hidden": args.hidden, "conditions": [], "ref": args.ref, "dr": args.dr, "con": args.con}
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
    delta = int(args.delta)
    c["hp"] = min(c["max_hp"], c["hp"] + delta)
    state = health(c) if c["hp"] > 0 else ("disabled" if c["hp"] == 0 else "dying / down")
    if not c.get("hidden"):
        why = f" ({args.why})" if args.why else ""
        if c["side"] in FRIENDLY:
            event(st, f"{who(c)}: {'+' if delta > 0 else ''}{delta} HP{why} [{status(c)}]")
        else:
            event(st, f"{who(c)} {'recovers' if delta > 0 else 'takes damage'}{why} [{status(c)}]")
    return f"{c['token']}: HP {c['hp']}/{c['max_hp']} ({state})"


def cmd_cond(args, st):
    c = token(st, args.token)
    if args.action == "add":
        c["conditions"].append(args.text)
        if not c.get("hidden"):
            event(st, f"{who(c)} is {args.text}")
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
        if args.command == "reveal":
            event(st, f"{who(c)} appears!")
    return f"{c['token']}: {args.command}"


def cmd_image(args, st):
    if args.mode:
        st["image"] = args.mode == "on"
    path = render_image(st, image_path(args.campaign))
    rel = path.relative_to(PROJECT)
    return f"Rendered {rel}" + (f" (auto-render {args.mode})" if args.mode else "")


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
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", "--campaign", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    n = sub.add_parser("new"); n.add_argument("mapfile", nargs="?"); n.add_argument("--blank"); n.add_argument("--force", action="store_true")
    a = sub.add_parser("add")
    a.add_argument("token"); a.add_argument("name"); a.add_argument("--pos", required=True)
    a.add_argument("--init", type=float, required=True); a.add_argument("--hp", type=int, required=True)
    a.add_argument("--ac", type=int); a.add_argument("--side", choices=["enemy", "pc", "ally"], default="enemy")
    a.add_argument("--size", type=int, default=1, choices=[1, 2, 3, 4]); a.add_argument("--reach", type=int, default=5)
    a.add_argument("--speed", type=int, default=30); a.add_argument("--cr"); a.add_argument("--hidden", action="store_true")
    a.add_argument("--ref", help="path to the stat block file (DM view only)")
    a.add_argument("--dr", type=int, default=0, help="hardness or damage reduction")
    a.add_argument("--con", type=int, help="Constitution score (PCs/allies): dead at -Con HP")
    at = sub.add_parser("attack"); at.add_argument("attacker"); at.add_argument("target")
    at.add_argument("--roll"); at.add_argument("--dmg"); at.add_argument("--crit", type=int, default=20)
    at.add_argument("--mult", type=int, default=2); at.add_argument("--total", type=int)
    at.add_argument("--damage", type=int); at.add_argument("--nat", type=int, choices=[1, 20])
    at.add_argument("--confirm", type=int); at.add_argument("--name"); at.add_argument("--ac", type=int)
    at.add_argument("--nonlethal", action="store_true"); at.add_argument("--no-crit", action="store_true")
    lg = sub.add_parser("log"); lg.add_argument("text")
    ev = sub.add_parser("events"); ev.add_argument("--all", action="store_true")
    s = sub.add_parser("show"); s.add_argument("--dm", action="store_true")
    sub.add_parser("next")
    m = sub.add_parser("move"); m.add_argument("token"); m.add_argument("pos")
    d = sub.add_parser("dist"); d.add_argument("a"); d.add_argument("b")
    t = sub.add_parser("threat"); t.add_argument("token")
    h = sub.add_parser("hp"); h.add_argument("token"); h.add_argument("delta"); h.add_argument("--why")
    c = sub.add_parser("cond"); c.add_argument("token"); c.add_argument("action", choices=["add", "remove"]); c.add_argument("text")
    i = sub.add_parser("init"); i.add_argument("token"); i.add_argument("value", type=float)
    for name in ("reveal", "hide", "remove"):
        sub.add_parser(name).add_argument("token")
    sub.add_parser("end")
    im = sub.add_parser("image"); im.add_argument("mode", nargs="?", choices=["on", "off"])
    dp = sub.add_parser("do"); dp.add_argument("cmds", nargs="+")
    args = p.parse_args(argv)

    handlers = {"add": cmd_add, "next": cmd_next, "move": cmd_move, "dist": cmd_dist,
                "threat": cmd_threat, "hp": cmd_hp, "cond": cmd_cond, "init": cmd_init,
                "reveal": cmd_flag, "hide": cmd_flag, "remove": cmd_flag, "end": cmd_end,
                "image": cmd_image, "attack": cmd_attack, "log": cmd_log, "events": cmd_events}
    if args.command == "do":
        import shlex
        for c in args.cmds:
            print(f"$ {c}")
            rc = main(["-c", args.campaign] + shlex.split(c))
            if rc:
                return rc
        return 0
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
            if args.command not in ("image", "dist", "threat"):
                maybe_image(args, st)
            save(args.campaign, st)
        print(result)
    except CombatError as e:
        print(f"combat error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
