#!/usr/bin/env python3
"""Combat tracker for Claude DM: grid map, tokens, initiative, HP, conditions.

The state lives in campaigns/<campaign>/dm/combat/current.json. Never edit the map by hand;
let this script render it and do the geometry (PF1e 5-10-5 diagonals, reach, flanking).

Usage: python3 scripts/combat.py -c CAMPAIGN COMMAND [args]

Setup
  new MAPFILE | --blank WxH       start an encounter from a terrain map (see below)
  add TOKEN NAME --pos D4 --ref STATBLOCK.md --init roll [--side enemy|pc|ally] [--hidden] [--cr 1/2]
                                  With --ref, the file's ```combat-profile block supplies HP, AC,
                                  touch/flat-footed AC, saves, attacks, speed, reach, size, DR, Con,
                                  feats; --init roll rolls d20 + its init. Anything given overrides:
      [--init 15] [--hp 11] [--ac 16] [--touch 12] [--ff 14] [--size 1|2|3|4] [--reach 5]
      [--speed 30] [--dr 5] [--con 14] [--profile '{json}']
                                  TOKEN is 1-2 chars: PCs uppercase (C), others lowercase+digit (g1)
Play
  show [--dm]                     player view (paste verbatim) / DM view (never paste)
  next                            advance the turn pointer. Also: ends expiring conditions, applies
                                  ongoing damage, resets AoOs and movement, reminds of dying checks.
                                  In web/terminal play (CLAUDE_DM_MODE=play) only the interface runs it.
  endturn C                       the player ended the PC's turn (in words other than the go signal,
                                  or together with their actions): the interface plays the next step
  maneuver ATT TGT KIND [--total N] [--charge] [--grab] [--aoo] [--condition X] [--to SQ] [--item X]
                                  combat maneuver: bull-rush dirty-trick disarm drag grapple overrun
                                  reposition steal sunder trip, plus escape and release. NPCs roll their
                                  profile CMB (cmb_vs per maneuver), PCs give --total. Provokes from the
                                  target unless the Improved feat/--grab (a PC target: question, then
                                  rerun with --aoo-damage N). Grapple again = maintain (+5), with
                                  --option pin|damage|move|tie; grapples are tracked and end when a
                                  party drops or isn't maintained
  Actor lock: attack, move, cast, sla, provoke and area --from only work for the creature the
  pointer is on. Exempt: attack --aoo, and --out-of-turn (readied/immediate actions, forced
  movement, repositioning during setup).
  move TOKEN POS [--step]         move along the cheapest legal path; tracks feet used this turn.
                                  Leaving threatened squares: NPC attacks of opportunity are rolled
                                  automatically (--no-aoo to skip); a PC's chance to take one opens a
                                  question (ask) unless its standing order says otherwise
  dist A B                        distance between two tokens (or squares) in feet
  threat TOKEN                    who threatens TOKEN, and who flanks it
  attack ATT TGT --with spear [--full] [--charge] [--touch] [--aoo] [--nonlethal]
                                  NPC attack from its profile. Applies situational modifiers itself:
                                  flanking, conditions (shaken, prone, …), charge, flat-footed/touch AC,
                                  range increments, firing into melee (unless Precise Shot), cover
                                  (walls; creatures for ranged), concealment miss chance. Rolls damage
                                  only on a hit, confirms crits, applies DR, updates HP, logs it.
  attack ATT TGT --roll "1d20+9" --dmg "1d8+5" [--crit 19] [--mult 3] [--name slam]
                                  NPC attack without a profile (the same modifiers are added)
  attack ATT TGT --total 17 --damage 9 [--nat 20|1] [--confirm 18] [--name rapier] [--touch]
                                  PC attack with the player's numbers against the hidden AC (target-side
                                  modifiers applied; attacker-side ones are listed as reminders)
       all: [--no-crit] (mercy: treat a crit as a normal hit)  [--ac N] (override)
  area burst|cone|line FEET (--at D4 | --from TOKEN --toward E5) [--save ref --dc 13 --dmg 2d6
       [--half] [--name "burning hands"]]
                                  which tokens a template covers; with --save, rolls the damage once,
                                  saves for NPCs from their profiles, and opens a question for PC saves
  save TOKEN fort|ref|will --dc N [--total N]
                                  NPC: rolled from the profile. PC: the player's total. Resolves a
                                  pending area-effect save for that token, if there is one
  stabilize TOKEN [--total N]     dying check: DC 10, minus the negative HP total (the PC's --total;
                                  NPCs roll). Failure costs 1 HP; success adds "stable"
  order TOKEN aoo always|never|ask
                                  a PC's standing order for attacks of opportunity
  cast TOKEN "SPELL" [--level N] [--class X] [--defensive] [--no-provoke]
                                  an NPC casts: checks and spends a slot (spontaneous) or a prepared copy,
                                  provokes AoOs when threatened (or --defensive: concentration DC 15+2x
                                  level), concentration after damage, reports the save DC. The log only
                                  says "casts a spell" (identifying it is a Spellcraft matter)
  sla TOKEN "NAME" [--defensive] [--no-provoke]
                                  the same for a spell-like ability (uses per day)
  spells TOKEN                    remaining slots, prepared spells and SLA uses (DM view)
  provoke TOKEN [--reason "drinking a potion"]
                                  resolve the AoOs a creature provokes right now (e.g. a PC casting)
  profile check FILE [FILE …]     validate combat-profile blocks against the system's schema
                                  (library/<system>/combat-profile.schema.json); add does it too
  log "TEXT"                      add a player-safe line to the combat log
  ask "QUESTION"                  mark that the DM waits for a player decision mid-round (a reaction,
                                  an AoO, a stabilization check). Pauses auto-combat in the web UI;
                                  cleared by the next state-changing command (or: ask --clear)
  events                          print combat log lines not shown yet (Claude Code UI mode)
  hp TOKEN DELTA                  e.g. hp g2 -7, hp V +5
  cond TOKEN add NAME [--rounds N] [--atk N --ac N --save N --dmg N] [--ongoing "1d6"]
  cond TOKEN remove NAME          conditions and effects. Known conditions (shaken, prone, blinded,
                                  invisible, …) apply their modifiers automatically; custom effects take
                                  explicit ones (e.g. bless: --atk 1 --rounds 30). With --rounds they end
                                  by themselves; --ongoing damage is rolled at the start of its turn
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
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import combat_rules as R  # noqa: E402

Token = R.Token    # one combatant in the combat state
State = R.State    # the whole combat state (dm/combat/current.json)
Square = R.Square  # (x, y) grid coordinates, 0-based
Args = argparse.Namespace

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
    """A combat command that can't be carried out; the message explains why."""
    pass


# ---------- state ----------

def state_path(campaign: str) -> Path:
    """The path of the campaign's current.json.

    Raises:
        CombatError: if the campaign doesn't exist.
    """
    dm = PROJECT / "campaigns" / campaign / "dm"
    if not dm.is_dir():
        raise CombatError(f"no such campaign: {campaign}")
    return dm / "combat" / "current.json"


def load(campaign: str) -> State:
    """Load the active encounter.

    Raises:
        CombatError: if there is none.
    """
    path = state_path(campaign)
    if not path.exists():
        raise CombatError("no active encounter; start one with 'new'")
    return json.loads(path.read_text(encoding="utf-8"))


def save(campaign: str, st: State) -> None:
    """Write the encounter state back to current.json."""
    path = state_path(campaign)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, indent=1), encoding="utf-8")


def token(st: State, tok: str) -> Token:
    """The token with this id.

    Raises:
        CombatError: if there is no such token.
    """
    for c in st["tokens"]:
        if c["token"] == tok:
            return c
    raise CombatError(f"no token '{tok}'")


# ---------- geometry ----------

def parse_pos(s: str, st: State | None = None) -> Square:
    """Parse a square like 'D4' into 0-based (x, y), checking it's on the map if `st` is given."""
    s = s.strip().upper()
    if len(s) < 2 or not s[0].isalpha() or not s[1:].isdigit():
        raise CombatError(f"bad square '{s}', expected e.g. D4")
    x, y = ord(s[0]) - ord("A"), int(s[1:]) - 1
    if st and not (0 <= x < st["w"] and 0 <= y < st["h"]):
        raise CombatError(f"square {s} is off the map")
    return x, y


def fmt_pos(x: int, y: int) -> str:
    """Format 0-based coordinates as a square name like 'D4'."""
    return f"{chr(ord('A') + x)}{y + 1}"


def cells(c: Token, at: Square | None = None) -> list[Square]:
    """The squares a token occupies, at its position or at `at`."""
    x, y = at or (c["x"], c["y"])
    return [(x + i, y + j) for i in range(c["size"]) for j in range(c["size"])]


def sq_dist(a: Square, b: Square) -> int:
    """Distance in squares, PF1e style (every second diagonal counts double)."""
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + min(dx, dy) // 2


def feet_between(c1: Token, c2: Token) -> int:
    """Shortest distance in feet between two tokens."""
    return 5 * min(sq_dist(a, b) for a in cells(c1) for b in cells(c2))


def cost(st: State, x: int, y: int) -> int | None:
    """Movement cost multiplier of a square (1 or 2), or None if it blocks movement or is off the map."""
    if not (0 <= x < st["w"] and 0 <= y < st["h"]):
        return None
    return TERRAIN.get(st["grid"][y][x], ("?", 1))[1]


def label(c: Token) -> str:
    """The token id for DM output, tagged [HIDDEN] if the players can't see it."""
    return c["token"] + (" [HIDDEN]" if c.get("hidden") else "")


def active(c: Token) -> bool:
    """Whether the token is still in the fight (not removed, above 0 HP)."""
    return not c.get("removed") and c["hp"] > 0


def blocked_by_hostile(st: State, mover: Token, x: int, y: int) -> bool:
    """Whether an active enemy of the mover stands on the square."""
    for o in st["tokens"]:
        if o is mover or not active(o) or o["token"] in mover.get("overrun_through", []):
            continue
        if (o["side"] in FRIENDLY) != (mover["side"] in FRIENDLY) and (x, y) in cells(o):
            return True
    return False


def occupied(st: State, mover: Token, x: int, y: int) -> bool:
    """Whether any other token stands on the square."""
    return any(o is not mover and not o.get("removed") and (x, y) in cells(o) for o in st["tokens"])


def path_cost(st: State, mover: Token, dest: Square) -> int:
    """Cheapest legal move in feet (Dijkstra over (x, y, diagonal parity))."""
    import heapq
    start = (mover["x"], mover["y"])

    def footprint_ok(x: int, y: int, final: bool) -> bool:
        """Whether the mover's whole footprint fits at (x, y); the final square must also be unoccupied."""
        for cx, cy in cells(mover, (x, y)):
            if cost(st, cx, cy) is None or blocked_by_hostile(st, mover, cx, cy):
                return False
            if final and occupied(st, mover, cx, cy):
                return False
        return True

    def step_cost(x: int, y: int) -> int:
        """The highest movement cost under the mover's footprint at (x, y)."""
        return max(cost(st, cx, cy) or 1 for cx, cy in cells(mover, (x, y)))   # footprint_ok ruled out None

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


def threatens(a: Token, t: Token) -> bool:
    """Whether `a` threatens `t`: active, hostile to it, and within reach (reach-10 diagonal rule included)."""
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


def flanks(a: Token, b: Token, t: Token) -> bool:
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

    def edges(tt: float) -> set[str]:
        """Which borders of the target's space (L, R, T, B) the line touches at parameter tt."""
        px, py = ax + tt * dx, ay + tt * dy
        return {e for e, hit in (("L", abs(px - x0) < eps), ("R", abs(px - x1) < eps),
                                 ("T", abs(py - y0) < eps), ("B", abs(py - y1) < eps)) if hit}
    e0, e1 = edges(t0), edges(t1)
    return ("L" in e0 and "R" in e1) or ("R" in e0 and "L" in e1) or \
           ("T" in e0 and "B" in e1) or ("B" in e0 and "T" in e1)


# ---------- rendering ----------

def health(c: Token) -> str:
    """Health as a word for the players: unhurt, scratched, hurt, bloodied, barely standing, down."""
    if c.get("removed"):
        return "gone"
    if c["hp"] <= 0:
        return "down"
    r = c["hp"] / max(c["max_hp"], 1)
    return ("unhurt" if r >= 1 else "scratched" if r > 0.75 else "hurt" if r > 0.5
            else "bloodied" if r > 0.25 else "barely standing")


def order(st: State) -> list[Token]:
    """Tokens in initiative order (ties: the higher initiative modifier first)."""
    return sorted(st["tokens"], key=lambda c: (-c["init"], -c.get("init_tb", 0)))


def render(st: State, dm: bool = False) -> str:
    """The ASCII map and initiative list. The player view hides hidden tokens and exact enemy HP."""
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
        if R.conditions(c):
            extra.append(", ".join(R.labels(c, st)))
        if dm:
            extra += [f"AC {c['ac']}" if c.get("ac") else "", "hidden" if c.get("hidden") else "",
                      f"CR {c['cr']}" if c.get("cr") else "", f"ref {c['ref']}" if c.get("ref") else ""]
        extras = "  ".join(e for e in extra if e)
        init = f"{c['init']:g}"
        out.append(f"{mark} {c['token']:<2} {c['name']:<18} {init:>4}  {hp:<16}{extras}".rstrip())
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


def font(size: int) -> Any:
    """A TrueType font at this size for the PNG renderer (falls back to Pillow's default font)."""
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


def image_path(campaign: str) -> Path:
    """Where the PNG player view is written (players/combat-map.png)."""
    return PROJECT / "campaigns" / campaign / "players" / "combat-map.png"


def draw_square(d: Any, ch: str, x0: int, y0: int) -> None:
    """Draw one terrain square with its pattern onto a Pillow ImageDraw."""
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


_TILES: dict[str, Any] = {}


def tile(ch: str) -> Any:
    """One square as its own image, so patterns can't bleed into neighbours."""
    if ch not in _TILES:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (CELL + 1, CELL + 1), COLORS["bg"])
        draw_square(ImageDraw.Draw(im), ch, 0, 0)
        _TILES[ch] = im
    return _TILES[ch]


TERRAIN_NAMES = {"#": "wall", "+": "door", "^": "difficult", "~": "water", "T": "trees", "_": "pit", "=": "bridge"}


def render_image(st: State, path: Path, panel: bool = True) -> Path:
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
            d.text((px + 46, py + 14), ", ".join(R.labels(t, st))[:34], font=f_lab, fill=c["ring"], anchor="lm")
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


def maybe_image(args: Args, st: State) -> None:
    """Re-render the PNG if the table turned the image view on."""
    if st.get("image"):
        render_image(st, image_path(args.campaign))


# ---------- combat log ----------

def event(st: State, text: str) -> None:
    """Add a player-safe line to the combat log."""
    st.setdefault("events", []).append({"round": st.get("round", 1), "text": text})


def who(c: Token) -> str:
    """The name the players see for a token."""
    return c["name"]


def status(c: Token) -> str:
    """Health for the log: exact HP (with disabled/dying/dead) for PCs and allies, a word for enemies."""
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


def apply_damage(c: Token, dmg: int, nonlethal: bool = False) -> tuple[int, int]:
    """Apply damage after hardness/DR. Returns (dealt, absorbed)."""
    dr = c.get("dr") or 0
    dealt = max(0, dmg - dr)
    absorbed = dmg - dealt
    if nonlethal:
        c["nonlethal"] = c.get("nonlethal", 0) + dealt
    else:
        c["hp"] -= dealt
    return dealt, absorbed


def _roll(expr: str) -> tuple[int, str, list[str]]:
    """Roll a dice expression with roll.py's evaluator. Returns (total, detail, flags)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import secrets
    from roll import evaluate
    total, detail, flags = evaluate(expr, secrets.SystemRandom())
    return total, detail, flags


def _natural(detail: str) -> int | None:
    """The d20 face from a roll.py detail string like '[17]+9'."""
    import re
    m = re.match(r"\[(\d+)\]", detail)
    return int(m.group(1)) if m else None


def cmd_attack(args: Args, st: State) -> str:
    """The attack command: resolve the attack(s) and keep the roll log complete."""
    out = _attack(args, st)
    try:  # keep the roll log complete
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from roll import append_log
        append_log(args.campaign, [f"Combat: {l}" for l in out.splitlines()], True, None)
    except Exception:
        pass
    return out


def flanking(st: State, a: Token, t: Token) -> bool:
    """Whether `a` flanks `t` with an ally that also threatens it."""
    return any(threatens(o, t) and o is not a and flanks(a, o, t)
               for o in st["tokens"] if (o["side"] in FRIENDLY) == (a["side"] in FRIENDLY))


def attack_mods(st: State, a: Token, t: Token, kind: str, touch: bool = False, charge: bool = False, weapon: dict[str, Any] | None = None) -> tuple[int, int, list[str], list[str], int]:
    """Situational modifiers for one attack. Returns (attacker delta, target AC, log notes,
    DM notes, miss chance %). kind is 'melee' or 'ranged'."""
    atk, notes, dmnotes = 0, [], []
    # attacker side: flat condition modifiers plus a changed Str/Dex modifier (e.g. grappled -4 Dex)
    ab = R.attack_ability(weapon, kind)
    cond_atk = R.total(a, "atk") + R.mod_change(a, ab)
    if cond_atk:
        atk += cond_atk
        names = R.condition_names(a, ("atk", ab, f"{ab}_zero"))
        notes.append(f"{cond_atk:+d} {', '.join(names) or 'conditions'}")
    if kind == "melee" and R.flag(a, "prone"):
        atk -= 4
        notes.append("-4 attacking prone")
    if charge:
        atk += 2
        notes.append("+2 charge")
    if kind == "melee" and flanking(st, a, t):
        atk += 2
        notes.append("+2 flanking")
    feats = [f.lower() for f in ((a.get("profile") or {}).get("feats") or [])]
    if kind == "ranged":
        if R.in_melee_with_friend_of(st, t, a) and "precise shot" not in feats:
            atk -= 4
            notes.append("-4 into melee")
        rng = (weapon or {}).get("range")
        if rng:
            dist = feet_between(a, t)
            inc = max(0, math.ceil(dist / rng) - 1)
            if inc:
                atk -= 2 * inc
                notes.append(f"-{2 * inc} range")
            limit = 5 if (weapon or {}).get("thrown") else 10
            if inc >= limit:
                dmnotes.append(f"out of range: {dist} ft is beyond {limit} range increments")
    # target side
    if t.get("ac") is None:
        raise CombatError(f"{t['token']} has no AC; pass --ac or give it a profile")
    dfn = R.defenses(t)   # AC, touch and flat-footed AC with the Dex effects of conditions
    base = dfn["ac"] or 0
    uncanny = bool((t.get("profile") or {}).get("uncanny_dodge"))
    flat = R.flag(t, "flatfooted") or (not t.get("acted") and not uncanny)
    ac, label = base, ""
    if touch:
        ac, label = (dfn["touch"] if dfn["touch"] is not None else base), "touch "
        if flat and dfn["ff"] is not None:
            ac = min(ac, dfn["ff"])
    elif flat and dfn["ff"] is not None:
        ac, label = dfn["ff"], "flat-footed "
    elif flat:
        dmnotes.append(f"{t['token']} is flat-footed but has no flat-footed AC; base AC used")
    if label:
        notes.append(label.strip())
    ac += R.total(t, "ac")
    ac_conds = R.condition_names(t, ("ac", "dex", "dex_zero"))
    if ac_conds:
        notes.append("target " + ", ".join(ac_conds))
    if R.mod_change(t, "dex") and not R.scores(t, "dex")[2]:
        dmnotes.append(f"{t['token']} has no Dex score in its profile: Dex 10 assumed for its condition")
    if R.flag(t, "prone"):
        ac += 4 if kind == "ranged" else -4
        notes.append("target prone")
    if kind == "melee" and R.flag(t, "helpless"):
        ac -= 4
        notes.append("target helpless")
    if R.cover(st, a, t):
        ac += 4
        notes.append("cover")
    elif kind == "ranged" and R.soft_cover(st, a, t):
        ac += 4
        notes.append("soft cover")
    miss = max((R.cond_effects(x).get("concealment", 0) for x in R.conditions(t)), default=0)
    if miss:
        notes.append(f"{miss}% concealment")
    return atk, ac, notes, dmnotes, miss


def _attack(args: Args, st: State) -> str:
    """Work out which attacks are made (profile --with/--full, raw --roll, or the PC's --total) and resolve each."""
    a, t = token(st, args.attacker), token(st, args.target)
    if args.aoo:
        why = aoo_blocked(a)
        if why:
            raise CombatError(f"{a['token']} can't make attacks of opportunity: {why}")
    prof = a.get("profile") or {}
    # (label, bonus, damage expr, crit, mult, kind, weapon dict)
    entries: list[tuple[str | None, int | None, str | None, int, int, str, dict[str, Any] | None]] = []
    if args.total is not None:
        entries.append((args.name, None, None, 20, 2, "ranged" if args.ranged else "melee", None))
    elif args.roll:
        m = re.match(r"^\s*1?d20\s*([+-]\s*\d+)?\s*$", args.roll)
        if not m:
            raise CombatError("--roll must look like 1d20+5")
        bonus = int((m.group(1) or "+0").replace(" ", ""))
        entries.append((args.name, bonus, args.dmg, args.crit, args.mult,
                        "ranged" if args.ranged else "melee", {"range": args.range_inc}))
    else:
        names: list[str] = prof["full_attack"] if args.full and prof.get("full_attack") else [args.with_]
        for n in names:
            key, w = R.find_attack(prof, n)
            if not w:
                known = ", ".join((prof.get("attacks") or {}).keys()) or "none"
                raise CombatError(f"{a['token']} has no attack '{n}' (profile attacks: {known}); "
                                  f"or pass --roll/--dmg")
            bonuses = w["bonus"] if isinstance(w["bonus"], list) else [w["bonus"]]
            if not (args.full and not prof.get("full_attack")):
                bonuses = bonuses[:1]
            for b in bonuses:
                entries.append((key, b, w["damage"], w.get("crit", 20), w.get("mult", 2),
                                w.get("type", "melee"), w))
    out = []
    if args.aoo:
        a["aoo_used"] = a.get("aoo_used", 0) + 1
    if args.charge:
        R.add_condition(st, a, "charged", rounds=1)
    for i, e in enumerate(entries):
        if i and t["hp"] <= 0:
            out.append(f"(remaining attacks skipped: {who(t)} is down)")
            break
        out.append(_attack_once(args, st, a, t, *e))
    return "\n".join(out)


def _attack_once(args: Args, st: State, a: Token, t: Token, name: str | None, bonus: int | None, dmg_expr: str | None, crit_at: int, mult: int, kind: str, weapon: dict[str, Any] | None) -> str:
    """Resolve one attack: situational modifiers, the roll (or the PC's total) against the adjusted AC,
    crit confirmation, concealment, damage and DR. Writes the combat log line; returns the DM report.
    """
    atk_delta, ac, notes, dmnotes, miss = attack_mods(st, a, t, kind, args.touch, args.charge, weapon)
    if args.ac is not None:
        ac = args.ac
    weapon_label = f" ({name})" if name else ""
    prefix = "Attack of opportunity: " if args.aoo else ""
    if a.get("hidden"):
        a["hidden"] = False
        prefix = f"{who(a)} bursts from hiding! " + prefix
    dm, crit = list(dmnotes), False
    if bonus is not None:   # NPC: roll everything, with the situational modifiers
        expr = f"1d20{bonus + atk_delta:+d}"
        total_a, detail, _ = _roll(expr)
        nat = _natural(detail)
        dm.append(f"attack {expr} (base {bonus:+d}{', ' + ', '.join(notes) if notes else ''}) → {detail} = {total_a} vs AC {ac}")
        hit = nat != 1 and (nat == 20 or total_a >= ac)
        if hit and nat is not None and nat >= crit_at and not args.no_crit:
            ctotal, cdetail, _ = _roll(expr)
            cnat = _natural(cdetail)
            crit = cnat != 1 and (cnat == 20 or ctotal >= ac)
            dm.append(f"confirm → {cdetail} = {ctotal}: {'crit' if crit else 'no crit'}")
        shown = total_a
    else:                   # PC: the player's total against the adjusted AC
        shown, nat = args.total, args.nat
        attacker_side = [n for n in notes if n.startswith(("+", "-"))]
        if attacker_side:
            dm.append(f"reminder: {', '.join(attacker_side)} applies to the player's roll; "
                      f"check they included it")
        hit = nat != 1 and (nat == 20 or shown >= ac)
        if hit and args.confirm is not None and not args.no_crit:
            crit = args.confirm >= ac
            dm.append(f"confirm {args.confirm} vs AC {ac}: {'crit' if crit else 'no crit'}")
        dm.append(f"attack {shown} vs AC {ac}" + (f" ({', '.join(notes)})" if notes else ""))
        notes = [n for n in notes if n not in attacker_side]
    vs = f" vs AC {ac}" if t["side"] in FRIENDLY else ""
    tag = f" ({', '.join(notes)})" if notes else ""
    line = f"{prefix}{who(a)}{weapon_label} → {who(t)}: {shown}{vs}{tag}"
    if nat == 20:
        line += " (natural 20)"
    elif nat == 1:
        line += " (natural 1)"
    if hit and miss:
        mroll, _, _ = _roll("1d100")
        dm.append(f"miss chance {miss}%: d% {mroll}")
        if mroll <= miss:
            event(st, line + f" — would hit, but misses (concealment, rolled {mroll})")
            return "\n".join(dm + [f"MISS (concealment). Log: {line}"])
    if not hit:
        event(st, line + " — miss")
        return "\n".join(dm + [f"MISS. Log: {line} — miss"])
    if dmg_expr:
        dmg_mod = R.total(a, "dmg") + R.str_damage_change(a, weapon, kind)
        times = mult if crit else 1
        dmg, parts = 0, []
        for _ in range(times):
            d, ddetail, _ = _roll(dmg_expr)
            dmg += d
            parts.append(ddetail)
        if dmg_mod:
            dmg = max(1, dmg + dmg_mod * times)
            parts.append(f"{dmg_mod * times:+d} conditions")
        dm.append(f"damage {dmg_expr} x{times} → {' + '.join(parts)} = {dmg}")
    elif args.damage is not None:
        dmg = args.damage
    else:
        raise CombatError("give --dmg (NPC) or --damage (PC) for the damage")
    dealt, absorbed = apply_damage(t, dmg, args.nonlethal)
    kind_l = " nonlethal" if args.nonlethal else ""
    res = f" — {'critical hit' if crit else 'hit'}, {dmg}{kind_l} damage"
    if absorbed:
        res += f" ({absorbed} absorbed, {dealt} gets through)" if dealt else " (all of it absorbed)"
    res += f" [{who(t)}: {status(t)}]"
    event(st, line + res)
    return "\n".join(dm + [f"HIT. HP {t['hp']}/{t['max_hp']}. Log: {line}{res}"])


def cmd_ask(args: Args, st: State) -> str:
    """Set (or clear) the open question that pauses auto-combat."""
    if args.clear or not args.question:
        st.pop("awaiting", None)
        return "No open question."
    st["awaiting"] = args.question
    return f"Waiting for the player: {args.question}"


def cmd_log(args: Args, st: State) -> str:
    """Add a free-text line to the combat log."""
    event(st, args.text)
    return f"Logged: {args.text}"


def cmd_events(args: Args, st: State) -> str:
    """Print combat-log lines not shown yet (or all with --all)."""
    evs = st.get("events", [])
    start = 0 if args.all else st.get("events_shown", 0)
    st["events_shown"] = len(evs)
    lines = [f"R{e['round']}: {e['text']}" for e in evs[start:]]
    return "\n".join(lines) if lines else "(no new combat log lines)"


# ---------- commands ----------

def cmd_new(args: Args) -> str:
    """Start an encounter from a map file or a blank grid."""
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


def cmd_add(args: Args, st: State) -> str:
    """Add a combatant, taking its numbers from a validated combat profile (and a PC's HP from its sheet)."""
    if len(args.token) > 2:
        raise CombatError("tokens are at most 2 characters")
    if any(c["token"] == args.token for c in st["tokens"]):
        raise CombatError(f"token '{args.token}' already exists")
    x, y = parse_pos(args.pos, st)
    prof = {}
    if args.ref:
        try:
            prof = R.load_profile(args.ref) or {}
        except ValueError as e:
            raise CombatError(f"bad combat-profile block in {args.ref}: {e}")
    if args.profile:
        prof.update(json.loads(args.profile))
    if prof:
        errs, warns = R.check_profile(prof, campaign_system(args.campaign))
        if errs:
            raise CombatError(f"the combat profile for {args.token} has errors (fix the stat block's block, "
                              f"see library/<system>/combat-profile-guide.md):\n  " + "\n  ".join(errs))

    def pick(arg: Any, key: str, default: Any = None) -> Any:
        """The command-line value if given, else the profile's, else the default."""
        return arg if arg is not None else prof.get(key, default)

    notes = []
    if args.init is None or str(args.init).lower() == "roll":
        if "init" not in prof:
            raise CombatError("give --init N, or a profile with 'init' to roll it")
        total_i, detail, _ = _roll(f"1d20{prof['init']:+d}")
        init: float = total_i
        notes.append(f"initiative 1d20{prof['init']:+d} → {detail} = {total_i}")
    else:
        init = float(args.init)
    hp = pick(args.hp, "hp")
    max_hp = prof.get("max_hp", hp)
    if args.hp is None and args.ref and "players/characters/" in args.ref:
        # a PC's current HP lives on the sheet's "**HP:** current / max" line (combat end writes it back)
        sheet = PROJECT / args.ref
        m = re.search(r"\*\*HP:\*\*\s*(-?\d+)\s*/\s*(\d+)", sheet.read_text(encoding="utf-8")) if sheet.exists() else None
        if m:
            hp, max_hp = int(m.group(1)), int(m.group(2))
    if hp is None:
        raise CombatError("give --hp, or a profile with 'hp'")
    c = {"token": args.token, "name": args.name, "side": args.side, "x": x, "y": y,
         "size": pick(args.size, "size", 1), "reach": pick(args.reach, "reach", 5),
         "speed": pick(args.speed, "speed", 30), "init": init,
         "hp": hp, "max_hp": max_hp, "ac": pick(args.ac, "ac"),
         "touch": pick(args.touch, "touch"), "ff": pick(args.ff, "ff"), "cr": args.cr,
         "hidden": args.hidden, "conditions": [], "ref": args.ref, "dr": pick(args.dr, "dr", 0),
         "con": pick(args.con, "con"), "profile": prof or None, "acted": False,
         "init_tb": prof.get("init", 0)}   # ties: the higher initiative modifier goes first
    for cx, cy in cells(c):
        if cost(st, cx, cy) is None or occupied(st, c, cx, cy):
            raise CombatError(f"{fmt_pos(cx, cy)} is blocked or occupied")
    st["tokens"].append(c)
    if not prof:
        notes.append("no combat profile: pass --roll/--dmg on attacks")
    return f"Added {args.token} ({args.name}) at {fmt_pos(x, y)}, init {init:g}" + (
        f" ({'; '.join(notes)})" if notes else "")


def cmd_endturn(args: Args, st: State) -> str:
    """Mark the PC's turn as over (the player ended it in words, or in the same message as their
    actions). In web/terminal play the interface then plays the next step itself."""
    c = token(st, args.token)
    if c["side"] != "pc":
        raise CombatError(f"{c['token']} isn't a PC: other actors' turns end with their step")
    if st.get("turn") != c["token"]:
        raise CombatError(f"it isn't {c['token']}'s turn")
    st["end_turn"] = c["token"]
    return f"{c['name']}'s turn is over; the interface plays the next step"


ACTOR_ARG = {"maneuver": "attacker", "attack": "attacker", "move": "token", "cast": "token", "sla": "token", "provoke": "token", "area": "frm"}


def check_actor(args: Args, st: State) -> None:
    """The actor lock: only the creature the turn pointer is on takes actions. Attacks of opportunity
    (`--aoo`) and anything marked `--out-of-turn` (readied or immediate actions, forced movement,
    repositioning during setup) are exempt. An area with no --from (a trap, a hazard) has no actor.

    Raises:
        CombatError: if another creature tries to act.
    """
    key = ACTOR_ARG.get(args.command)
    actor = getattr(args, key, None) if key else None
    if not actor or getattr(args, "out_of_turn", False) or getattr(args, "aoo", False):
        return
    turn = st.get("turn")
    if turn is None:
        raise CombatError(f"no one is acting yet: {actor} can't act before the first turn starts "
                          f"(use --out-of-turn to reposition during setup)")
    if actor != turn:
        raise CombatError(f"it's {turn}'s turn, not {actor}'s: resolve only the current actor. "
                          f"AoOs take --aoo; readied or immediate actions and forced movement take --out-of-turn")


def in_fight(c: Token) -> bool:
    """Whether the token still gets turns: not removed, and above 0 HP unless a PC or ally (dying ones roll)."""
    return not c.get("removed") and (c["hp"] > 0 or c["side"] in FRIENDLY)


def next_actor(st: State) -> tuple[Token, bool] | None:
    """The creature `next` will land on, and whether that starts a new round. Counts from the
    pointer's place in the full order, so it's right even if the current actor just dropped."""
    full = order(st)
    if not any(in_fight(c) for c in full):
        return None
    toks = [c["token"] for c in full]
    start = toks.index(st["turn"]) if st.get("turn") in toks else -1
    for k in range(1, len(full) + 1):
        j = start + k
        c = full[j % len(full)]
        if in_fight(c):
            return c, start >= 0 and j >= len(full)
    return None


def cmd_next(args: Args, st: State) -> str:
    """Advance the turn pointer and handle the start of that creature's turn: expiring conditions,
    ongoing damage, AoO and movement resets, and dying checks (NPCs roll; a dying PC opens a question).
    """
    found = next_actor(st)
    if not found:
        raise CombatError("no combatants")
    lapsed = []
    for g in list(grapples(st)):   # a grapple must be maintained every round, on the grappler's turn
        if g["by"] == st.get("turn") and g.get("round") != st.get("round"):
            end_grapple(st, g)
            lapsed.append(f"  {g['by']} didn't maintain its grapple on {g['target']}: the grapple ends")
            event(st, f"{who(token(st, g['by']))} lets go of {who(token(st, g['target']))}")
    c, wraps = found
    if wraps:
        st["round"] = st.get("round", 1) + 1
    st["turn"] = c["token"]
    st.pop("end_turn", None)
    out = [f"Round {st['round']}: {label(c)} ({c['name']}) acts"] + lapsed
    # start of this creature's turn
    for o, name in R.expire(st, c["token"], st["round"]):
        out.append(f"  ended: {name} on {label(o)}")
        if not o.get("hidden"):
            event(st, f"{who(o)} is no longer {name}")
    c["acted"] = True          # no longer flat-footed from the start of the fight
    c["aoo_used"] = 0
    c["moved"] = 0
    c.pop("stepped", None)
    c.pop("overrun_through", None)
    for g in grapples(st):
        if g["by"] == c["token"]:
            out.append(f"  {c['token']} is grappling {g['target']}{' (pinned)' if g['pinned'] else ''}: maintain it this "
                       f"turn (`maneuver {c['token']} {g['target']} grapple`, +5) or `release`; not maintaining ends it")
        elif g["target"] == c["token"]:
            can = "only verbal and mental actions" if g["pinned"] else "act without two hands"
            out.append(f"  {c['token']} is {'pinned' if g['pinned'] else 'grappled'} by {g['by']}: it can try to escape "
                       f"(`maneuver {c['token']} {g['by']} escape`, CMB or Escape Artist) or take {can}")
    for x in R.conditions(c):
        if x.get("ongoing") and c["hp"] > -1000:
            d, detail, _ = _roll(x["ongoing"])
            dealt, _abs = apply_damage(c, d)
            out.append(f"  ongoing {x['name']}: {x['ongoing']} → {detail} = {d}")
            if not c.get("hidden"):
                event(st, f"{who(c)} takes {d} damage from {x['name']} [{who(c)}: {status(c)}]")
    if c["hp"] < 0 and not R.has(c, "stable") and not (c.get("con") and c["hp"] <= -c["con"]):
        if c["side"] == "pc":
            st["awaiting"] = f"{c['name']} is dying: roll a stabilization check (d20 + Con modifier)"
            out.append(f"  {c['name']} is dying: ask the player for a stabilization check, then "
                       f"`stabilize {c['token']} --total N` (question set)")
        else:
            out.append("  " + _stabilize(st, c, None))
    elif c["hp"] == 0:
        out.append("  disabled: a single move or standard action; a strenuous one costs 1 HP")
    return "\n".join(out)


def aoo_left(o: Token) -> int:
    """How many attacks of opportunity the token has left this round (1, or 1 + Dex with Combat Reflexes)."""
    prof = o.get("profile") or {}
    allowed = prof.get("aoo")
    if allowed is None:
        feats = [f.lower() for f in (prof.get("feats") or [])]
        allowed = 1 + (max(0, R.ability_mod(prof.get("dex"))) if "combat reflexes" in feats else 0)
    return allowed - o.get("aoo_used", 0)


def aoo_blocked(o: Token) -> str | None:
    """Why the token can't make attacks of opportunity right now, or None if it can: a condition
    (grappled, pinned, helpless, stunned, …), or being flat-footed before its first turn without
    Combat Reflexes or uncanny dodge."""
    names = R.condition_names(o, ("no_aoo",))
    if names:
        return ", ".join(names)
    prof = o.get("profile") or {}
    feats = [f.lower() for f in (prof.get("feats") or [])]
    if not o.get("acted") and "combat reflexes" not in feats and not prof.get("uncanny_dodge"):
        return "flat-footed (hasn't acted yet)"
    return None


def provoke_aoos(st: State, c: Token, no_aoo: bool = False, reason: str = 'provoking',
                 only: list[Token] | None = None) -> tuple[list[str], int]:
    """Resolve the attacks of opportunity that `c` provokes right now. NPC and ally threateners
    attack automatically (first melee attack in their profile); a PC's chance opens a question
    (unless its standing order says never). `only` limits it to these threateners (a combat
    maneuver provokes only from its target). Returns (lines, damage c took)."""
    out, hp_before = [], c["hp"]
    for o in [x for x in st["tokens"] if threatens(x, c) and (only is None or x in only)]:
        why = aoo_blocked(o)
        if why:
            out.append(f"  {label(o)} can't make an AoO ({why})")
            continue
        if aoo_left(o) <= 0:
            out.append(f"  {label(o)} could make an AoO but has none left this round")
            continue
        if o["side"] == "pc":
            order = st.get("orders", {}).get(o["token"], {}).get("aoo", "ask")
            if order == "never":
                out.append(f"  {label(o)} passes on the AoO (standing order)")
                continue
            st["awaiting"] = f"{o['name']}: {who(c)} provokes ({reason}). Take an attack of opportunity? If so, roll it"
            out.append(f"  {label(o)} may take an AoO on {c['token']} ({reason}): ask the player (question set), "
                       f"then `attack {o['token']} {c['token']} --total N --damage N --aoo`")
            continue
        if no_aoo:
            out.append(f"  {label(o)} could take an AoO (skipped: --no-aoo)")
            continue
        melee = [(k, v) for k, v in ((o.get("profile") or {}).get("attacks") or {}).items()
                 if v.get("type", "melee") == "melee"]
        if not melee:
            out.append(f"  {label(o)} may take an AoO on {c['token']}: no melee attack in its profile, "
                       f"resolve with `attack {o['token']} {c['token']} --roll … --dmg … --aoo`")
            continue
        k, w = melee[0]
        b = w["bonus"][0] if isinstance(w["bonus"], list) else w["bonus"]
        o["aoo_used"] = o.get("aoo_used", 0) + 1
        ns = argparse.Namespace(touch=False, charge=False, ac=None, aoo=True, nonlethal=False,
                                no_crit=False, total=None, nat=None, confirm=None, damage=None)
        out.append("  " + _attack_once(ns, st, o, c, k, b, w["damage"], w.get("crit", 20),
                                       w.get("mult", 2), "melee", w).replace("\n", "\n  "))
        if c["hp"] <= 0:
            break
    return out, max(0, hp_before - c["hp"])


def cmd_provoke(args: Args, st: State) -> str:
    """Resolve the AoOs a creature provokes now; a PC casting who takes damage gets a concentration question."""
    c = token(st, args.token)
    out, dmg = provoke_aoos(st, c, args.no_aoo, args.reason)
    if dmg and c["side"] == "pc" and c["hp"] > 0 and "cast" in args.reason.lower():
        st["awaiting"] = (f"{c['name']} took {dmg} damage while {args.reason}: roll a concentration check "
                          f"(DC {10 + dmg} + the spell's level) or lose the spell")
        out.append(f"  {c['name']} must make a concentration check: DC {10 + dmg} + spell level (question set)")
    return "\n".join([f"{c['token']} provokes ({args.reason})"] + (out or ["  no one threatens it"]))


# ---------- spellcasting ----------

def _spent(c: Token) -> dict[str, Any]:
    """The token's record of used spell slots, cast prepared spells and SLA uses (created if missing)."""
    return c.setdefault("spent", {"slots": {}, "prepared": {}, "sla": {}})


def _concentration(st: State, c: Token, bonus: int, dc: int, why: str) -> tuple[bool, str]:
    """Roll a concentration check. Returns (success, report line)."""
    total_c, detail, _ = _roll(f"1d20{bonus:+d}")
    ok = total_c >= dc
    return ok, f"concentration ({why}) 1d20{bonus:+d} → {detail} = {total_c} vs DC {dc}: {'success' if ok else 'FAILED, the spell is lost'}"


def _cast_common(st: State, c: Token, name: str, level: int, conc_bonus: int, args: Args) -> tuple[list[str], bool]:
    """Provoking, defensive casting and concentration. Returns (lines, success)."""
    out = []
    threatened = any(threatens(o, c) for o in st["tokens"])
    if threatened and args.defensive:
        ok, line = _concentration(st, c, conc_bonus, 15 + 2 * level, "casting defensively")
        out.append("  " + line)
        return out, ok
    if threatened and not args.no_provoke:
        lines, dmg = provoke_aoos(st, c, False, f"casting {name}")
        out += lines
        if c["hp"] <= 0:
            out.append(f"  {c['token']} goes down; the spell is lost")
            return out, False
        if dmg:
            ok, line = _concentration(st, c, conc_bonus, 10 + dmg + level, f"took {dmg} damage while casting")
            out.append("  " + line)
            return out, ok
    return out, True


def cmd_cast(args: Args, st: State) -> str:
    """An NPC casts a spell: check and spend the slot or prepared copy, provoke or cast defensively, then the effect."""
    c = token(st, args.token)
    spell = args.spell.lower()
    casters = (c.get("profile") or {}).get("spellcasting") or []
    if not casters:
        raise CombatError(f"{c['token']} has no spellcasting in its profile")
    sp = _spent(c)
    found = None
    for sc in casters:
        if args.cls and sc["class"].lower() != args.cls.lower():
            continue
        for lvl, lst in (sc.get("spells") or {}).items():
            if args.level is not None and int(lvl) != args.level:
                continue
            if spell in [x.lower() for x in lst]:
                found = (sc, int(lvl))
                break
        if found:
            break
    if not found:
        raise CombatError(f"{c['token']} doesn't have {args.spell!r}" + (f" at level {args.level}" if args.level is not None else "")
                          + " in its spells known / prepared")
    sc, lvl = found
    key = sc["class"].lower()
    left_note = ""
    if lvl > 0:
        if sc["type"] == "spontaneous":
            used = sp["slots"].setdefault(key, {}).get(str(lvl), 0)
            per_day = sc["slots"].get(str(lvl), 0)
            if used >= per_day:
                raise CombatError(f"{c['token']} has no level-{lvl} {sc['class']} slots left ({used}/{per_day} used)")
            sp["slots"][key][str(lvl)] = used + 1
            left_note = f"level-{lvl} slots left: {per_day - used - 1}/{per_day}"
        else:
            prepared = [x.lower() for x in sc["spells"][str(lvl)]].count(spell)
            cast_n = sp["prepared"].setdefault(key, []).count(spell)
            if cast_n >= prepared:
                raise CombatError(f"{c['token']} has already cast every prepared {args.spell!r} ({cast_n}/{prepared})")
            sp["prepared"][key].append(spell)
            left_note = f"prepared {args.spell!r} left: {prepared - cast_n - 1}"
    lines, ok = _cast_common(st, c, args.spell, lvl, sc["concentration"], args)
    dc = args.dc or (sc["dc_base"] + lvl)
    if not c.get("hidden"):
        event(st, f"{who(c)} casts a spell" + ("" if ok else ", but loses it"))
    head = f"{c['token']} casts {args.spell} ({sc['class']} {lvl}, CL {sc['cl']}, save DC {dc}): {'OK' if ok else 'LOST'}"
    effect = _spell_effect(args, st, c, args.spell, dc) if ok else []
    return "\n".join([head] + ([f"  {left_note}"] if left_note else []) + lines + effect)


def _spell_effect(args: Args, st: State, c: Token, name: str, dc: int | None) -> list[str]:
    """The effect part of cast/sla: an area template or a single target, with save and damage.
    The player's log and questions say "the spell" / "the ability": naming it is a Spellcraft matter."""
    out = []
    shown = "the ability" if args.command == "sla" else "the spell"
    if args.area:
        m = re.match(r"^\s*(burst|cone|line)\s+(\d+)\s*$", args.area)
        if not m:
            raise CombatError('--area must look like "cone 15", "burst 20" or "line 60"')
        ns = argparse.Namespace(shape=m.group(1), feet=int(m.group(2)), at=args.at, frm=c["token"],
                                toward=args.toward, save=args.save, dc=dc, dmg=args.dmg, half=args.half,
                                name=name, no_slot=True, log_name=shown)
        out.append(cmd_area(ns, st))
    elif args.target:
        t = token(st, args.target)
        dmg = 0
        if args.dmg:
            dmg, detail, _ = _roll(args.dmg)
            out.append(f"{name}: damage {args.dmg} → {detail} = {dmg}")
        if args.save:
            if dc is None:
                raise CombatError("--save needs a DC: pass --dc")
            if t["side"] == "pc":
                st.setdefault("pending_saves", {})[t["token"]] = {
                    "kind": args.save, "dc": dc, "dmg": dmg, "half": args.half, "name": shown}
                st["awaiting"] = f"{t['name']}: roll a {args.save.capitalize()} save against {shown}"
                out.append(f"  {t['name']}'s save is pending: ask the player, then `save {t['token']} --total N` (question set)")
            else:
                ok, total_s, how = _save(st, t, args.save, dc)
                taken = (dmg // 2 if args.half else 0) if ok else dmg
                out.append(f"  {label(t)} {args.save} {how} vs DC {dc}: {'success' if ok else 'failure'}"
                           + (f", {taken} damage" if args.dmg else ""))
                if taken:
                    apply_damage(t, taken)
                if not t.get("hidden"):
                    event(st, f"{shown}: {who(t)} {args.save} save {total_s} — {'success' if ok else 'failure'}"
                              + (f", {taken} damage [{who(t)}: {status(t)}]" if args.dmg else ""))
        elif dmg:
            apply_damage(t, dmg)
            if not t.get("hidden"):
                event(st, f"{shown}: {who(t)} takes {dmg} damage [{who(t)}: {status(t)}]")
    return out


def cmd_sla(args: Args, st: State) -> str:
    """An NPC uses a spell-like ability: check and spend a use, provoke or use it defensively, then the effect."""
    c = token(st, args.token)
    name = args.name.lower()
    entry = next((s for s in (c.get("profile") or {}).get("sla") or [] if s["name"].lower() == name), None)
    if not entry:
        raise CombatError(f"{c['token']} has no spell-like ability {args.name!r}")
    sp = _spent(c)
    per_day = entry["per_day"]
    note = ""
    if per_day == "constant":
        return f"{args.name} is constant: always active, nothing to use"
    if per_day != "at will":
        used = sp["sla"].get(name, 0)
        if used >= per_day:
            raise CombatError(f"{c['token']} has used {args.name!r} {used}/{per_day} times today")
        sp["sla"][name] = used + 1
        note = f"uses left today: {per_day - used - 1}/{per_day}"
    lvl = entry.get("level", 0)
    lines, ok = _cast_common(st, c, args.name, lvl, entry.get("concentration", entry.get("cl", 0)), args)
    if not c.get("hidden"):
        event(st, f"{who(c)} uses a spell-like ability" + ("" if ok else ", but loses it"))
    dc_val = args.dc or entry.get("dc")
    dc = f", DC {dc_val}" if dc_val else ""
    head = f"{c['token']} uses {args.name} (SLA, CL {entry.get('cl', '?')}{dc}): {'OK' if ok else 'LOST'}"
    if ok and (args.area or args.target) and args.save and not dc_val:
        raise CombatError(f"{args.name} has no DC in the profile: pass --dc")
    effect = _spell_effect(args, st, c, args.name, dc_val) if ok else []
    return "\n".join([head] + ([f"  {note}"] if note else []) + lines + effect)


def cmd_spells(args: Args, st: State) -> str:
    """The remaining slots, prepared spells and SLA uses of a token (DM view)."""
    c = token(st, args.token)
    prof = c.get("profile") or {}
    sp = _spent(c)
    out = []
    for sc in prof.get("spellcasting") or []:
        key = sc["class"].lower()
        out.append(f"{sc['class']} ({sc['type']}, CL {sc['cl']}, concentration {sc['concentration']:+d}, DC {sc['dc_base']}+level)")
        for lvl in sorted(sc["slots"], key=int):
            spells = sc.get("spells", {}).get(lvl, [])
            if lvl == "0":
                out.append(f"  0: at will: {', '.join(spells)}")
            elif sc["type"] == "spontaneous":
                used = sp["slots"].get(key, {}).get(lvl, 0)
                out.append(f"  {lvl}: {sc['slots'][lvl] - used}/{sc['slots'][lvl]} left: {', '.join(spells)}")
            else:
                cast = list(sp["prepared"].get(key, []))
                left = []
                for s in spells:
                    if s.lower() in cast:
                        cast.remove(s.lower())
                    else:
                        left.append(s)
                out.append(f"  {lvl}: left {', '.join(left) or 'none'}")
    for s in prof.get("sla") or []:
        per = s["per_day"]
        if isinstance(per, int):
            per = f"{per - sp['sla'].get(s['name'].lower(), 0)}/{per} left"
        out.append(f"SLA {s['name']}: {per}")
    return "\n".join(out) or f"{c['token']} has no spells or spell-like abilities"


def campaign_system(campaign: str) -> str:
    """The campaign's system from the '**System:**' line of campaign.md (default 'pf1e')."""
    f = PROJECT / "campaigns" / campaign / "campaign.md"
    if f.exists():
        m = re.search(r"\*\*System:\*\*\s*([a-z0-9]+)", f.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return "pf1e"


def cmd_profile(args: Args) -> int:
    """profile check FILE [FILE …]: validate the combat-profile blocks in stat block files."""
    system = campaign_system(args.campaign)
    bad = 0
    lines = []
    for f in args.files:
        path = Path(f) if Path(f).is_absolute() else PROJECT / f
        if not path.exists():
            lines.append(f"{f}: no such file"); bad += 1; continue
        blocks = R.profile_text_blocks(path.read_text(encoding="utf-8"))
        if not blocks:
            lines.append(f"{f}: NO combat-profile block"); bad += 1; continue
        for i, b in enumerate(blocks):
            tag = f"{f}" + (f" (block {i + 1})" if len(blocks) > 1 else "")
            try:
                prof = json.loads(b)
            except ValueError as e:
                lines.append(f"{tag}: INVALID JSON: {e}"); bad += 1; continue
            errs, warns = R.check_profile(prof, system)
            if errs:
                bad += 1
            lines.append(f"{tag}: {'ERRORS' if errs else 'OK'}")
            lines += [f"  error: {e}" for e in errs] + [f"  warning: {w}" for w in warns]
    print("\n".join(lines))
    return 1 if bad else 0


def cmd_move(args: Args, st: State) -> str:
    """Move a token along the cheapest legal path. Tracks feet per turn and the 5-foot step, and resolves
    the attacks of opportunity for leaving threatened squares (the mover stops if it drops).
    """
    c = token(st, args.token)
    if c["hp"] <= 0 and c["side"] not in FRIENDLY:
        raise CombatError(f"{c['token']} is down (HP {c['hp']}) and can't move")
    if c["hp"] < 0:
        raise CombatError(f"{c['token']} is dying (HP {c['hp']}) and can't move")
    stuck = R.condition_names(c, ("no_move",))
    if stuck and not args.out_of_turn:
        raise CombatError(f"{c['token']} can't move ({', '.join(stuck)}); forced movement takes --out-of-turn")
    dest = parse_pos(args.pos, st)
    feet = path_cost(st, c, dest)
    frm = fmt_pos(c["x"], c["y"])
    out = []
    if args.step:
        if feet != 5:
            raise CombatError(f"a 5-foot step moves exactly one square (this move costs {feet} ft)")
        if c.get("moved"):
            raise CombatError(f"{c['token']} already moved this turn; no 5-foot step allowed")
        c["stepped"] = True
    elif c.get("stepped"):
        out.append("  WARNING: took a 5-foot step this turn, so no other movement is allowed")
    # attacks of opportunity for leaving threatened squares (not on a 5-foot step)
    if not args.step:
        lines, _dmg = provoke_aoos(st, c, args.no_aoo, "moving out of a threatened square")
        out += lines
        if c["hp"] <= 0:
            out.insert(0, f"{c['token']} is dropped by an attack of opportunity at {frm} and doesn't move")
            return "\n".join(out)
    c["x"], c["y"] = dest
    c["moved"] = c.get("moved", 0) + feet
    speed = c.get("speed") or 30
    warn = ""
    if c["moved"] > 2 * speed:
        warn = f"  EXCEEDS a double move ({c['moved']} ft this turn, max {2 * speed})"
    elif c["moved"] > speed:
        warn = f"  (double move: {c['moved']} ft this turn)"
    kind = "5-foot step" if args.step else "moves"
    out.insert(0, f"{c['token']} {kind} {frm} → {fmt_pos(*dest)}: {feet} ft{warn}")
    return "\n".join(out)


# ---------- combat maneuvers ----------
# Rules: library/pf1e/rules/combat-maneuvers.md (Core Rulebook pg. 198-201, APG). d20 + CMB vs CMD;
# a tie succeeds, a natural 20 always succeeds and a natural 1 always fails.

MANEUVERS = ("bull-rush", "dirty-trick", "disarm", "drag", "grapple", "overrun", "reposition",
             "steal", "sunder", "trip", "escape", "release")
FEAT_NAME = {"bull-rush": "bull rush", "dirty-trick": "dirty trick", "disarm": "disarm", "drag": "drag",
             "grapple": "grapple", "overrun": "overrun", "reposition": "reposition", "steal": "steal",
             "sunder": "sunder", "trip": "trip"}
SIZE_LIMITED = {"bull-rush", "drag", "overrun", "reposition", "trip"}   # target at most one size larger
AS_AOO = {"disarm", "sunder", "trip"}                                  # may replace an attack (or an AoO)
DIRTY_TRICKS = ("blinded", "dazzled", "deafened", "entangled", "shaken", "sickened")
VERB = {"bull-rush": "bull rush", "dirty-trick": "use a dirty trick on", "disarm": "disarm", "drag": "drag",
        "grapple": "grapple", "overrun": "overrun", "reposition": "reposition", "steal": "steal from",
        "sunder": "sunder the gear of", "trip": "trip", "escape": "escape from"}


def _feats(c: Token) -> list[str]:
    """The token's feats in lowercase."""
    return [f.lower() for f in ((c.get("profile") or {}).get("feats") or [])]


def grapples(st: State) -> list[dict[str, Any]]:
    """Active grapples: {"by": grappler token, "target": token, "pinned": bool}."""
    return st.setdefault("grapples", [])


def _grapple(st: State, by: str, target: str) -> dict[str, Any] | None:
    """The grapple `by` holds on `target`, if any."""
    return next((g for g in grapples(st) if g["by"] == by and g["target"] == target), None)


def end_grapple(st: State, g: dict[str, Any]) -> None:
    """End a grapple: both lose grappled/pinned/pinning unless another grapple still holds them."""
    st["grapples"] = [x for x in grapples(st) if x is not g]
    for tok in (g["by"], g["target"]):
        if any(tok in (x["by"], x["target"]) for x in grapples(st)):
            continue
        c = token(st, tok)
        for name in ("grappled", "pinned", "pinning"):
            R.remove_condition(c, name)


def clean_grapples(st: State) -> list[str]:
    """End grapples whose grappler or target is out of the fight or unconscious (the usual ruling;
    the rules don't say). Returns report lines."""
    out = []
    for g in list(grapples(st)):
        a, t = token(st, g["by"]), token(st, g["target"])
        gone = [c for c in (a, t) if c.get("removed") or c["hp"] < 0 or (c["hp"] == 0 and c["side"] not in FRIENDLY)]
        if gone:
            end_grapple(st, g)
            out.append(f"  grapple {g['by']} → {g['target']} ended ({', '.join(c['token'] for c in gone)} is out)")
            if not any(c.get("hidden") for c in (a, t)):
                event(st, f"{who(a)}'s grapple on {who(t)} ends")
    return out


def _free_adjacent(st: State, anchor: Token, mover: Token, near: Square) -> Square | None:
    """The open square next to `anchor` where `mover` fits, closest to `near`."""
    best = None
    for y in range(st["h"]):
        for x in range(st["w"]):
            ok = all(cost(st, cx, cy) is not None and not occupied(st, mover, cx, cy) for cx, cy in cells(mover, (x, y)))
            if not ok:
                continue
            probe = dict(mover, x=x, y=y)
            if feet_between(anchor, probe) != 5:
                continue
            d = sq_dist((x, y), near)
            if best is None or d < best[0]:
                best = (d, (x, y))
    return best[1] if best else None


def _fits(st: State, c: Token, at: Square, ignore: tuple[Token, ...] = ()) -> bool:
    """Whether the token fits at `at`: on the map, passable, and not on another token."""
    for cx, cy in cells(c, at):
        if cost(st, cx, cy) is None:
            return False
        if any(o is not c and o not in ignore and not o.get("removed") and (cx, cy) in cells(o) for o in st["tokens"]):
            return False
    return True


def _direction(frm: Token, to: Token) -> tuple[int, int]:
    """Unit step (dx, dy) from one token's center toward another's."""
    fx, fy = frm["x"] + frm["size"] / 2, frm["y"] + frm["size"] / 2
    tx, ty = to["x"] + to["size"] / 2, to["y"] + to["size"] / 2
    sgn = lambda v: (v > 0.01) - (v < -0.01)
    return sgn(tx - fx), sgn(ty - fy)


def _push(st: State, c: Token, d: tuple[int, int], squares: int, ignore: tuple[Token, ...] = ()) -> int:
    """Move `c` up to `squares` squares in direction d, stopping at anything in the way. Returns squares moved."""
    moved = 0
    for _ in range(squares):
        nxt = (c["x"] + d[0], c["y"] + d[1])
        if not _fits(st, c, nxt, ignore):
            break
        c["x"], c["y"] = nxt
        moved += 1
    return moved


def maneuver_cmd(st: State, t: Token, kind: str) -> tuple[int, list[str]]:
    """The target's CMD against this maneuver, with conditions applied: Str/Dex changes, AC penalties
    and bonuses (which also apply to CMD), and a flat-footed target's lost Dex bonus. Returns (CMD, notes)."""
    prof = t.get("profile") or {}
    base = (prof.get("cmd_vs") or {}).get(kind, prof.get("cmd"))
    if base is None:
        raise CombatError(f"{t['token']} has no CMD: add 'cmd' to its profile, or pass --cmd N")
    notes = []
    v = base + R.mod_change(t, "str") + R.mod_change(t, "dex") + R.total(t, "ac")
    uncanny = bool(prof.get("uncanny_dodge"))
    if R.flag(t, "flatfooted") or (not t.get("acted") and not uncanny):
        dex_mod = R.ability_mod(R.scores(t, "dex")[1])
        if dex_mod > 0:
            v -= dex_mod
            notes.append("flat-footed")
    names = R.condition_names(t, ("ac", "dex", "dex_zero", "str", "str_zero"))
    if names:
        notes.append("target " + ", ".join(names))
    return v, notes


def maneuver_cmb(st: State, a: Token, t: Token, kind: str, args: Args) -> tuple[int, list[str]]:
    """Situational modifiers on the attacker's check (not the base CMB). Returns (delta, notes)."""
    delta, notes = 0, []
    # attack-roll modifiers from conditions; grappled/pinned don't apply to grappling or escaping
    skip = ("grappled", "pinned") if kind in ("grapple", "escape") else ()
    cond = sum(R.cond_effects(x).get("atk", 0) for x in R.conditions(a) if x["name"].lower() not in skip)
    cond += R.mod_change(a, "str")
    if cond:
        delta += cond
        names = [n for n in R.condition_names(a, ("atk", "str", "str_zero")) if n.lower() not in skip]
        notes.append(f"{cond:+d} {', '.join(names) or 'conditions'}")
    if R.flag(a, "prone"):
        delta -= 4
        notes.append("-4 prone")
    if getattr(args, "charge", False):
        delta += 2
        notes.append("+2 charge")
    if kind != "escape" and flanking(st, a, t):
        delta += 2
        notes.append("+2 flanking")
    if R.has(t, "stunned"):
        delta += 4
        notes.append("+4 target stunned")
    if kind == "grapple" and _grapple(st, a["token"], t["token"]):
        delta += 5
        notes.append("+5 maintaining")
    if kind == "grapple" and getattr(args, "grab", False):
        delta += 4
        notes.append("+4 grab")
    if getattr(args, "mod", None):
        delta += args.mod
        notes.append(f"{args.mod:+d} situational")
    return delta, notes


def cmd_maneuver(args: Args, st: State) -> str:
    """A combat maneuver: provoke (unless the Improved feat or grab), roll or take the check
    against CMD, and apply the result (prone, pushed, grappled, …). Grapples are tracked:
    `maneuver A T grapple` again maintains (+5) with --option pin|damage|move, `escape`
    breaks free (or --reverse), `release` lets go."""
    a, t = token(st, args.attacker), token(st, args.target)
    kind = args.kind
    pa, pt = a.get("profile") or {}, t.get("profile") or {}
    if a is t:
        raise CombatError("a maneuver needs another creature as its target")

    if kind == "release":
        g = _grapple(st, a["token"], t["token"])
        if not g:
            raise CombatError(f"{a['token']} isn't grappling {t['token']}")
        end_grapple(st, g)
        event(st, f"{who(a)} releases {who(t)}")
        return f"{a['token']} releases {t['token']} (free action)"

    held = _grapple(st, t["token"], a["token"]) if kind == "escape" else None
    if kind == "escape" and not held:
        raise CombatError(f"{t['token']} isn't grappling {a['token']}")
    maintain = _grapple(st, a["token"], t["token"]) if kind == "grapple" else None
    if args.option and not maintain:
        raise CombatError("--option (pin, damage, move, tie) only works when maintaining a grapple you started")
    if kind in (pt.get("maneuver_immune") or []):
        raise CombatError(f"{t['token']} can't be affected by {kind} (its profile says so)")
    if kind in SIZE_LIMITED and t["size"] - a["size"] > 1:
        raise CombatError(f"{t['token']} is too big to {kind.replace('-', ' ')} (more than one size larger)")
    if kind == "dirty-trick" and args.condition not in DIRTY_TRICKS:
        raise CombatError(f"a dirty trick needs --condition, one of: {', '.join(DIRTY_TRICKS)}")
    if kind == "reposition" and not args.to:
        raise CombatError("a reposition needs --to SQUARE (where the target should end up)")
    dm = []
    reach = args.reach or a.get("reach", 5)
    if feet_between(a, t) > reach and kind != "escape":
        raise CombatError(f"{t['token']} is {feet_between(a, t)} ft away, beyond {a['token']}'s reach ({reach} ft); "
                          f"move first, or pass --reach N for a reach weapon or whip")
    if args.aoo:
        if kind not in AS_AOO:
            raise CombatError(f"only {', '.join(sorted(AS_AOO))} can be made as an attack of opportunity")
        why = aoo_blocked(a)
        if why:
            raise CombatError(f"{a['token']} can't make attacks of opportunity: {why}")
        if aoo_left(a) <= 0:
            raise CombatError(f"{a['token']} has no attacks of opportunity left this round")
        a["aoo_used"] = a.get("aoo_used", 0) + 1

    # provoking: from the target only, unless the Improved feat, grab, or not a new attempt
    penalty = 0
    feat = FEAT_NAME.get(kind)
    improved = bool(feat) and f"improved {feat}" in _feats(a)
    provokes = feat is not None and not maintain and not improved and not args.grab and not args.no_provoke and not args.aoo
    if provokes:
        if args.aoo_damage is not None:
            penalty = args.aoo_damage
            if penalty:
                dm.append(f"the AoO it provoked dealt {penalty}: -{penalty} on the check")
        elif threatens(t, a) and (aoo_blocked(t) or aoo_left(t) <= 0):
            dm.append(f"it provokes, but {t['token']} can't take the AoO ({aoo_blocked(t) or 'none left this round'})")
        elif threatens(t, a):
            if t["side"] == "pc" and st.get("orders", {}).get(t["token"], {}).get("aoo", "ask") != "never":
                st["awaiting"] = (f"{t['name']}: {who(a)} tries to {VERB[kind]} you and provokes. Take an attack of "
                                  f"opportunity? If so, roll it")
                return (f"{a['token']}'s {kind} provokes an AoO from {t['token']}: ask the player (question set). Then "
                        f"`attack {t['token']} {a['token']} --total N --damage N --aoo` if they take it, and rerun this "
                        f"maneuver with --aoo-damage N (the damage dealt, 0 if it missed or they passed)")
            lines, taken = provoke_aoos(st, a, reason=f"attempting to {VERB[kind]} {t['token']}", only=[t])
            dm += [l.strip() for l in lines]
            penalty = taken
            if a["hp"] <= 0:
                event(st, f"{who(a)} goes down before the {kind.replace('-', ' ')} lands")
                return "\n".join([f"{a['token']} is dropped by the AoO; the {kind} fails"] + dm)
            if penalty:
                dm.append(f"the AoO dealt {penalty}: -{penalty} on the check")
    elif feat and improved and not maintain:
        dm.append(f"no AoO (Improved {feat.title()})")

    # the check
    target_cmd = args.cmd if args.cmd is not None else None
    if kind == "escape":   # against the grappler's CMD
        cmd_v, cmd_notes = maneuver_cmd(st, t, "grapple") if target_cmd is None else (target_cmd, [])
    else:
        cmd_v, cmd_notes = maneuver_cmd(st, t, kind) if target_cmd is None else (target_cmd, [])
    delta, notes = maneuver_cmb(st, a, t, kind, args)
    delta -= penalty
    if penalty:
        notes.append(f"-{penalty} AoO damage")
    auto = kind != "escape" and any(R.has(t, n) for n in ("helpless", "unconscious", "paralyzed"))
    if args.total is not None:        # the player's roll, everything they know included
        total_v, nat = args.total, args.nat
        pc_side = [n for n in notes if n.startswith(("+", "-"))]
        if pc_side:
            dm.append(f"reminder: {', '.join(pc_side)} applies to the player's roll; check they included it")
        how = f"reported {total_v}"
    else:
        base = args.cmb if args.cmb is not None else (pa.get("cmb_vs") or {}).get(kind, pa.get("cmb"))
        if base is None:
            raise CombatError(f"{a['token']} has no CMB: add 'cmb' to its profile, or pass --cmb N (or --total for a PC)")
        expr = f"1d20{base + delta:+d}"
        total_v, detail, _ = _roll(expr)
        nat = _natural(detail)
        how = f"{expr} (CMB {base:+d}{', ' + ', '.join(notes) if notes else ''}) → {detail} = {total_v}"
    ok = auto or nat == 20 or (nat != 1 and total_v >= cmd_v)
    margin = total_v - cmd_v
    dm.insert(0, f"{kind}: {how} vs CMD {cmd_v}" + (f" ({', '.join(cmd_notes)})" if cmd_notes else "")
              + (" — automatic success (helpless target)" if auto else "")
              + f": {'SUCCESS' if ok else 'FAILURE'} by {abs(margin)}")
    shown_cmd = f" vs CMD {cmd_v}" if t["side"] in FRIENDLY else ""
    nat_s = " (natural 20)" if nat == 20 else " (natural 1)" if nat == 1 else ""
    head = f"{who(a)} tries to {VERB[kind]} {who(t)}: {total_v}{shown_cmd}{nat_s} — {'success' if ok else 'failure'}"
    result = _maneuver_effect(args, st, a, t, kind, ok, margin, maintain, held, dm)
    for g in grapples(st):   # a check made this round counts as maintaining
        if g["by"] == a["token"] and g["target"] == t["token"] and kind == "grapple":
            g["round"] = st.get("round", 1)
    if a.get("hidden"):
        a["hidden"] = False
        head = f"{who(a)} bursts from hiding! " + head
    event(st, head + (f": {result}" if result else ""))
    return "\n".join(dm + [f"Log: {head}" + (f": {result}" if result else "")])


def _maneuver_effect(args: Args, st: State, a: Token, t: Token, kind: str, ok: bool, margin: int,
                     maintain: dict[str, Any] | None, held: dict[str, Any] | None, dm: list[str]) -> str:
    """Apply a maneuver's result. Returns the player-safe result text for the log."""
    extra = max(0, margin) // 5            # every 5 points over the CMD
    if kind == "trip":
        if ok:
            R.add_condition(st, t, "prone")
            if "greater trip" in _feats(a):
                lines, _ = provoke_aoos(st, t, reason="knocked prone (Greater Trip)")
                dm += [l.strip() for l in lines]
            return f"{who(t)} falls prone"
        if margin <= -10:
            R.add_condition(st, a, "prone")
            return f"{who(a)} is knocked prone instead"
        return ""
    if kind == "grapple":
        if maintain:
            if not ok:
                end_grapple(st, maintain)
                return f"{who(t)} slips out of the grapple"
            return _grapple_option(args, st, a, t, maintain, dm)
        if not ok:
            return ""
        if feet_between(a, t) > 5:
            spot = _free_adjacent(st, a, t, (t["x"], t["y"]))
            if not spot:
                dm.append("no open square next to the grappler: the grapple fails")
                return "but there's no room to hold on"
            t["x"], t["y"] = spot
            dm.append(f"{t['token']} pulled to {fmt_pos(*spot)}")
        grapples(st).append({"by": a["token"], "target": t["token"], "pinned": False})
        R.add_condition(st, a, "grappled")
        R.add_condition(st, t, "grappled")
        return f"both are grappled"
    if kind == "escape":
        if not ok:
            return ""
        assert held is not None
        end_grapple(st, held)
        if args.reverse:
            grapples(st).append({"by": a["token"], "target": t["token"], "pinned": False})
            R.add_condition(st, a, "grappled")
            R.add_condition(st, t, "grappled")
            return f"{who(a)} breaks free and turns the hold around"
        return f"{who(a)} breaks free"
    if kind == "bull-rush":
        if not ok:
            return f"{who(a)} is stopped in front of {who(t)}"
        d = _direction(a, t)
        start = (a["x"], a["y"])
        moved = _push(st, t, d, 1 + extra)
        if args.follow and moved:
            a["x"], a["y"] = start
            _push(st, a, d, moved)
        if moved < 1 + extra:
            dm.append(f"pushed {5 * moved} of {5 * (1 + extra)} ft: something is in the way (a creature in the "
                      f"way can be pushed too with a new check at -4)")
        return f"{who(t)} is pushed back {5 * moved} ft" if moved else f"{who(t)} is pinned against an obstacle"
    if kind == "drag":
        if not ok:
            return ""
        d = _direction(t, a)
        moved = 0
        for _ in range(1 + extra):
            old = (a["x"], a["y"])
            if _push(st, a, d, 1) != 1:
                break
            if not _fits(st, t, (t["x"] + d[0], t["y"] + d[1])):
                a["x"], a["y"] = old
                break
            t["x"], t["y"] = t["x"] + d[0], t["y"] + d[1]
            moved += 1
        a["moved"] = a.get("moved", 0) + 5 * moved
        return f"{who(a)} drags {who(t)} {5 * moved} ft"
    if kind == "reposition":
        if not ok:
            return ""
        dest = parse_pos(args.to, st)
        allowed = 1 + extra
        if sq_dist((t["x"], t["y"]), dest) > allowed:
            raise CombatError(f"{args.to} is too far: the check allows {5 * allowed} ft")
        if not _fits(st, t, dest):
            raise CombatError(f"{args.to} is blocked or occupied")
        if feet_between(a, dict(t, x=dest[0], y=dest[1])) > a.get("reach", 5) + 5:
            raise CombatError(f"{args.to} is beyond {a['token']}'s reach (+5 ft)")
        t["x"], t["y"] = dest
        return f"{who(t)} is moved to {fmt_pos(*dest)}"
    if kind == "overrun":
        if not ok:
            return f"{who(a)} is stopped in front of {who(t)}"
        a.setdefault("overrun_through", []).append(t["token"])
        dm.append(f"{a['token']} may now move through {t['token']}'s space this turn (continue with `move`)")
        if margin >= 5:
            R.add_condition(st, t, "prone")
            if "greater overrun" in _feats(a):
                lines, _ = provoke_aoos(st, t, reason="knocked prone (Greater Overrun)")
                dm += [l.strip() for l in lines]
            return f"{who(a)} barrels through, and {who(t)} falls prone"
        return f"{who(a)} barrels through"
    if kind == "dirty-trick":
        if not ok:
            return ""
        if "greater dirty trick" in _feats(a):
            r, detail, _ = _roll("1d4")
            rounds = r + extra
            dm.append(f"Greater Dirty Trick: 1d4 → {detail} + {extra} = {rounds} rounds; removing it takes a standard action")
        else:
            rounds = 1 + extra
            dm.append(f"{rounds} round(s); the target can remove it with a move action (`cond {t['token']} remove {args.condition}`)")
        R.add_condition(st, t, args.condition, rounds=rounds)
        return f"{who(t)} is {args.condition}"
    their = "their" if t["side"] == "pc" else "its"
    item = args.item or (f"{their} weapon" if kind in ("disarm", "sunder") else "an item")
    if kind == "disarm":
        if ok:
            R.add_condition(st, t, "disarmed")
            where = " (it lands 15 ft away)" if "greater disarm" in _feats(a) else ""
            return f"{who(t)} drops {item}{where}" + (" and whatever else it holds" if margin >= 10 else "")
        if margin <= -10:
            R.add_condition(st, a, "disarmed")
            return f"{who(a)} fumbles and drops {'their' if a['side'] == 'pc' else 'its'} own weapon"
        return ""
    if kind == "steal":
        if ok:
            dm.append("Greater Steal: the target doesn't notice yet" if "greater steal" in _feats(a) else "the target notices")
            return f"{who(a)} takes {item}"
        return ""
    if kind == "sunder":
        if not ok:
            return ""
        if args.damage is not None:
            dmg = args.damage
        else:
            expr = args.dmg or next((w["damage"] for w in ((a.get("profile") or {}).get("attacks") or {}).values()
                                     if w.get("type", "melee") == "melee"), None)
            if not expr:
                raise CombatError("sunder damage: pass --dmg EXPR (NPC) or --damage N (PC)")
            dmg, detail, _ = _roll(expr)
            dm.append(f"sunder damage {expr} → {detail} = {dmg} (subtract the item's hardness; half its hp or less = broken)")
        return f"{item} takes {dmg} damage"
    return ""


def _grapple_option(args: Args, st: State, a: Token, t: Token, g: dict[str, Any], dm: list[str]) -> str:
    """A successful maintain: hold on, and optionally pin, deal damage, move, or tie up."""
    opt = args.option
    if opt == "pin":
        g["pinned"] = True
        R.remove_condition(t, "grappled")
        R.add_condition(st, t, "pinned")
        R.add_condition(st, a, "pinning")
        return f"{who(t)} is pinned"
    if opt == "damage":
        if args.damage is not None:
            dmg = args.damage
        else:
            expr = args.dmg or next((w["damage"] for w in ((a.get("profile") or {}).get("attacks") or {}).values()
                                     if w.get("type", "melee") == "melee"), None)
            if not expr:
                raise CombatError("grapple damage: pass --dmg EXPR (NPC) or --damage N (PC)")
            dmg, detail, _ = _roll(expr)
            dm.append(f"grapple damage {expr} → {detail} = {dmg}")
        dealt, absorbed = apply_damage(t, dmg, args.nonlethal)
        if absorbed:
            dm.append(f"DR/hardness absorbs {absorbed}")
        return f"{who(t)} takes {dealt} damage [{who(t)}: {status(t)}]"
    if opt == "move":
        if not args.to:
            raise CombatError("moving a grapple needs --to SQUARE (where the grappler goes); --place SQUARE for the target")
        dest = parse_pos(args.to, st)
        feet = path_cost(st, dict(a, conditions=[]), dest) if (a["x"], a["y"]) != dest else 0
        half = (a.get("speed") or 30) // 2
        if feet > half:
            raise CombatError(f"a grapple moves at most half speed ({half} ft); this move costs {feet} ft")
        a["x"], a["y"] = dest
        spot = parse_pos(args.place, st) if args.place else _free_adjacent(st, a, t, (t["x"], t["y"]))
        if not spot or not _fits(st, t, spot) or feet_between(a, dict(t, x=spot[0], y=spot[1])) != 5:
            raise CombatError("no open square next to the grappler for the target (pass --place SQUARE)")
        t["x"], t["y"] = spot
        return f"{who(a)} hauls {who(t)} along"
    if opt == "tie":
        dm.append("tie up: needs rope; -10 on this check unless the target was pinned, restrained or unconscious. "
                  "Escape DC 20 + the grappler's CMB. Track it as a condition (`cond … add \"tied up\"`) and end the "
                  "grapple with `maneuver … release`")
        return f"{who(a)} ties up {who(t)}"
    return f"{who(a)} keeps hold of {who(t)}"


def resolve(st: State, ref: str) -> Token:
    """A token by id, or a 1x1 pseudo-token for a square name (for distances)."""
    try:
        return token(st, ref)
    except CombatError:
        x, y = parse_pos(ref, st)
        return {"x": x, "y": y, "size": 1}


def cmd_dist(args: Args, st: State) -> str:
    """Distance in feet between two tokens or squares."""
    a, b = resolve(st, args.a), resolve(st, args.b)
    return f"{args.a} ↔ {args.b}: {feet_between(a, b)} ft"


def cmd_threat(args: Args, st: State) -> str:
    """Who threatens a token, and which pairs flank it."""
    t = token(st, args.token)
    th = [o for o in st["tokens"] if threatens(o, t)]
    if not th:
        return f"{t['token']} is not threatened"
    out = [f"{t['token']} threatened by: {', '.join(label(o) for o in th)}"]
    pairs = [(label(a), label(b)) for i, a in enumerate(th) for b in th[i + 1:] if flanks(a, b, t)]
    if pairs:
        out.append("Flanked by: " + "; ".join(f"{a} + {b}" for a, b in pairs) + " (+2 melee for each)")
    return "\n".join(out)


def cmd_hp(args: Args, st: State) -> str:
    """Change a token's HP (healing or damage outside an attack) and log it."""
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


def cmd_cond(args: Args, st: State) -> str:
    """Add a condition or effect (optionally timed, with modifiers or ongoing damage), or remove one."""
    c = token(st, args.token)
    if args.action == "add":
        mods = {k: v for k, v in (("atk", args.atk), ("ac", args.ac), ("save", args.save),
                                  ("dmg", args.dmg), ("check", args.check)) if v}
        R.add_condition(st, c, args.text, rounds=args.rounds, mods=mods or None, ongoing=args.ongoing)
        if not c.get("hidden"):
            dur = f" for {args.rounds} round{'s' if args.rounds != 1 else ''}" if args.rounds else ""
            event(st, f"{who(c)} is {args.text}{dur}")
        known = args.text.lower() in R.CONDITIONS
        note = "" if known or mods or args.ongoing else " (no built-in modifiers: tracked by name)"
    else:
        if not R.remove_condition(c, args.text):
            raise CombatError(f"{c['token']} has no condition '{args.text}'")
        if not c.get("hidden"):
            event(st, f"{who(c)} is no longer {args.text}")
        note = ""
    return f"{c['token']}: {', '.join(R.labels(c, st)) or 'no conditions'}{note}"


def _stabilize(st: State, c: Token, total_reported: int | None) -> str:
    """PF1e dying check: DC 10 Constitution check, with a penalty equal to the negative HP total."""
    if total_reported is None:
        mod = R.ability_mod(c.get("con"))
        total_c, detail, _ = _roll(f"1d20{mod:+d}")
        how = f"1d20{mod:+d} → {detail} = {total_c}"
    else:
        total_c, how = total_reported, f"reported {total_reported}"
    final = total_c + c["hp"]   # hp is negative: the penalty
    if final >= 10:
        R.add_condition(st, c, "stable")
        if not c.get("hidden"):
            event(st, f"{who(c)} stabilizes [{status(c)}]")
        return f"stabilization: {how}, {c['hp']} HP penalty → {final} vs DC 10: stable"
    c["hp"] -= 1
    if not c.get("hidden"):
        event(st, f"{who(c)} fails to stabilize and loses 1 HP [{who(c)}: {status(c)}]")
    return f"stabilization: {how}, penalty → {final} vs DC 10: fails, loses 1 HP (now {c['hp']})"


def cmd_stabilize(args: Args, st: State) -> str:
    """A dying token's stabilization check (a PC's total is required; NPCs roll)."""
    c = token(st, args.token)
    if c["hp"] >= 0:
        return f"{c['token']} isn't dying (HP {c['hp']})"
    if c.get("con") and c["hp"] <= -c["con"]:
        raise CombatError(f"{c['token']} is dead (HP {c['hp']}, Con {c['con']})")
    if c["side"] == "pc" and args.total is None:
        raise CombatError("a PC's stabilization check is the player's roll: pass --total N")
    return _stabilize(st, c, args.total)


def _save(st: State, c: Token, kind: str, dc: int, total_reported: int | None = None) -> tuple[bool, int, str]:
    """Roll (or take) a saving throw. Returns (success, total, how it was rolled). Natural 1 fails, 20 succeeds."""
    if total_reported is None:
        bonus = R.save_bonus(c, kind)
        if bonus is None:
            raise CombatError(f"{c['token']} has no {kind} save in its profile; pass --total")
        total_s, detail, _ = _roll(f"1d20{bonus:+d}")
        nat = _natural(detail)
        how = f"1d20{bonus:+d} → {detail} = {total_s}"
    else:
        total_s, nat, how = total_reported, None, f"reported {total_reported}"
    ok = nat != 1 and (nat == 20 or total_s >= dc)
    return ok, total_s, how


def cmd_save(args: Args, st: State) -> str:
    """A single save, or the resolution of a PC's pending area or spell save."""
    c = token(st, args.token)
    if c["side"] == "pc" and args.total is None:
        raise CombatError("a PC's save is the player's roll: pass --total N")
    pending = st.get("pending_saves", {}).get(c["token"])
    kind = args.kind or (pending or {}).get("kind")
    dc = args.dc or (pending or {}).get("dc")
    if not kind or not dc:
        raise CombatError("give the save type and --dc (or resolve a pending area save)")
    ok, total_s, how = _save(st, c, kind, dc, args.total)
    out = [f"{c['token']} {kind} save: {how} vs DC {dc}: {'success' if ok else 'failure'}"]
    shown = f"{who(c)} {kind} save: {total_s}" + (f" vs DC {dc}" if c["side"] in FRIENDLY else "")
    if pending:
        st["pending_saves"].pop(c["token"], None)
        dmg = pending["dmg"] // 2 if ok and pending.get("half") else (0 if ok else pending["dmg"])
        if dmg:
            dealt, absorbed = apply_damage(c, dmg)
            out.append(f"  {pending['name']}: {dmg} damage")
            event(st, f"{shown} — {'success, half' if ok else 'failure'}: {dmg} damage from {pending['name']} [{who(c)}: {status(c)}]")
        else:
            event(st, f"{shown} — success: no damage from {pending['name']}")
    else:
        event(st, f"{shown} — {'success' if ok else 'failure'}")
    return "\n".join(out)


def cmd_area(args: Args, st: State) -> str:
    """Resolve an area template: which tokens it covers and, with --save, damage and saves (NPCs roll,
    PCs get a pending question). Refuses a name that's the caster's spell or SLA (use cast/sla).
    """
    if args.frm and args.name and not getattr(args, "no_slot", False):
        # safety net: a spell or SLA of the caster must go through cast/sla so its use is spent
        prof = token(st, args.frm).get("profile") or {}
        nm = args.name.lower().replace("-", " ")
        spells = [s.lower() for sc in prof.get("spellcasting") or [] for lst in (sc.get("spells") or {}).values() for s in lst]
        slas = [s["name"].lower() for s in prof.get("sla") or []]
        if nm in spells or nm in slas:
            kind = "cast" if nm in spells else "sla"
            raise CombatError(f"{args.name!r} is a {'spell' if kind == 'cast' else 'spell-like ability'} of {args.frm}: "
                              f"use `{kind} {args.frm} \"{nm}\" --area \"{args.shape} {args.feet}\" …` so it's spent "
                              f"(or --no-slot if this isn't that spell)")
    if args.shape == "burst":
        if not args.at:
            raise CombatError("a burst needs --at SQUARE")
        squares = R.area_cells(st, "burst", args.feet, origin=parse_pos(args.at, st))
    else:
        if not (args.frm and args.toward):
            raise CombatError("a cone or line needs --from TOKEN --toward SQUARE")
        squares = R.area_cells(st, args.shape, args.feet, frm=token(st, args.frm),
                               toward=parse_pos(args.toward, st))
    hit = [o for o in R.tokens_in(st, squares) if o["token"] != args.frm]
    out = [f"{args.shape} {args.feet} ft covers {len(squares)} squares; creatures: "
           + (", ".join(label(o) for o in hit) or "none")]
    if not args.save:
        return "\n".join(out)
    if args.dc is None:
        raise CombatError("--save needs --dc")
    name = args.name or f"the {args.shape}"
    shown_name = getattr(args, "log_name", None) or name   # what the player's log and questions say
    dmg, detail, _ = _roll(args.dmg) if args.dmg else (0, "no damage", None)
    out.append(f"{name}: damage {args.dmg} → {detail} = {dmg}")
    if not any(not o.get("hidden") for o in hit):
        event(st, f"{shown_name} hits no one")
    pcs = []
    for o in hit:
        if o["side"] == "pc":
            st.setdefault("pending_saves", {})[o["token"]] = {
                "kind": args.save, "dc": args.dc, "dmg": dmg, "half": args.half, "name": shown_name}
            pcs.append(o)
            continue
        ok, total_s, how = _save(st, o, args.save, args.dc)
        taken = (dmg // 2 if args.half else 0) if ok else dmg
        out.append(f"  {label(o)} {args.save} {how} vs DC {args.dc}: {'success' if ok else 'failure'}, {taken} damage")
        if taken:
            apply_damage(o, taken)
        if not o.get("hidden"):
            shown = f"{who(o)} {args.save} save {total_s}" + (f" vs DC {args.dc}" if o["side"] in FRIENDLY else "")
            event(st, f"{shown_name}: {shown} — {'success' if ok else 'failure'}, {taken} damage [{who(o)}: {status(o)}]")
    if pcs:
        names = ", ".join(o["name"] for o in pcs)
        st["awaiting"] = f"{names}: roll a {args.save.capitalize()} save against {shown_name}"
        out.append(f"  PC saves pending ({names}): ask the player, then `save TOKEN --total N` (question set)")
    return "\n".join(out)


def cmd_order(args: Args, st: State) -> str:
    """Set a PC's standing order for attacks of opportunity."""
    c = token(st, args.token)
    st.setdefault("orders", {}).setdefault(c["token"], {})[args.kind] = args.value
    return f"{c['token']} standing order: {args.kind} {args.value}"


def cmd_init(args: Args, st: State) -> str:
    """Change a token's initiative (delay, ready)."""
    token(st, args.token)["init"] = args.value
    return f"{args.token} initiative → {args.value:g}"


def cmd_flag(args: Args, st: State) -> str:
    """Reveal, hide or remove a token."""
    c = token(st, args.token)
    if args.command == "remove":
        c["removed"] = True
    else:
        c["hidden"] = args.command == "hide"
        if args.command == "reveal":
            event(st, f"{who(c)} appears!")
    return f"{c['token']}: {args.command}"


def cmd_image(args: Args, st: State) -> str:
    """Render the PNG player view now, and optionally turn auto-rendering on or off."""
    if args.mode:
        st["image"] = args.mode == "on"
    path = render_image(st, image_path(args.campaign))
    rel = path.relative_to(PROJECT)
    return f"Rendered {rel}" + (f" (auto-render {args.mode})" if args.mode else "")


def cmd_end(args: Args, st: State) -> str:
    """End the encounter: summary and XP, PC HP back onto their sheets, the combat log into the session log,
    and archive the state.
    """
    defeated = [c for c in st["tokens"] if c["side"] not in FRIENDLY and (c["hp"] <= 0 or c.get("removed"))]
    xp = sum(XP_BY_CR.get(str(c.get("cr")), 0) for c in defeated)
    out = [f"Encounter over after {st['round']} round(s)."]
    for c in st["tokens"]:
        status = "removed" if c.get("removed") else f"HP {c['hp']}/{c['max_hp']}"
        cr = f", CR {c['cr']}" if c.get("cr") else ""
        out.append(f"  {c['token']} {c['name']}: {status}{cr}")
    out.append(f"XP from defeated/removed enemies with CR: {xp} (check removed ones: fled ≠ defeated unless overcome)")
    # bookkeeping: PC HP back to their sheets, the combat log into the session log
    for c in st["tokens"]:
        ref = c.get("ref") or ""
        if c["side"] == "pc" and "players/characters/" in ref:
            sheet = PROJECT / ref
            if sheet.exists():
                text = sheet.read_text(encoding="utf-8")
                new, n = re.subn(r"(\*\*HP:\*\*\s*)-?\d+(\s*/\s*\d+)", rf"\g<1>{c['hp']}\g<2>", text, count=1)
                if n:
                    sheet.write_text(new, encoding="utf-8")
                    out.append(f"  {c['name']}'s sheet: HP set to {c['hp']}")
    logs = sorted((PROJECT / "campaigns" / args.campaign / "dm" / "session-log").glob("session-*.md"))
    if logs and st.get("events"):
        lines = [f"- R{e['round']}: {e['text']}" for e in st["events"]]
        with logs[-1].open("a", encoding="utf-8") as f:
            f.write(f"\n### Combat log ({datetime.now():%H:%M}, {st['round']} rounds, XP {xp})\n" + "\n".join(lines) + "\n")
        out.append(f"  combat log appended to {logs[-1].name}")
    path = state_path(args.campaign)
    archive = path.parent / "archive" / f"{datetime.now():%Y%m%d-%H%M}.json"
    archive.parent.mkdir(exist_ok=True)
    path.rename(archive)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the process exit code."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", "--campaign", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    n = sub.add_parser("new"); n.add_argument("mapfile", nargs="?"); n.add_argument("--blank"); n.add_argument("--force", action="store_true")
    a = sub.add_parser("add")
    a.add_argument("token"); a.add_argument("name"); a.add_argument("--pos", required=True)
    a.add_argument("--init", help="initiative value, or 'roll' (from the profile)"); a.add_argument("--hp", type=int)
    a.add_argument("--ac", type=int); a.add_argument("--touch", type=int); a.add_argument("--ff", type=int)
    a.add_argument("--side", choices=["enemy", "pc", "ally"], default="enemy")
    a.add_argument("--size", type=int, choices=[1, 2, 3, 4]); a.add_argument("--reach", type=int)
    a.add_argument("--speed", type=int); a.add_argument("--cr"); a.add_argument("--hidden", action="store_true")
    a.add_argument("--ref", help="stat block or character sheet with a combat-profile block")
    a.add_argument("--profile", help="profile JSON (merged over --ref's)")
    a.add_argument("--dr", type=int, help="hardness or damage reduction")
    a.add_argument("--con", type=int, help="Constitution score (PCs/allies): dead at -Con HP")
    at = sub.add_parser("attack"); at.add_argument("attacker"); at.add_argument("target")
    at.add_argument("--roll"); at.add_argument("--dmg"); at.add_argument("--crit", type=int, default=20)
    at.add_argument("--mult", type=int, default=2); at.add_argument("--total", type=int)
    at.add_argument("--damage", type=int); at.add_argument("--nat", type=int, choices=[1, 20])
    at.add_argument("--confirm", type=int); at.add_argument("--name"); at.add_argument("--ac", type=int)
    at.add_argument("--nonlethal", action="store_true"); at.add_argument("--no-crit", action="store_true")
    at.add_argument("--with", dest="with_", help="attack name from the attacker's profile")
    at.add_argument("--full", action="store_true", help="full attack (the profile's full_attack or iterative bonuses)")
    at.add_argument("--charge", action="store_true"); at.add_argument("--touch", action="store_true")
    at.add_argument("--aoo", action="store_true", help="an attack of opportunity (uses up one)")
    at.add_argument("--ranged", action="store_true", help="with --roll/--total: it's a ranged attack")
    at.add_argument("--range-inc", type=int, help="with --roll: range increment in feet")
    lg = sub.add_parser("log"); lg.add_argument("text")
    ak = sub.add_parser("ask"); ak.add_argument("question", nargs="?"); ak.add_argument("--clear", action="store_true")
    ev = sub.add_parser("events"); ev.add_argument("--all", action="store_true")
    s = sub.add_parser("show"); s.add_argument("--dm", action="store_true")
    sub.add_parser("next")
    m = sub.add_parser("move"); m.add_argument("token"); m.add_argument("pos")
    m.add_argument("--step", action="store_true", help="a 5-foot step (no AoO)")
    m.add_argument("--no-aoo", action="store_true", help="don't roll NPC attacks of opportunity")
    sb = sub.add_parser("stabilize"); sb.add_argument("token"); sb.add_argument("--total", type=int)
    sv = sub.add_parser("save"); sv.add_argument("token"); sv.add_argument("kind", nargs="?", choices=["fort", "ref", "will"])
    sv.add_argument("--dc", type=int); sv.add_argument("--total", type=int)
    ar = sub.add_parser("area"); ar.add_argument("shape", choices=["burst", "cone", "line"]); ar.add_argument("feet", type=int)
    ar.add_argument("--at"); ar.add_argument("--from", dest="frm"); ar.add_argument("--toward")
    ar.add_argument("--save", choices=["fort", "ref", "will"]); ar.add_argument("--dc", type=int)
    ar.add_argument("--dmg"); ar.add_argument("--half", action="store_true"); ar.add_argument("--name")
    ar.add_argument("--no-slot", action="store_true", help="not a spell/SLA of the caster (e.g. a breath weapon)")
    pf = sub.add_parser("profile"); pf.add_argument("action", choices=["check"]); pf.add_argument("files", nargs="+")
    for nm in ("cast", "sla"):
        cp = sub.add_parser(nm); cp.add_argument("token"); cp.add_argument("spell" if nm == "cast" else "name")
        cp.add_argument("--defensive", action="store_true", help="cast defensively (concentration DC 15 + 2x level)")
        cp.add_argument("--no-provoke", action="store_true", help="it doesn't provoke (e.g. a quickened spell)")
        if nm == "cast":
            cp.add_argument("--level", type=int); cp.add_argument("--class", dest="cls")
        cp.add_argument("--area", help='template, e.g. "cone 15", "burst 20", "line 60"')
        cp.add_argument("--at", help="burst center square"); cp.add_argument("--toward", help="cone/line direction square")
        cp.add_argument("--target", help="a single target token")
        cp.add_argument("--save", choices=["fort", "ref", "will"]); cp.add_argument("--dmg")
        cp.add_argument("--half", action="store_true"); cp.add_argument("--dc", type=int, help="override the DC")
    sub.add_parser("spells").add_argument("token")
    pv = sub.add_parser("provoke"); pv.add_argument("token"); pv.add_argument("--reason", default="provoking")
    pv.add_argument("--no-aoo", action="store_true")
    od = sub.add_parser("order"); od.add_argument("token"); od.add_argument("kind", choices=["aoo"])
    od.add_argument("value", choices=["always", "never", "ask"])
    d = sub.add_parser("dist"); d.add_argument("a"); d.add_argument("b")
    t = sub.add_parser("threat"); t.add_argument("token")
    h = sub.add_parser("hp"); h.add_argument("token"); h.add_argument("delta"); h.add_argument("--why")
    c = sub.add_parser("cond"); c.add_argument("token"); c.add_argument("action", choices=["add", "remove"]); c.add_argument("text")
    c.add_argument("--rounds", type=int); c.add_argument("--ongoing")
    for k in ("atk", "ac", "save", "dmg", "check"):
        c.add_argument(f"--{k}", type=int)
    i = sub.add_parser("init"); i.add_argument("token"); i.add_argument("value", type=float)
    for name in ("reveal", "hide", "remove"):
        sub.add_parser(name).add_argument("token")
    sub.add_parser("end")
    sub.add_parser("endturn").add_argument("token")
    im = sub.add_parser("image"); im.add_argument("mode", nargs="?", choices=["on", "off"])
    dp = sub.add_parser("do"); dp.add_argument("cmds", nargs="+")
    mn = sub.add_parser("maneuver"); mn.add_argument("attacker"); mn.add_argument("target")
    mn.add_argument("kind", choices=MANEUVERS)
    mn.add_argument("--total", type=int, help="the player's check total (PC), or an Escape Artist total")
    mn.add_argument("--nat", type=int, choices=[1, 20]); mn.add_argument("--cmb", type=int, help="NPC CMB if its profile has none")
    mn.add_argument("--cmd", type=int, help="override the target's CMD"); mn.add_argument("--mod", type=int, help="other situational modifier")
    mn.add_argument("--charge", action="store_true"); mn.add_argument("--grab", action="store_true", help="grab: +4, no AoO")
    mn.add_argument("--aoo", action="store_true", help="trip/disarm/sunder made as an attack of opportunity")
    mn.add_argument("--no-provoke", action="store_true", help="it doesn't provoke (a similar ability)")
    mn.add_argument("--aoo-damage", type=int, help="damage the provoked AoO dealt (after asking a PC target)")
    mn.add_argument("--option", choices=["pin", "damage", "move", "tie"], help="what a successful maintain does")
    mn.add_argument("--to", help="reposition: target's square; grapple move: grappler's square")
    mn.add_argument("--place", help="grapple move: the target's square next to the grappler")
    mn.add_argument("--follow", action="store_true", help="bull rush: move along with the target")
    mn.add_argument("--condition", help="dirty trick: " + ", ".join(DIRTY_TRICKS))
    mn.add_argument("--item", help="disarm/steal/sunder: the item"); mn.add_argument("--dmg", help="damage dice (NPC)")
    mn.add_argument("--damage", type=int, help="damage (PC)"); mn.add_argument("--nonlethal", action="store_true")
    mn.add_argument("--reverse", action="store_true", help="escape: become the grappler instead")
    mn.add_argument("--reach", type=int, help="reach of the weapon used, if longer (whip, reach weapon)")
    for sp in (at, m, pv, ar, mn, sub.choices["cast"], sub.choices["sla"]):
        sp.add_argument("--out-of-turn", action="store_true",
                        help="the actor isn't the current one: a readied or immediate action, forced movement, setup")
    args = p.parse_args(argv)

    handlers = {"add": cmd_add, "next": cmd_next, "move": cmd_move, "dist": cmd_dist,
                "threat": cmd_threat, "hp": cmd_hp, "cond": cmd_cond, "init": cmd_init,
                "reveal": cmd_flag, "hide": cmd_flag, "remove": cmd_flag, "end": cmd_end,
                "image": cmd_image, "attack": cmd_attack, "log": cmd_log, "events": cmd_events,
                "ask": cmd_ask, "stabilize": cmd_stabilize, "save": cmd_save, "area": cmd_area,
                "order": cmd_order, "cast": cmd_cast, "sla": cmd_sla, "spells": cmd_spells,
                "provoke": cmd_provoke, "endturn": cmd_endturn, "maneuver": cmd_maneuver}
    if args.command == "profile":
        return cmd_profile(args)
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
        if args.command == "next" and os.environ.get("CLAUDE_DM_MODE") == "play":
            raise CombatError("the interface advances turns in this mode: don't run `next`. Resolve only the "
                              "current actor, then stop")
        check_actor(args, st)
        if args.command == "show":
            print(render(st, dm=args.dm))
            return 0
        if args.command not in ("ask", "dist", "threat", "events", "image"):
            st.pop("awaiting", None)   # any real change answers an open question
        result = handlers[args.command](args, st)
        ended = clean_grapples(st)
        if ended:
            result += "\n" + "\n".join(ended)
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
