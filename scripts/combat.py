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
Action economy (each turn: standard + move, or two moves, or one full-round action; one swift; one
5-foot step if it doesn't otherwise move). Commands charge the actor: attack = standard (a second attack
turns it into a full attack if it hasn't moved), --full = full-round, cast/sla = --time (default
standard), maneuvers by kind, movement by distance (a stretch can't be split around a standard action).
Every action reports what's left. --override: a feat or ability changes it (Spring Attack, …).
  act TOKEN standard|move|full|swift|immediate|free ["what"] [--provokes] [--log TEXT]
                                  any other action ("draw weapon", "drink potion"); "stand up" removes
                                  prone and provokes; an immediate action off-turn takes the next swift
  move TOKEN POS --as charge|withdraw|run   movement as part of that full-round action
                                  (a charge: --target T; straight, clear, to the closest square it can attack T from)
  actions TOKEN                   what the creature has left this turn
  undo                            take back the last command if it was the player's input (e.g. a roll
                                  they correct: forgot flanking), then enter it again. NPC rolls stand
  options TOKEN [--target T] [--area "burst 20" --range 100]
                                  tactical options (DM only): ranked turn plans with rough expected values
                                  (damage incl. sneak attack, spells and abilities with effect data,
                                  support, AoO risk, exposure), then per target the squares that threaten
                                  it and the d20 roll needed there, charge lanes, ranged spots, retreats
  surprise on --unaware C,k1 | off
                                  the surprise round: the unaware (tokens, or party / enemies) get no turn and
                                  stay flat-footed; the aware act with one standard or move action each
Prepared encounters (dm/combat/encounters/<name>.md, a ```encounter block; library/general/encounter.schema.json)
  encounter list | check [NAME …] list them, or validate (map, profiles, squares, lights) without creating anything
  setup NAME --init C=17 [--place C=E5] [--force]
                                  build the whole fight in one go: map, lighting, combatants (NPC
                                  initiative rolled), light sources; prints tactics, morale, exit ramp
Play
  show [--dm]                     player view (paste verbatim) / DM view (never paste)
  next                            advance the turn pointer. Also: ends expiring conditions, applies
                                  ongoing damage, resets AoOs and movement, reminds of dying checks.
                                  In play (CLAUDE_DM_MODE=play) only the web interface runs it.
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
  attack ATT TGT --total 17 [--damage 9] [--nat 20|1] [--confirm 18] [--name rapier] [--touch]
                                  PC attack with the player's numbers against the hidden AC (target-side
                                  modifiers applied; attacker-side ones are listed as reminders). Without
                                  --damage a hit waits for the player's damage roll:
  damage ATT N [--nonlethal]      the player's damage for that hit (DR, minimum damage, the log line)
  wield TOKEN WEAPON [--drop W | --sheathe W]
                                  draw a weapon (a move action; with BAB +1 it rides on a move action spent
                                  on movement; Quick Draw: free). Attacks need the weapon in hand; only
                                  melee weapons in hand (or natural attacks) threaten
  pickup TOKEN ITEM               pick up an item from the ground next to it (a move action, provokes)
  briefing TOKEN [--round N]      the tactical options and turn plans an NPC's step was given (DM only)
       ammunition: an attack with "ammo": N (creatures) or the PC profile's "ammo" map counts shots and
       throws, reports what's left and refuses an empty one (--override if it found more)
       all: [--no-crit] (mercy: treat a crit as a normal hit)  [--ac N] (override)
  area burst|cone|line FEET (--at D4 | --from TOKEN --toward E5) [--save ref --dc 13 --dmg 2d6
       [--half] [--name "burning hands"]]
                                  which tokens a template covers; with --save, rolls the damage once,
                                  saves for NPCs from their profiles, and opens a question for PC saves
  save TOKEN fort|ref|will --dc N [--total N]
                                  NPC: rolled from the profile. PC: the player's total. Resolves a
                                  pending area-effect save for that token, if there is one
  sheet-hp CHARACTER +N|-N|=N --why "…"
                                  a character's HP outside a fight (healing, rest, a trap): the sheet's
                                  HP line, logged in the live log (in a fight: hp)
  first-aid HEALER TARGET [--total N]
                                  a Heal check (DC 15, standard action, provokes) on a dying creature next
                                  to the healer: success makes it stable with help (NPCs roll skills.heal)
  stabilize TOKEN [--total N]     dying check: DC 10, minus the negative HP total (the PC's --total;
                                  NPCs roll). Failure costs 1 HP; success adds "stable"
  plan TOKEN "ORDERS" | --clear  the player's standing orders for a companion or ally ("grapple Dessick, keep
                                  him from the satchel"): shown at the top of its briefing until cleared
  order TOKEN aoo always|never|ask
                                  a PC's standing order for attacks of opportunity
  cast TOKEN "SPELL" [--level N] [--class X] [--defensive] [--no-provoke]
                                  an NPC casts: checks and spends a slot (spontaneous) or a prepared copy,
                                  provokes AoOs when threatened (or --defensive: concentration DC 15+2x
                                  level), concentration after damage, reports the save DC. The log only
                                  says "casts a spell" (identifying it is a Spellcraft matter)
  sla TOKEN "NAME" [--defensive] [--no-provoke]
                                  the same for a spell-like ability (uses per day). Both take the
                                  effect (area, save, damage, healing, condition) from the profile's
                                  spellcasting "effects" / the SLA's "effect" when it's there
  ability TOKEN "NAME" [--target T] [--at SQ] [--toward SQ]
                                  a special ability from the profile's "abilities" (bardic performance,
                                  channel energy, breath weapon): spends a use, applies the buff, healing,
                                  damage or condition; a performance is kept up with the same command
  spells TOKEN                    remaining slots, prepared spells and SLA uses (DM view)
  provoke TOKEN [--reason "drinking a potion"]
                                  resolve the AoOs a creature provokes right now (e.g. a PC casting)
  profile check FILE [FILE …]     validate combat-profile blocks against the system's schema
                                  (library/<system>/combat-profile.schema.json); add does it too
  log "TEXT"                      add a player-safe line to the combat log
  ask "QUESTION"                  mark that the DM waits for a player decision mid-round (a reaction,
                                  an AoO, a stabilization check). Pauses auto-combat in the web UI;
                                  cleared by the next state-changing command (or: ask --clear)
  events                          print combat log lines not shown yet
  hp TOKEN DELTA                  e.g. hp g2 -7, hp V +5
  cond TOKEN add NAME [--rounds N] [--atk N --ac N --save N --dmg N] [--ongoing "1d6"]
  cond TOKEN remove NAME          conditions and effects. Known conditions (shaken, prone, blinded,
                                  invisible, …) apply their modifiers automatically; custom effects take
                                  explicit ones (e.g. bless: --atk 1 --rounds 30). With --rounds they end
                                  by themselves; --ongoing damage is rolled at the start of its turn
  init TOKEN VALUE                change initiative (delay / ready)
  reveal TOKEN / hide TOKEN       toggle visibility to the players
  remove TOKEN                    take a token off the board (fled, dismissed)
  flee TOKEN                      flee the battlefield (house rule): a full-round action, from the map edge, not while threatened;
                                  it's gone at the start of its next turn, unless a hit or a grapple stops it first
  end                             finish the encounter: summary + XP, archive the state
  do "CMD" ["CMD" ...]            run several commands in one call, e.g.
                                  do "move g1 D4" "hp V -6" "next" "show"

Map files: one line per row, one character per square, no spaces between squares (or generate one:
`map TEMPLATE`, see below). Lines starting with // are notes.
  .  floor/ground   #  wall (blocks)   +  door   =  bridge   ^  difficult (dense rubble, cave floor: 2)
  ~  shallow water/bog (2)   W  deep water (swim)   _  pit / chasm   (space) outside (blocks)
  T  tree (partial cover +2 AC to whoever stands in it)   O  boulder / massive tree / pillar (blocks)
  "  undergrowth, tall grass (2, 20% concealment)   &  heavy undergrowth (4, 30% concealment)
  Y  tree in undergrowth (2, partial cover + 20%)   -  low wall / fence / log (3, cover within 30 ft)
  m  furniture (3)
Columns are lettered A-Z (max 26 wide), rows numbered from 1.
  terrain AREA=TERRAIN [...]      paint the current map: a square (C3=W) or rectangle (E5:H9=.); tokens on a
                                  square that becomes impassable move to the nearest free one
  map TEMPLATE [--size 24x14] [--seed N] [--density sparse|medium|dense] [--time day|dusk|night]
       [--name NAME] [--start] [--force]
                                  generate a battle map that fits the scene, save it to dm/combat/maps/, and
                                  with --start begin the encounter on it. Templates: forest-road, forest,
                                  clearing, field, river, village, tavern, cave, ruins, camp, swamp. Prints
                                  where the party is, ambush spots (cover/concealment) and light sources
Tokens: a PC uses the first letter of its name (Corin -> C); others lowercase + digit (g1, s1).

The combat log (events) is what the player sees about attacks, damage and conditions. The web
interface shows it next to the map. The numbers shown: attack totals (against AC only for PCs and allies),
damage per hit (and what hardness/DR absorbed), PC/ally HP, enemy health in words.
"""
from __future__ import annotations

import argparse
import contextlib
import io
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
import vision as V  # noqa: E402

Token = R.Token    # one combatant in the combat state
State = R.State    # the whole combat state (dm/combat/current.json)
Square = R.Square  # (x, y) grid coordinates, 0-based
Args = argparse.Namespace

PROJECT = Path(__file__).resolve().parents[1]
# Map characters: (name, movement cost in squares; None = impassable). What else they do (cover,
# concealment, blocking sight) is in combat_rules.TERRAIN_FX / LINE_BLOCKERS; the rulings are in
# library/pf1e/house-rules/terrain.md.
TERRAIN = {
    ".": ("floor", 1), "+": ("door", 1), "=": ("bridge", 1),
    "^": ("difficult", 2), "~": ("shallow water", 2), "T": ("tree", 1),
    '"': ("undergrowth", 2), "&": ("heavy undergrowth", 4), "Y": ("tree in undergrowth", 2),
    "-": ("low wall", 3), "m": ("furniture", 3),
    "#": ("wall", None), "O": ("boulder", None), "_": ("pit", None), "W": ("deep water", None), " ": ("outside", None),
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
    # a name instead of a token id ("Harl Dessick", "dessick"): exact, then a unique part
    want = tok.strip().lower()
    alive = [c for c in st["tokens"] if not c.get("removed")]
    for test in (lambda c: c["name"].lower() == want, lambda c: want in c["name"].lower()):
        hits = [c for c in alive if test(c)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise CombatError(f"'{tok}' fits several: " + ", ".join(f"{c['token']} ({c['name']})" for c in hits)
                              + ": use the token id")
    raise CombatError(f"no token '{tok}' (tokens: " + ", ".join(f"{c['token']} {c['name']}" for c in alive) + ")")


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
    return path_route(st, mover, dest)[0]


def diag_parity(st: State, c: Token) -> int:
    """Where the creature is in the 5-10-5 diagonal count: 1 if its next diagonal costs 10 ft.
    The count runs through all of its movement in one turn (a double move included) and starts
    over on its next turn (table ruling, library/pf1e/rules/movement.md: PF1e doesn't say)."""
    return c.get("diag_parity", 0) if st.get("turn") == c["token"] else 0


def path_route(st: State, mover: Token, dest: Square) -> tuple[int, list[Square]]:
    """The cheapest legal move: (feet, the squares from start to dest, both included)."""
    feet, route, _parity = path_route_parity(st, mover, dest)
    return feet, route


def path_route_parity(st: State, mover: Token, dest: Square) -> tuple[int, list[Square], int]:
    """path_route, plus the diagonal count's parity at the end (for the rest of the turn)."""
    import heapq
    start = (mover["x"], mover["y"])
    p0 = diag_parity(st, mover)

    def footprint_ok(x: int, y: int, final: bool) -> bool:
        """Whether the mover's whole footprint fits at (x, y); the final square must also be unoccupied."""
        for cx, cy in cells(mover, (x, y)):
            if cost(st, cx, cy) is None or blocked_by_hostile(st, mover, cx, cy):
                return False
            if final and occupied(st, mover, cx, cy):
                return False
        return True

    def terrain_ok(x: int, y: int) -> bool:
        """Whether the footprint at (x, y) is clear of walls (creatures don't block a diagonal's corner)."""
        return all(cost(st, cx, cy) is not None for cx, cy in cells(mover, (x, y)))

    def step_cost(x: int, y: int) -> int:
        """The highest movement cost under the mover's footprint at (x, y)."""
        return max(cost(st, cx, cy) or 1 for cx, cy in cells(mover, (x, y)))   # footprint_ok ruled out None

    if not footprint_ok(*dest, final=True):
        raise CombatError(f"{fmt_pos(*dest)} is blocked or occupied")
    best = {(start, p0): 0}
    came: dict[tuple[Square, int], tuple[Square, int]] = {}
    heap = [(0, start, p0)]
    while heap:
        feet, (x, y), parity = heapq.heappop(heap)
        if (x, y) == dest:
            route, key = [dest], ((x, y), parity)
            while key in came:
                key = came[key]
                route.append(key[0])
            return feet, route[::-1], parity
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
                if diag and (not terrain_ok(x + dx, y) or not terrain_ok(x, y + dy)):
                    continue  # can't cut a wall's corner; past a creature's corner is fine (CRB p. 192)
                mult = step_cost(nx, ny)
                if diag:
                    squares, npar = (mult + mult // 2 if mult > 1 else (1 if parity == 0 else 2)), 1 - parity   # costly terrain: x1.5 on a diagonal
                else:
                    squares, npar = mult, parity
                nf = feet + 5 * squares
                key = ((nx, ny), npar)
                if nf < best.get(key, 1e9):
                    best[key] = nf
                    came[key] = ((x, y), parity)
                    heapq.heappush(heap, (nf, (nx, ny), npar))
    raise CombatError(f"no legal path to {fmt_pos(*dest)}")


def threatens(a: Token, t: Token) -> bool:
    """Whether `a` threatens `t`: active, hostile to it, and within reach (reach-10 diagonal rule included)."""
    if not active(a) or a is t or a.get("no_threat"):
        return False
    if (a["side"] in FRIENDLY) == (t["side"] in FRIENDLY):
        return False
    reach = threat_reach(a)   # only with a melee weapon in hand, natural attacks, or trained unarmed strikes
    if reach is None:
        return False
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
    if V.has_lighting(st):
        L = V.light_state(st)
        srcs = []
        for src in L.get("sources", []):
            carrier = next((o for o in st["tokens"] if o["token"] == src.get("on")), None)
            if carrier and carrier.get("hidden") and not dm:
                where = "carried by someone unseen"
            else:
                where = f"carried by {carrier['token']}" if carrier else f"at {fmt_pos(*src['at'])}"
            srcs.append(f"{src['kind']} {where}")
        out.append(f"    Light: {L.get('ambient')} ambient" + (f"; {'; '.join(srcs)}" if srcs else ""))
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


# ---------- map data for the web interface ----------

TERRAIN_NAMES = {"#": "wall", "+": "door", "^": "difficult", "~": "shallow water", "T": "tree (partial cover)",
                 '"': "undergrowth (concealment)", "&": "heavy undergrowth (concealment)", "Y": "tree in undergrowth",
                 "-": "low wall / fence (cover)", "m": "furniture", "O": "boulder / massive tree", "W": "deep water",
                 "_": "pit", "=": "bridge"}


# ---------- turn marks: what the map shows of the latest turn ----------
# The actor's movement, the areas of its area effects, and whom it attacked or targeted (spells,
# maneuvers, buffs, heals). A new turn clears them; when the interface moves on to a PC's turn, the
# last NPC's marks stay until the PC acts, so the player sees what just happened. Only the actor's
# own actions count (not attacks of opportunity or readied actions on others' turns). A turn that
# can't be acted on (dazed, unconscious, helpless) keeps the previous actor's marks.

def marks_for(st: State, c: Token) -> dict[str, Any]:
    """The turn marks of `c`, started fresh if they belonged to someone else."""
    m = st.get("turn_marks")
    if not m or m.get("token") != c["token"]:
        m = st["turn_marks"] = {"token": c["token"], "areas": [], "targets": []}
    return m


def mark_target(st: State, a: Token, t: Token, kind: str) -> None:
    """Record that the actor attacked or targeted `t` on its own turn (kind: attack, spell, help)."""
    if st.get("turn") != a["token"] or t is a:
        return
    m = marks_for(st, a)
    if not any(x["to"] == t["token"] and x["kind"] == kind for x in m["targets"]):
        m["targets"].append({"to": t["token"], "kind": kind})


def mark_area(st: State, a: Token | None, squares: list[Square]) -> None:
    """Record the squares an area effect of the actor covered, on its own turn."""
    if a is None or st.get("turn") != a["token"]:
        return
    marks_for(st, a)["areas"].append([list(q) for q in squares])


def turn_marks(st: State) -> dict[str, Any] | None:
    """The player-safe marks of the latest turn for the map: {token, side, size, x, y, path, areas,
    targets: [{to, kind, x, y, size}]}, or None (nothing yet, or a hidden actor)."""
    m = st.get("turn_marks")
    if not m:
        line = movement_line(st)   # an older fight: just the movement
        return dict(line, areas=[], targets=[]) if line else None
    a = next((t for t in st["tokens"] if t["token"] == m["token"]), None)
    if a is None or a.get("hidden") or a.get("removed"):
        return None
    if a["token"] == st.get("turn"):
        path = a.get("turn_path") or []
    else:
        lm = st.get("last_move") or {}
        path = lm.get("path") or [] if lm.get("token") == a["token"] else []
    targets = []
    for x in m["targets"]:
        t = next((o for o in st["tokens"] if o["token"] == x["to"]), None)
        if t is not None and not t.get("hidden") and not t.get("removed"):
            targets.append({"to": t["token"], "kind": x["kind"], "x": t["x"], "y": t["y"], "size": t.get("size", 1)})
    if len(path) < 2 and not m["areas"] and not targets:
        return None
    return {"token": a["token"], "side": a["side"], "size": a.get("size", 1), "x": a["x"], "y": a["y"],
            "path": [list(p) for p in path] if len(path) > 1 else [], "areas": m["areas"], "targets": targets}


def movement_line(st: State) -> dict[str, Any] | None:
    """The movement to draw on the map: the current actor's path this turn if it has moved, else
    the last actor's. Never a hidden creature's. Returns {token, side, size, path} or None."""
    cur = next((t for t in st["tokens"] if t["token"] == st.get("turn")), None)
    cands: list[tuple[Token, list[Any]]] = []
    if cur is not None and len(cur.get("turn_path") or []) > 1:
        cands.append((cur, cur["turn_path"]))
    if st.get("last_move"):
        t = next((x for x in st["tokens"] if x["token"] == st["last_move"]["token"]), None)
        if t is not None:
            cands.append((t, st["last_move"]["path"]))
    # a hidden mover is skipped, not blanked: the line vanishing would give it away
    pick = next(((t, p) for t, p in cands if not t.get("hidden") and not t.get("removed")), None)
    if pick is None:
        return None
    t, path = pick
    return {"token": t["token"], "side": t["side"], "size": t.get("size", 1), "path": [list(p) for p in path]}


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
            s += ", stable" if R.has(c, "stable") else ", dying"
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
    if R.remove_condition(c, "fleeing"):   # a hit stops the flight (house rule), even one DR absorbs
        c["flight_stopped"] = "hit"
    return dealt, absorbed


RNG: Any = None   # tests set a seeded random.Random here; play uses secrets.SystemRandom


def _roll(expr: str) -> tuple[int, str, list[str]]:
    """Roll a dice expression with roll.py's evaluator. Returns (total, detail, flags)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import secrets
    from roll import evaluate
    total, detail, flags = evaluate(expr, RNG or secrets.SystemRandom())
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


def denied_dex(st: State, a: Token, t: Token) -> str | None:
    """Why `t` is denied its Dex bonus against `a` (flat-footed, a condition, can't see the attacker), or None."""
    prof = t.get("profile") or {}
    if R.flag(t, "flatfooted"):
        return ", ".join(R.condition_names(t, ("flatfooted",))) or "flat-footed"
    if not t.get("acted") and not prof.get("uncanny_dodge"):
        return "flat-footed (hasn't acted yet)"
    if R.flag(t, "dex_zero"):
        return "helpless"
    if (V.concealment(st, t, a)[0] >= 50 or R.has(a, "invisible")) and not prof.get("uncanny_dodge"):
        return "can't see the attacker"
    return None


def sneak_attack(st: State, a: Token, t: Token, kind: str, miss: int) -> tuple[str | None, str | None]:
    """The sneak attack dice that apply to this hit, or (None, why not). Rules: the target is denied its
    Dex bonus or flanked by the attacker (melee); no concealment at all; ranged only within 30 ft;
    creatures immune to precision damage take none (library/pf1e/rules/combat-abilities.md)."""
    dice = (a.get("profile") or {}).get("sneak_attack")
    if not dice:
        return None, None
    tp = t.get("profile") or {}
    immune = " ".join(str(x).lower() for x in (tp.get("immune") or []))
    if "precision" in immune or "sneak" in immune:
        return None, "the target is immune to precision damage"
    if miss:
        return None, f"the target has concealment ({miss}%)"
    if kind == "ranged" and feet_between(a, t) > 30:
        return None, "ranged, and more than 30 ft away"
    if denied_dex(st, a, t):
        return dice, None
    can_flank = not tp.get("improved_uncanny_dodge") and "flanking" not in immune
    if kind == "melee" and can_flank and flanking(st, a, t):
        return dice, None
    return None, "the target is neither flanked nor denied its Dex"


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
    blind, blind_why = V.concealment(st, t, a)   # can the defender see its attacker?
    unseen = blind >= 50 or R.has(a, "invisible")
    if unseen and not flat and not uncanny:
        flat = True
        dmnotes.append(f"{t['token']} can't see {a['token']} ({blind_why if blind >= 50 else 'invisible'}): loses its Dex bonus")
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
    if blind >= 50 and blind_why == "darkness":
        ac -= 2
        notes.append("target can't see in the dark")
    elif unseen:
        notes.append("target can't see the attacker")
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
    elif R.partial_cover(st, t):   # standing in a tree's square (CRB pg. 425)
        ac += 2
        notes.append("partial cover (tree)")
    miss = max((R.cond_effects(x).get("concealment", 0) for x in R.conditions(t)), default=0)
    lmiss, lwhy = V.concealment(st, a, t)   # lighting, from the attacker's eyes (doesn't stack)
    if lmiss > miss:
        miss = lmiss
        dmnotes.append(f"{miss}% miss chance from {lwhy}")
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
        held = next((n for n in weapons(a) if args.name and n.lower() == args.name.lower()), None)
        if held and not at_hand(a, held) and not args.aoo:
            raise CombatError(f"{a['name']} isn't holding the {held} (in hand: {', '.join(wielding(a)) or 'nothing'}): "
                              f"`wield {a['token']} \"{held}\"` first (a move action; with BAB +1 it rides on a move)")
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
            if key and not at_hand(a, key):
                raise CombatError(f"{a['token']} isn't holding its {key} (in hand: {', '.join(wielding(a)) or 'nothing'}): "
                                  f"draw it first, `wield {a['token']} \"{key}\"` (a move action; with BAB +1 it rides on "
                                  f"a move; --drop the other weapon if its hands are full)")
            bonuses = w["bonus"] if isinstance(w["bonus"], list) else [w["bonus"]]
            if not (args.full and not prof.get("full_attack")):
                bonuses = bonuses[:1]
            for b in bonuses:
                entries.append((key, b, w["damage"], w.get("crit", 20), w.get("mult", 2),
                                w.get("type", "melee"), w))
    # melee needs the target within reach (the weapon's, else the creature's); a charge needs its move
    dist = feet_between(a, t)
    for e in entries:
        if e[5] == "melee":
            reach = (e[6] or {}).get("reach") or a.get("reach", 5)
            if dist > reach and not getattr(args, "override", False):
                raise CombatError(f"{t['token']} is {dist} ft away, out of {a['token']}'s melee reach ({reach} ft): move first"
                                  + (" (a charge: `move … --as charge`, then the attack)" if args.charge else "")
                                  + ", or attack with a ranged weapon")
    if args.charge and not args.out_of_turn and not getattr(args, "override", False) and st.get("turn") == a["token"]:
        if a.get("move_mode") != "charge" or (a.get("mode_feet") or 0) < 10:
            raise CombatError(f"a charge moves at least 10 ft first, in a straight line: `move {a['token']} <square> --as charge "
                              f"--target {t['token']}`, then `attack … --charge`")
        if a.get("charge_at") and a["charge_at"] != t["token"]:
            raise CombatError(f"{a['token']} charged {a['charge_at']}: the charge's attack goes against it")
    shots: dict[str, int] = {}   # ammunition this command uses, checked before anything is rolled
    for e in entries:
        found = ammo_key(a, e[0])
        if found:
            shots[found[0]] = shots.get(found[0], 0) + 1
    used = _spent(a).setdefault("ammo", {})
    for key, count in shots.items():
        left = ammo_key(a, key)[1] - used.get(key, 0)   # type: ignore[index]
        if count > left and not getattr(args, "override", False):
            raise CombatError(f"{a['token']} has {'no' if left <= 0 else f'only {left}'} {key} ammunition left "
                              f"({'a thrown weapon has to be picked up first: a move action that provokes' if left <= 0 else 'fewer attacks'}); "
                              f"--override if it found more")
    out = []
    if args.aoo:
        a["aoo_used"] = a.get("aoo_used", 0) + 1
    if args.charge:
        R.add_condition(st, a, "charged", rounds=1)
    # A ranged attack provokes from everyone threatening the attacker (CRB Table 8-2), once per attack
    # action here (a threatener gets one AoO a round anyway). Not a ray's or touch spell's attack: the
    # casting already provoked.
    if any(e[5] == "ranged" for e in entries) and not args.aoo and not args.touch:
        verb = "throwing" if any(e[5] == "ranged" and (weapons(a).get(e[0] or "") or {}).get("type") != "ranged"
                                 for e in entries) else "shooting"
        lines, _taken = provoke_aoos(st, a, reason=f"{verb} at {t['token']}")
        out += lines
        if a["hp"] <= 0 or not can_act(a):
            return "\n".join(out + [f"{a['token']} goes down before the attack (no attack made)"])
    for i, e in enumerate(entries):
        if i and t["hp"] <= 0:
            out.append(f"(remaining attacks skipped: {who(t)} is down)")
            break
        found = ammo_key(a, e[0])
        if found:
            used[found[0]] = used.get(found[0], 0) + 1
        out.append(_attack_once(args, st, a, t, *e))
    for key in shots:
        total_n = ammo_key(a, key)[1]   # type: ignore[index]
        out.append(f"  {key}: {total_n - used[key]}/{total_n} left")
    return "\n".join(out)


def _attack_once(args: Args, st: State, a: Token, t: Token, name: str | None, bonus: int | None, dmg_expr: str | None, crit_at: int, mult: int, kind: str, weapon: dict[str, Any] | None) -> str:
    """Resolve one attack: situational modifiers, the roll (or the PC's total) against the adjusted AC,
    crit confirmation, concealment, damage and DR. Writes the combat log line; returns the DM report.
    """
    atk_delta, ac, notes, dmnotes, miss = attack_mods(st, a, t, kind, args.touch, args.charge, weapon)
    if not args.aoo:
        mark_target(st, a, t, "attack")
    if V.reveals_senses(st, a, t):
        dmnotes.append(f"{a['token']} has given its special senses away (its foes now plan with them)")
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
        if mroll <= miss and kind == "melee" and "blind-fight" in [f.lower() for f in ((a.get("profile") or {}).get("feats") or [])]:
            mroll, _, _ = _roll("1d100")
            dm.append(f"Blind-Fight reroll: d% {mroll}")
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
            dmg += dmg_mod * times
            parts.append(f"{dmg_mod * times:+d} conditions")
        dm.append(f"damage {dmg_expr} x{times} → {' + '.join(parts)} = {dmg}")
    elif args.damage is not None:
        dmg = args.damage
    elif bonus is None:   # the player rolls their own damage: the hit stands, the damage waits for them
        sneak, _ = sneak_attack(st, a, t, kind, miss)
        st["pending_damage"] = {"attacker": a["token"], "target": t["token"], "crit": crit, "mult": mult,
                                "nonlethal": bool(args.nonlethal), "line": line, "sneak": sneak}
        st["awaiting"] = f"{a['name']}: roll damage" + (f" (critical hit: ×{mult})" if crit else "")
        tip = f"; sneak attack applies (+{sneak})" if sneak else ""
        return "\n".join(dm + [f"{'CRITICAL ' if crit else ''}HIT. Ask the player for the damage"
                                + (f" (critical: ×{mult}, extra dice not multiplied)" if crit else "") + tip
                                + f", then `damage {a['token']} N` (question set). Don't roll it yourself."])
    else:
        raise CombatError("give --dmg for the NPC's damage")
    sneak, why_not = sneak_attack(st, a, t, kind, miss)
    if sneak and dmg_expr:   # precision damage: rolled once, never multiplied on a crit
        sd, sdetail, _ = _roll(sneak)
        dmg += sd
        dm.append(f"sneak attack {sneak} → {sdetail} = {sd}")
    elif sneak:
        dm.append(f"reminder: sneak attack applies (+{sneak}); check the player's damage includes it")
    elif why_not and (a.get("profile") or {}).get("sneak_attack"):
        dm.append(f"no sneak attack: {why_not}")
    nonlethal = bool(args.nonlethal)
    if dmg < 1:   # CRB pg. 179: "a hit still deals 1 point of nonlethal damage" (on the total, crits included)
        immune = any("nonlethal" in str(x).lower() for x in (t.get("profile") or {}).get("immune") or [])
        dmg, nonlethal = (0 if immune else 1), True
        dm.append("minimum damage: 1 nonlethal" + (" (it's immune to nonlethal damage: none)" if immune else ""))
    dealt, absorbed = apply_damage(t, dmg, nonlethal)
    kind_l = " nonlethal" if nonlethal else ""
    res = f" — {'critical hit' if crit else 'hit'}, {dmg}{kind_l} damage"
    if absorbed:
        res += f" ({absorbed} absorbed, {dealt} gets through)" if dealt else " (all of it absorbed)"
    res += f" [{who(t)}: {status(t)}]"
    event(st, line + res)
    return "\n".join(dm + [f"HIT. HP {t['hp']}/{t['max_hp']}. Log: {line}{res}"])


def cmd_damage(args: Args, st: State) -> str:
    """Apply the player's damage roll to the hit their last attack scored (`attack … --total` without
    --damage): DR, minimum damage and the log line, as if it had come with the attack. Or the damage
    or healing roll a PC's spell waits for (`cast` without --amount: spell_roll)."""
    pend = st.get("pending_damage")
    if not pend or pend["attacker"] != args.token:
        raise CombatError(f"{args.token} has no hit waiting for damage (`attack {args.token} TARGET --total N` first)")
    if pend.get("spell"):
        return spell_roll(args, st, pend)
    a, t = token(st, pend["attacker"]), token(st, pend["target"])
    dmg, nonlethal, dm = args.amount, pend["nonlethal"] or bool(args.nonlethal), []
    if pend.get("sneak"):
        dm.append(f"reminder: sneak attack applies (+{pend['sneak']}); check the player's damage includes it")
    if dmg < 1:
        immune = any("nonlethal" in str(x).lower() for x in (t.get("profile") or {}).get("immune") or [])
        dmg, nonlethal = (0 if immune else 1), True
        dm.append("minimum damage: 1 nonlethal" + (" (it's immune to nonlethal damage: none)" if immune else ""))
    dealt, absorbed = apply_damage(t, dmg, nonlethal)
    res = f" — {'critical hit' if pend['crit'] else 'hit'}, {dmg}{' nonlethal' if nonlethal else ''} damage"
    if absorbed:
        res += f" ({absorbed} absorbed, {dealt} gets through)" if dealt else " (all of it absorbed)"
    res += f" [{who(t)}: {status(t)}]"
    event(st, pend["line"] + res)
    st.pop("pending_damage", None)
    if str(st.get("awaiting", "")).startswith(f"{a['name']}: roll damage"):
        st.pop("awaiting", None)
    return "\n".join(dm + [f"HP {t['hp']}/{t['max_hp']}. Log: {pend['line']}{res}"])


def cmd_briefing(args: Args, st: State) -> str:
    """The briefing an NPC's combat step was given (tactical options, turn plans, sight), as the
    interface logged it in dm/combat/briefings.jsonl: to explain or audit a decision afterwards."""
    path = PROJECT / "campaigns" / args.campaign / "dm" / "combat" / "briefings.jsonl"
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()] if path.exists() else []
    rows = [r for r in rows if r.get("token") == args.token and r.get("started") == st.get("started")
            and (args.round is None or r.get("round") == args.round)]
    if not rows:
        raise CombatError(f"no logged briefing for {args.token}" + (f" in round {args.round}" if args.round else "")
                          + " in this fight (only steps the interface ran are logged)")
    r = rows[-1]
    return f"Briefing for {r['token']} ({r['name']}), round {r['round']}:\n{r['briefing']}" + (f"\n{r['sight']}" if r.get("sight") else "")


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

def fresh_state(mapfile: str | None, blank: str | None, light: str | None = None) -> State:
    """A new, unsaved encounter state from a map file or a blank 'WxH' grid. A map file may carry
    lighting: an "ambient: dim" line, and a "light:" line followed by zone rows (X dark, D dim,
    N normal, B bright, anything else = ambient), the same size as the map."""
    ambient, light_rows = "normal", None
    if blank:
        try:
            w, h = (int(v) for v in blank.lower().split("x"))
        except ValueError:
            raise CombatError(f"--blank must look like 10x8, not {blank!r}")
        grid = ["." * w for _ in range(h)]
    else:
        if not mapfile:
            raise CombatError("give a MAPFILE or --blank WxH")
        mp = Path(mapfile)
        if not mp.is_file():
            mp = PROJECT / mapfile
        if not mp.is_file():
            raise CombatError(f"no such map file: {mapfile}")
        lines = [l.rstrip("\n") for l in mp.read_text(encoding="utf-8").splitlines()]
        lines = [l for l in lines if l.strip() and not l.lstrip().startswith("//")]
        for l in [l for l in lines if l.strip().lower().startswith("ambient:")]:
            ambient = l.split(":", 1)[1].strip().lower()
            lines.remove(l)
        cut = next((i for i, l in enumerate(lines) if l.strip().lower() == "light:"), None)
        if cut is not None:
            light_rows = lines[cut + 1:]
            lines = lines[:cut]
        w = max(len(l) for l in lines)
        grid = [l.ljust(w) for l in lines]
        h = len(grid)
        bad = {ch for row in grid for ch in row} - set(TERRAIN)
        if bad:
            raise CombatError(f"unknown map characters: {''.join(sorted(bad))}")
    if not (1 <= w <= 26 and h >= 1):
        raise CombatError("map must be 1-26 columns wide")
    if light:
        ambient = light
    if ambient not in V.LEVELS:
        raise CombatError(f"ambient light must be one of: {', '.join(V.LEVELS)}")
    return {"w": w, "h": h, "grid": grid, "tokens": [], "round": 1, "turn": None,
            "started": datetime.now().isoformat(timespec="minutes"),
            "light": {"ambient": ambient, "sources": [],
                      "grid": [r.ljust(w)[:w] for r in light_rows][:h] if light_rows else None}}


def cmd_new(args: Args) -> str:
    """Start an encounter from a map file or a blank grid."""
    if state_path(args.campaign).exists() and not args.force:
        raise CombatError("an encounter is already active; 'end' it first or pass --force")
    st = fresh_state(args.mapfile, args.blank, args.light)
    save(args.campaign, st)
    return render(st, dm=True)


def resettle(st: State) -> list[str]:
    """After the map changed under the tokens: move every token that now stands off the map, in a wall
    or in deep water, or on another token, to the nearest free square it can stand on. Report lines."""
    out = []
    for c in st["tokens"]:
        if c.get("removed"):
            continue

        def fits(x: int, y: int) -> bool:
            with _placed(c, (x, y)):
                return all(cost(st, cx, cy) is not None and not occupied(st, c, cx, cy) for cx, cy in cells(c))
        if fits(c["x"], c["y"]):
            continue
        spots = sorted((max(abs(x - c["x"]), abs(y - c["y"])), y, x) for y in range(st["h"]) for x in range(st["w"]))
        spot = next(((x, y) for _d, y, x in spots if fits(x, y)), None)
        if spot is None:
            out.append(f"  {c['token']}: no free square left for it on this map (still at {fmt_pos(c['x'], c['y'])})")
            continue
        out.append(f"  {c['token']} moved from {fmt_pos(c['x'], c['y'])} to {fmt_pos(*spot)} (its square is blocked now)")
        c["x"], c["y"] = spot
    return out


def cmd_terrain(args: Args, st: State) -> str:
    """Paint terrain onto the current map: AREA=CHAR pairs, AREA a square (E5) or a rectangle (E5:H9).
    Tokens stay put unless their square became impassable (then they move to the nearest free one)."""
    grid = [list(r) for r in st["grid"]]
    done = []
    for item in args.paint:
        if "=" not in item:
            raise CombatError(f"paint as AREA=TERRAIN, e.g. E5:H9=. or C3=W (not {item!r})")
        area, ch = item.rsplit("=", 1)
        if ch not in TERRAIN:
            raise CombatError(f"unknown terrain {ch!r}: " + ", ".join(f"{k} {v[0]}" for k, v in TERRAIN.items()))
        a, _, b = area.partition(":")
        (x1, y1), (x2, y2) = parse_pos(a, st), parse_pos(b or a, st)
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for x in range(min(x1, x2), max(x1, x2) + 1):
                grid[y][x] = ch
        done.append(f"{area} → {ch} ({TERRAIN[ch][0]})")
    st["grid"] = ["".join(r) for r in grid]
    return "\n".join(["Terrain painted: " + "; ".join(done)] + resettle(st) + [render(st, dm=True)])


def cmd_map(args: Args) -> str:
    """Generate a battle map from a template (scripts/mapgen.py), save it to dm/combat/maps/, and with
    --start begin the encounter on it (its light sources included), or with --replace swap it in
    under the running fight (tokens, turn order, HP and conditions kept). Prints the map and where the
    party is, the ambush spots and the lights, for placing the tokens."""
    import mapgen
    opts = {"width": getattr(args, "width", None), "boat": getattr(args, "boat", False)}
    try:
        m = mapgen.generate(args.template, args.size, args.seed, args.density, args.time, opts)
    except mapgen.MapError as e:
        raise CombatError(str(e))
    if args.replace and args.start:
        raise CombatError("--start begins a new encounter, --replace swaps the map under the running one: pick one")
    if args.replace and not state_path(args.campaign).exists():
        raise CombatError("no encounter to swap the map under: use --start")
    name = re.sub(r"[^a-z0-9-]+", "-", (args.name or f"{args.template}-{m['seed']}").lower()).strip("-")
    path = PROJECT / "campaigns" / args.campaign / "dm" / "combat" / "maps" / f"{name}.txt"
    if path.exists() and not args.force:
        raise CombatError(f"{path.relative_to(PROJECT)} exists: give another --name, or --force")
    if args.start and state_path(args.campaign).exists() and not args.force:
        raise CombatError("an encounter is already active; 'end' it first or pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mapgen.to_file(m), encoding="utf-8")
    out = [f"Map {path.relative_to(PROJECT)} ({args.template}, seed {m['seed']}): " + " ".join(m["notes"])]
    if args.replace:   # the same fight on the new ground: tokens, turn, round, HP, conditions all stay
        st = load(args.campaign)
        new = fresh_state(str(path), None, None)
        st.update(w=new["w"], h=new["h"], grid=new["grid"])
        st["light"]["ambient"], st["light"]["grid"] = new["light"]["ambient"], new["light"]["grid"]
        for li in m["lights"]:
            add_light(st, li["kind"], mapgen.fmt(li["at"]), None)
        out += ["The fight goes on on the new map (tokens, turn order, HP and conditions kept)."] + resettle(st)
        save(args.campaign, st)
        out.append(render(st, dm=True))
    elif args.start:
        st = fresh_state(str(path), None, None)
        for li in m["lights"]:
            add_light(st, li["kind"], mapgen.fmt(li["at"]), None)
        save(args.campaign, st)
        undo_path(args.campaign).unlink(missing_ok=True)
        out.append(render(st, dm=True))
    else:
        out.append("\n".join(m["grid"]))
        out.append(f"ambient {m['ambient']}" + (f"; lights: " + ", ".join(f"{li['kind']} at {mapgen.fmt(li['at'])}" for li in m["lights"])
                                                  if m["lights"] else ""))
        out.append(f"Start it: `new {path.relative_to(PROJECT)}`" + (" (then add the lights)" if m["lights"] else ""))
    out.append("Party (where the PCs plausibly are): " + " ".join(mapgen.fmt(q) for q in m["party"]))
    out.append("Ambush spots (cover or concealment near their path): "
               + (", ".join(f"{mapgen.fmt(q)} ({why})" for q, why in m["ambush"]) or "none: use the terrain as it is"))
    return "\n".join(out)


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
    system = campaign_system(args.campaign)
    if args.side == "pc":
        # a PC always needs a complete profile on their sheet: enemies roll against it, and
        # conditions, vision and dying all read it
        schema = R.schema_path(system, "pc").relative_to(PROJECT)
        if not prof:
            raise CombatError(
                f"{args.name} has no combat profile. Their character sheet (players/characters/<slug>.md, "
                f"pass it with --ref) needs a ```combat-profile block that passes {schema}. Fill in what the "
                f"sheet already has, ASK THE PLAYER for anything missing, then add them")
        if prof.get("kind") != "pc":
            raise CombatError(f"{args.name} is a PC, so the profile needs \"kind\": \"pc\" (and must pass {schema})")
    elif prof.get("kind") == "pc":
        raise CombatError(f"{args.token} has a PC profile (\"kind\": \"pc\") but isn't on side pc")
    if prof:
        errs, warns = R.check_profile(prof, system)
        if errs and args.side == "pc":
            missing = [e.split("'")[1] for e in errs if "missing required field" in e]
            raise CombatError(
                f"{args.name}'s character sheet isn't complete for combat"
                + (f": missing {', '.join(missing)}" if missing else "") + ". Fill in what the sheet already "
                f"shows; ASK THE PLAYER for the rest (senses: {{}} means normal vision), update the sheet's "
                f"combat-profile block, then add them.\n  " + "\n  ".join(errs))
        if errs:
            raise CombatError(f"the combat profile for {args.token} has errors (fix the stat block's block, "
                              f"see library/<system>/combat-profile-guide.md):\n  " + "\n  ".join(errs))
        if prof.get("spellcasting") or prof.get("sla"):   # spell effects from the library, at its caster level
            prof = R.resolve_spell_effects(prof, system)[0]

    def pick(arg: Any, key: str, default: Any = None) -> Any:
        """The command-line value if given, else the profile's, else the default."""
        return arg if arg is not None else prof.get(key, default)

    if getattr(args, "tactics", None):   # this fight's personality and morale (encounter files), over the stat block's
        try:
            prof = dict(prof, tactics=json.loads(args.tactics))
        except json.JSONDecodeError as e:
            raise CombatError(f"--tactics must be JSON: {e}")
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
         "main_dm": bool(getattr(args, "main_dm", False)),   # played by the main DM, not the combat runner
         "init_tb": prof.get("init", 0)}   # ties: the higher initiative modifier goes first
    for cx, cy in cells(c):
        if cost(st, cx, cy) is None or occupied(st, c, cx, cy):
            raise CombatError(f"{fmt_pos(cx, cy)} is blocked or occupied")
    st["tokens"].append(c)
    c["wielding"] = default_wielding(c)   # what it holds when the fight starts
    held = inventory_wielding(args.campaign, c)
    if held is not None:   # a party member: what the inventory says it has equipped (none: empty hands)
        c["wielding"] = held
    if getattr(args, "wielding", None):
        c["wielding"] = [find_weapon(c, n.strip()) for n in args.wielding.split(",") if n.strip()]
    if not prof:
        notes.append("no combat profile: pass --roll/--dmg on attacks")
    return f"Added {args.token} ({args.name}) at {fmt_pos(x, y)}, init {init:g}" + (
        f" ({'; '.join(notes)})" if notes else "")


def cmd_endturn(args: Args, st: State) -> str:
    """Mark the PC's turn as over (the player ended it in words, or in the same message as their
    actions). In play the interface then plays the next step itself."""
    c = token(st, args.token)
    if c["side"] != "pc":
        raise CombatError(f"{c['token']} isn't a PC: other actors' turns end with their step")
    if st.get("turn") != c["token"]:
        raise CombatError(f"it isn't {c['token']}'s turn")
    st["end_turn"] = c["token"]
    return f"{c['name']}'s turn is over; the interface plays the next step"


ACTOR_ARG = {"wield": "token", "pickup": "token", "ability": "token", "maneuver": "attacker", "attack": "attacker", "move": "token", "cast": "token", "sla": "token", "provoke": "token", "area": "frm", "first-aid": "token", "flee": "token"}


UNDOABLE = ("wield", "pickup", "attack", "damage", "maneuver", "move", "save", "stabilize", "act", "provoke", "endturn", "ability",
            "first-aid", "flee")
READ_ONLY = ("show", "dist", "threat", "events", "sight", "actions", "options", "spells", "ask", "briefing")


def undo_path(campaign: str) -> Path:
    """Where the state before the last undoable command is kept (one level)."""
    return state_path(campaign).with_name("undo.json")


def remember_undo(args: Args, st: State, before: str) -> None:
    """Keep the state from before this command, with who acted, for `undo`."""
    actor_tok = getattr(args, ACTOR_ARG.get(args.command, "") or "_", None) or getattr(args, "token", None)
    actor = next((t for t in st["tokens"] if t["token"] == actor_tok), None)
    undo_path(args.campaign).write_text(json.dumps({
        "state": json.loads(before), "command": args.command, "actor": actor_tok,
        "pc": bool(actor and actor["side"] == "pc")}))


def cmd_undo(args: Args) -> str:
    """Take back the last command, if it was the player's own input (a PC's attack, save, maneuver,
    move, …): e.g. the player forgot a modifier and gives the corrected roll. NPC rolls stand
    ("never reroll silently"), and the correction is visible in the combat log."""
    path = undo_path(args.campaign)
    if not path.exists():
        raise CombatError("nothing to undo (only the last command can be taken back, once)")
    rec = json.loads(path.read_text())
    if not rec.get("pc"):
        raise CombatError(f"the last command ({rec.get('command')} by {rec.get('actor')}) wasn't the player's input: "
                          f"NPC rolls stand. Fix a mistake with the specific command (hp, cond, …) instead")
    st = rec["state"]
    who_ = next((t["name"] for t in st["tokens"] if t["token"] == rec.get("actor")), rec.get("actor"))
    event(st, f"(correction: {who_}'s {rec['command']} is re-entered)")
    save(args.campaign, st)
    path.unlink()
    return (f"Undone: {rec['command']} by {rec['actor']}. The fight is as it was before it (HP, log, actions); "
            f"enter the corrected command now.")


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
        raise CombatError(f"the fight hasn't started its first turn yet, so {actor} can't act. "
                          + ("You ARE in the player interface: it starts the turns right after your reply. Finish your "
                             "reply (the opening, who acts first) and stop." if play_mode() else
                             "Run `next` to start the first turn.") + " (Repositioning during setup: --out-of-turn.)")
    if actor != turn:
        raise CombatError(turn_message(st, actor, turn))


def play_mode() -> bool:
    """Whether the script runs under the player interface (web.py), which runs the turn order."""
    return os.environ.get("CLAUDE_DM_MODE") == "play"


def turn_message(st: State, actor: str, turn: str) -> str:
    """Why an actor can't act now, and what to do about it (for the DM)."""
    names = {t["token"]: t["name"] for t in st["tokens"]}
    who_ = f"{turn} ({names.get(turn, turn)})"
    msg = f"it's {who_}'s turn, not {actor}'s."
    a = next((t for t in st["tokens"] if t["token"] == actor), None)
    if a and a["side"] == "pc":
        msg += (f" The PC's turn hasn't come yet: tell the player that {names.get(turn, turn)} acts first "
                + ("and that their turn follows when they press Next (or say 'next'); keep their declared action "
                   "for then." if play_mode() else "and resolve the turns before theirs first."))
    else:
        msg += " Resolve only the current actor."
    return msg + " (AoOs take --aoo; readied or immediate actions and forced movement take --out-of-turn.)"


def is_dead(c: Token) -> bool:
    """Whether the creature is dead (HP at or below −Con, or marked dead)."""
    return bool(R.has(c, "dead") or (c.get("con") and c["hp"] <= -c["con"]))


def in_fight(c: Token) -> bool:
    """Whether the token still gets turns: not removed, and above 0 HP unless a PC or ally (dying ones
    roll to stabilize); the dead never do."""
    return not c.get("removed") and not is_dead(c) and (c["hp"] > 0 or c["side"] in FRIENDLY)


NO_ACTIONS = ("stunned", "dazed", "cowering")   # conditions that allow no actions at all (helpless is a flag)


def can_act(c: Token) -> bool:
    """Whether the creature can do anything on its turn: conscious (HP 0 or more) and not helpless,
    stunned, dazed or cowering. A turn without actions needs no decision: the engine skips it."""
    return (c["hp"] >= 0 and not c.get("removed") and not R.flag(c, "helpless")
            and not any(R.has(c, n) for n in NO_ACTIONS))


def surprised(st: State, c: Token) -> bool:
    """Whether the creature was unaware when the fight began, during the surprise round: it gets no
    turn in it (CRB pg. 178), and stays flat-footed until its first turn."""
    s = st.get("surprise")
    return isinstance(s, dict) and c["token"] in s.get("unaware", [])


def next_actor(st: State) -> tuple[Token, bool] | None:
    """The creature `next` will land on, and whether that starts a new round. Counts from the
    pointer's place in the full order, so it's right even if the current actor just dropped.
    In the surprise round, creatures that were unaware are skipped until the round wraps."""
    full = order(st)
    if not any(in_fight(c) for c in full):
        return None
    toks = [c["token"] for c in full]
    start = toks.index(st["turn"]) if st.get("turn") in toks else -1
    for k in range(1, len(full) + 1):
        j = start + k
        c = full[j % len(full)]
        wraps = start >= 0 and j >= len(full)
        if in_fight(c) and (wraps or not surprised(st, c)):
            return c, wraps
    return None


def cmd_next(args: Args, st: State) -> str:
    """Advance the turn pointer and handle the start of that creature's turn: expiring conditions,
    ongoing damage, AoO and movement resets, and dying checks (NPCs roll; a dying PC opens a question).
    """
    found = next_actor(st)
    if not found:
        raise CombatError("no combatants")
    prev = next((t for t in st["tokens"] if t["token"] == st.get("turn")), None)
    if prev is not None and not prev.get("hidden"):   # a hidden actor's movement is never shown
        path = prev.pop("turn_path", None)
        if path and len(path) > 1:
            st["last_move"] = {"token": prev["token"], "path": path}
        elif not prev.pop("skipped", None):
            st["last_move"] = None
        # else it couldn't act: the marks (and movement) of the one before it stay on the map
    lapsed = []
    for g in list(grapples(st)):   # a grapple must be maintained every round, on the grappler's turn
        if g["by"] == st.get("turn") and g.get("round") != st.get("round"):
            end_grapple(st, g)
            lapsed.append(f"  {g['by']} didn't maintain its grapple on {g['target']}: the grapple ends")
            event(st, f"{who(token(st, g['by']))} lets go of {who(token(st, g['target']))}")
    c, wraps = found
    surprise_over = False
    if wraps:
        st["round"] = st.get("round", 1) + 1
        surprise_over = bool(st.pop("surprise", None))
    st["turn"] = c["token"]
    st.pop("end_turn", None)
    if R.has(c, "fleeing"):   # declared last turn and nothing stopped it: it's off the battlefield
        R.remove_condition(c, "fleeing")
        c["removed"], c["fled"], c["skipped"] = True, True, True   # the last actor's marks stay on the map
        if not c.get("hidden"):
            event(st, f"{who(c)} flees the battlefield")
        return f"Round {st['round']}: {label(c)} ({c['name']}) flees the battlefield: removed (it's gone; no turn)"
    out = [f"Round {st['round']}: {label(c)} ({c['name']}) acts"] + lapsed
    if surprise_over:
        out.append("  the surprise round is over: full actions from now on")
    elif st.get("surprise"):
        out.append("  surprise round: only a standard or move action (plus free and swift actions); no full-round actions")
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
    if c.get("performing") and c.get("performed_round", 0) < st["round"] - 1:   # not kept up: it ended
        c.pop("performing", None)
        out.append(f"  {c['token']}'s performance has ended (not maintained)")
    for k in ("turn_actions", "move_mode", "mode_feet", "charge_at", "chain_feet", "chain_moves", "move_closed", "turn_path", "diag_parity"):
        c.pop(k, None)
    if c.get("immediate_used"):   # an immediate action since its last turn took this turn's swift
        turn_actions(c)["swift"] = f"immediate action before this turn ({c.pop('immediate_used')})"
    for src in list(V.light_state(st).get("sources", [])):
        e = src.get("expires")
        if e and (e["round"] < st["round"] or (e["round"] == st["round"] and e["token"] == c["token"])):
            V.light_state(st)["sources"].remove(src)
            out.append(f"  ended: {src['kind']} {src['id']}")
            event(st, f"The {src['kind']} goes out")
    out += light_sensitivity(st, c)
    for g in grapples(st):
        if g["by"] == c["token"]:
            out.append(f"  {c['token']} is grappling {g['target']}{' (pinned)' if g['pinned'] else ''}: maintain it this "
                       f"turn (`maneuver {c['token']} {g['target']} grapple`, +5) or `release`; not maintaining ends it")
        elif g["target"] == c["token"]:
            can = "only verbal and mental actions" if g["pinned"] else "actions that don't need two hands"
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
    if not can_act(c):   # one that can't act leaves the last actor's marks on the map
        c["skipped"] = True
    elif c["side"] != "pc":
        st["turn_marks"] = {"token": c["token"], "areas": [], "targets": []}
    return "\n".join(out)


def light_sensitivity(st: State, c: Token) -> list[str]:
    """Light sensitivity / light blindness at the start of the creature's turn: dazzled while in
    bright light (light blindness: blinded for 1 round on first exposure). Approximation: checked
    at the start of its turn only."""
    s = V.senses(c)
    if not (s.get("light_sensitivity") or s.get("light_blindness")):
        return []
    bright = max(V.level_at(st, q)[0] for q in cells(c)) >= V.BRIGHT
    out = []
    if bright:
        if s.get("light_blindness") and not c.get("light_exposed"):
            R.add_condition(st, c, "blinded", rounds=1)
            out.append(f"  {c['token']} is blinded by the bright light (1 round)")
        if not R.has(c, "dazzled by light"):
            R.add_condition(st, c, "dazzled by light")
            out.append(f"  {c['token']} is dazzled by the bright light")
        c["light_exposed"] = True
    else:
        if R.remove_condition(c, "dazzled by light"):
            out.append(f"  {c['token']} is out of the bright light: no longer dazzled")
        c.pop("light_exposed", None)
    return out


def reveal_observed(st: State) -> list[str]:
    """Stealth needs cover or concealment while observed: a hidden creature that a PC sees clearly
    (no concealment, no cover, not invisible) within take-10 Perception range is revealed.
    Only once the fight has started (so the DM can set up lighting first)."""
    if st.get("turn") is None:
        return []
    out = []
    pcs = [p for p in st["tokens"] if p["side"] == "pc" and not p.get("removed") and p["hp"] >= 0]
    for c in st["tokens"]:
        if not c.get("hidden") or c.get("removed") or R.has(c, "invisible"):
            continue
        for p in pcs:
            if V.hidden_from(st, c, p):
                continue
            perception = (p.get("profile") or {}).get("perception", 0)
            if feet_between(p, c) // 10 > 10 + perception:   # too far to notice on a take-10
                continue
            c["hidden"] = False
            event(st, f"{who(c)} comes into view")
            out.append(f"  {c['token']} is revealed: {p['token']} sees it clearly (no cover or concealment)")
            break
    return out


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
        if not why and (V.concealment(st, o, c)[0] >= 50 or R.has(c, "invisible")):
            why = f"can't see {c['token']}"
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
                 if v.get("type", "melee") == "melee" and at_hand(o, k)]
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

def ammo_key(c: Token, name: str | None) -> tuple[str, int] | None:
    """The tracked ammunition behind an attack: (key, how many it carries), or None if untracked.
    Creatures: `"ammo": N` on the attack (arrows, bolts, or the number of javelins for a thrown weapon).
    PCs: the profile's `"ammo": {"shortbow": 20}`, matched by the attack's name."""
    if not name:
        return None
    prof = c.get("profile") or {}
    key, w = R.find_attack(prof, name) if prof.get("attacks") else (None, None)
    if w and w.get("ammo") is not None:
        return str(key), int(w["ammo"])
    for k, n in (prof.get("ammo") or {}).items():
        if k.lower() == name.lower() or name.lower().startswith(k.lower()):
            return k, int(n)
    return None


def ammo_left(c: Token, name: str | None) -> int | None:
    """Shots or throws left with that attack, or None if it isn't tracked."""
    found = ammo_key(c, name)
    if not found:
        return None
    key, n = found
    return n - _spent(c).get("ammo", {}).get(key, 0)


def _spent(c: Token) -> dict[str, Any]:
    """The token's record of used spell slots, cast prepared spells and SLA uses (created if missing)."""
    return c.setdefault("spent", {"slots": {}, "prepared": {}, "sla": {}})


def spell_left(c: Token, sc: dict[str, Any], lvl: str | int, name: str) -> bool:
    """Whether the caster can still cast this spell of this spellcasting entry: cantrips always; a
    spontaneous caster while it has slots of that level; a prepared one while an uncast copy is left."""
    sp = _spent(c)
    if int(lvl) == 0:
        return True
    if sc.get("type") == "spontaneous":
        return sp["slots"].get(sc["class"].lower(), {}).get(str(lvl), 0) < (sc.get("slots") or {}).get(str(lvl), 0)
    names = [x.lower() for x in (sc.get("spells") or {}).get(str(lvl), [])]
    return sp["prepared"].get(sc["class"].lower(), []).count(name.lower()) < names.count(name.lower())


def sla_left(c: Token, s_: dict[str, Any]) -> bool:
    """Whether a spell-like ability has a use left today."""
    return s_.get("per_day") == "at will" or _spent(c)["sla"].get(s_["name"].lower(), 0) < (s_.get("per_day") or 0)


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


def immunity_of(args: Args) -> dict[str, Any] | None:
    """The immunity an effect leaves behind, as set by apply_effect_data: {name, from (caster token or
    None for anyone's), rounds, after ("affected" or "targeted")}, or None."""
    return getattr(args, "immunity", None)


def is_immune(st: State, t: Token, imm: dict[str, Any] | None) -> bool:
    """Whether `t` is still immune to that effect (from anyone, or from that caster)."""
    if not imm:
        return False
    return any((x.get("immune") or {}).get("to") == imm["name"] and (x["immune"].get("from") in (None, imm["from"]))
               for x in R.conditions(t))


def grant_immunity(st: State, t: Token, imm: dict[str, Any] | None, affected: bool) -> list[str]:
    """After the effect: `t` becomes immune to it for a while (daze: 1 minute, from anyone, once it was
    dazed; a witch's slumber hex: a day, from that witch, once targeted). A tracked condition."""
    if not imm or (imm["after"] == "affected" and not affected):
        return []
    who_from = "" if imm["from"] is None else f" from {token(st, imm['from'])['name']}"
    cond = R.add_condition(st, t, f"immune to {imm['name']}{who_from}", rounds=rounds_of(imm["rounds"]))
    cond["immune"] = {"to": imm["name"], "from": imm["from"]}
    return [f"  {t['token']} is now immune to {imm['name']}{who_from} for {imm['rounds']} rounds"]


def apply_effect_data(args: Args, data: dict[str, Any] | None, c: Token, st: State, name: str | None = None) -> None:
    """Fill in a spell's or ability's effect from the profile (area, save, DC, damage, healing,
    condition), for whatever the command didn't give itself. Checks the aim, the range, and that a
    single target isn't immune to it (a refusal, before the slot or use is spent).

    Raises:
        CombatError: if it needs an aim (--target, --toward, --at), the target is out of range, or immune.
    """
    if not data:
        return
    spec = data.get("immunity")
    if spec and name:
        args.immunity = {"name": name.lower(), "from": c["token"] if spec.get("from") == "caster" else None,
                         "rounds": spec.get("rounds", 10), "after": spec.get("after", "affected")}
        if data.get("target") == "one" and args.target and is_immune(st, token(st, args.target), args.immunity):
            raise CombatError(f"{args.target} is immune to {name} right now (it was {'affected' if args.immunity['after'] == 'affected' else 'targeted'} "
                              f"recently): pick another target or action (nothing was spent)")
    if data.get("target") == "area" and not args.area:
        args.area = data.get("area")
        if data.get("center") == "self" and not args.at:
            args.at = fmt_pos(c["x"], c["y"])
        shape = (args.area or "").split()[0]
        if shape in ("cone", "line") and not args.toward:
            raise CombatError(f"aim the {args.area}: --toward SQUARE (`options {c['token']} --area \"{args.area}\"` "
                              f"shows the best placements)")
        if shape == "burst" and not args.at:
            raise CombatError(f"place the {args.area}: --at SQUARE")
    if data.get("target") == "one" and not args.target:
        raise CombatError("this targets one creature: --target TOKEN")
    rng = data.get("range")
    if rng is not None and args.target:
        d = feet_between(c, token(st, args.target))
        reach = max(rng, 5) if rng == 0 else rng   # touch: adjacent
        if d > reach:
            raise CombatError(f"{args.target} is {d} ft away, out of range ({'touch' if rng == 0 else f'{rng} ft'})")
    for k in ("save", "dmg", "heal", "cond", "cond_rounds", "cond_mods"):
        if not getattr(args, k, None) and data.get(k):
            setattr(args, k, data[k])
    if data.get("half") and not args.half:
        args.half = True
    if data.get("sr") is not None:
        args.sr, args.sr_harmless = bool(data["sr"]), bool(data.get("sr_harmless"))
    if data.get("dc") and args.dc is None:
        args.dc = data["dc"]
    if data.get("touch") and data.get("target") == "one":
        if data.get("attack") is None and c["side"] == "pc":   # a PC's touch attack is the player's roll
            args.touch_attack = (None, "ranged" if (data.get("range") or 0) > 0 else "melee")
            return
        if data.get("attack") is None:
            raise CombatError("this effect needs a touch attack, but its effect data has no \"attack\" bonus: "
                              "add it to the profile, or resolve it with `attack --touch` and the effect by hand")
        args.touch_attack = (data["attack"], "ranged" if (data.get("range") or 0) > 0 else "melee")


def _rolled(args: Args, expr: str) -> tuple[int, str]:
    """A spell's damage or healing: the player's rolled amount for a PC's spell (`amount`), else the
    script rolls the dice. Returns (value, how)."""
    if getattr(args, "amount", None) is not None:
        return int(args.amount), f"the player's roll {args.amount}"
    value, detail, _ = _roll(expr)
    return value, detail


def touch_attack(args: Args, st: State, c: Token, t: Token, shown: str) -> tuple[bool, int, list[str]]:
    """Roll the touch attack of a spell or ability with effect data (against touch AC, with the usual
    modifiers and miss chance). Returns (hit, crit multiplier, output lines)."""
    bonus, kind = args.touch_attack
    delta, ac, notes, _dm, miss = attack_mods(st, c, t, kind, True)
    if bonus is None:   # a PC: the player's touch attack total
        total, detail, nat = args.total, f"the player's {args.total}", None
        attacker_side = [n for n in notes if n.startswith(("+", "-"))]
        if attacker_side:
            notes = [n for n in notes if n not in attacker_side] + [f"remind the player: {', '.join(attacker_side)}"]
    else:
        total, detail, _ = _roll(f"1d20{bonus + delta:+d}")
        nat = _natural(detail)
    hit = nat != 1 and (nat == 20 or total >= ac)
    mult = 1
    out = [f"  {kind} touch attack {detail} = {total} vs touch AC {ac}" + (f" ({', '.join(notes)})" if notes else "")
           + f": {'hit' if hit else 'miss'}"]
    if hit and nat == 20 and bonus is not None:
        conf, cdetail, _ = _roll(f"1d20{bonus + delta:+d}")
        mult = 2 if conf >= ac else 1
        out.append(f"  threat: confirm {cdetail} = {conf}: {'critical, damage dice ×2' if mult == 2 else 'no crit'}")
    if hit and miss:
        mroll, _, _ = _roll("1d100")
        out.append(f"  miss chance {miss}%: d% {mroll}")
        hit = mroll > miss
    if not t.get("hidden"):
        vs = f" vs AC {ac}" if t["side"] in FRIENDLY else ""
        event(st, f"{shown} → {who(t)}: {total}{vs}, {'hit' if hit else 'miss'}")
    return hit, mult, out


def find_ability(c: Token, name: str) -> tuple[str, dict[str, Any]]:
    """An ability from the profile by exact name, unique prefix or unique substring.

    Raises:
        CombatError: if there's no such ability (the message lists them).
    """
    abilities = (c.get("profile") or {}).get("abilities") or {}
    key = name.lower()
    for test in (lambda k: k == key, lambda k: k.startswith(key), lambda k: key in k):
        hits = [k for k in abilities if test(k.lower())]
        if len(hits) == 1:
            return hits[0], abilities[hits[0]]
    raise CombatError(f"{c['token']} has no ability {name!r} (abilities: {', '.join(abilities) or 'none in its profile'})")


def ability_action(c: Token, name: str, spec: dict[str, Any]) -> str:
    """The action an ability costs now: a performance kept up since its last turn costs its maintain action."""
    if spec.get("maintain") and c.get("performing") == name:
        return spec["maintain"]
    return spec.get("action", "standard")


def effect_notes(spec: dict[str, Any] | None) -> list[str]:
    """The effect's notes (what the script doesn't apply) as a reminder line for the DM."""
    return [f"  DM, by hand: {spec['notes']}"] if spec and spec.get("notes") else []


def is_buff(spec: dict[str, Any] | None) -> bool:
    """Whether effect data is a buff for allies (bless, inspire courage), not damage or healing."""
    return bool(spec and (spec.get("allies") or (spec.get("buff") and not spec.get("heal") and not spec.get("dmg")
                                                   and not spec.get("cond"))))


def buff_mods(spec: dict[str, Any]) -> dict[str, int]:
    """A buff's modifiers: its own `allies`, else those of the catalog condition it names."""
    return dict(spec.get("allies") or R.catalog_mods(spec.get("buff") or ""))


def buff_targets(st: State, c: Token, spec: dict[str, Any], target: str | None) -> list[Token]:
    """Who a buff reaches: one ally (--target), or every ally in range (a burst on the user: its radius).

    Raises:
        CombatError: a one-ally buff without --target, or a target out of range.
    """
    friendly = c["side"] in FRIENDLY
    rng = spec.get("range")
    area = str(spec.get("area") or "")
    if rng is None and area.startswith("burst") and spec.get("center", "self") == "self":
        rng = int(area.split()[1])
    if spec.get("target") == "self":
        return [c]
    if spec.get("target") == "one":
        if not target:
            raise CombatError("this buff targets one ally: --target TOKEN")
        t = token(st, target)
        if rng is not None and t is not c and feet_between(c, t) > max(rng, 5):
            raise CombatError(f"{t['token']} is {feet_between(c, t)} ft away, out of range ({'touch' if rng == 0 else f'{rng} ft'})")
        return [t]
    allies = [o for o in st["tokens"] if not o.get("removed") and in_fight(o) and o["hp"] >= 0
              and (o["side"] in FRIENDLY) == friendly]
    return [o for o in allies if o is c or rng is None or feet_between(c, o) <= rng]


def apply_buff(st: State, c: Token, spec: dict[str, Any], name: str, target: str | None) -> list[str]:
    """Put a buff's condition (with its modifiers) on everyone it reaches, for buff_rounds rounds."""
    targets = buff_targets(st, c, spec, target)
    label_ = spec.get("buff") or name
    mods = buff_mods(spec)
    base = R.catalog_mods(label_)   # a catalog condition brings its own modifiers: store only the difference
    extra = {k: v - base.get(k, 0) for k, v in mods.items() if v != base.get(k, 0)}
    rounds = rounds_of(spec.get("buff_rounds", 1))
    for o in targets:
        R.add_condition(st, o, label_, rounds=rounds, mods=extra or None)
        mark_target(st, c, o, "help")
    if targets and not c.get("hidden"):
        event(st, f"{label_}: {', '.join(who(o) for o in targets)} ({rounds} rounds)")
    return [f"  {label_} on {', '.join(o['token'] for o in targets) or 'nobody in range'} for {rounds} rounds"
            + (": " + ", ".join(f"{k} {v:+d}" for k, v in mods.items()) if mods else " (tracked by name)")] + effect_notes(spec)


def cmd_ability(args: Args, st: State) -> str:
    """Use a special ability from the profile: uses per day (rounds per day for a performance),
    the action (charged to the turn), and its effect: a buff on the allies it reaches, healing,
    or damage and conditions with saves, like a spell."""
    c = token(st, args.token)
    name, spec = find_ability(c, args.name)
    sp = _spent(c).setdefault("abilities", {})
    used = sp.get(name, 0)
    if spec.get("uses") is not None and used >= spec["uses"]:
        raise CombatError(f"{c['token']} has used {name!r} {used}/{spec['uses']} {'rounds' if spec.get('maintain') else 'times'} today")
    sp[name] = used + 1
    out = [f"{c['token']} uses {name}" + (f" ({used + 1}/{spec['uses']} {'rounds' if spec.get('maintain') else 'uses'} today)"
                                          if spec.get("uses") is not None else "")]
    if spec.get("maintain"):
        c["performing"], c["performed_round"] = name, st.get("round", 1)
    friendly = c["side"] in FRIENDLY
    if is_buff(spec):
        out += apply_buff(st, c, spec, name, args.target)
        if not c.get("hidden"):
            event(st, f"{who(c)} uses {name}")
        return "\n".join(out)
    if spec.get("heal") and spec.get("target") == "area":   # e.g. channel energy: one roll, everyone it covers
        at = parse_pos(args.at, st) if args.at else (c["x"], c["y"])
        shape, ft = spec.get("area", "burst 30").split()
        squares = R.area_cells(st, "burst", int(ft), origin=at) if shape == "burst" else []
        mark_area(st, c, squares)
        hit = [o for o in R.tokens_in(st, squares) if not o.get("removed")]
        if spec.get("who") == "allies":
            hit = [o for o in hit if (o["side"] in FRIENDLY) == friendly]
        amount, detail, _ = _roll(spec["heal"])
        out.append(f"  heals {spec['heal']} → {detail} = {amount}")
        for o in hit:
            before = o["hp"]
            o["hp"] = min(o.get("max_hp", o["hp"] + amount), o["hp"] + amount)
            healed(st, o, before)
            out.append(f"  {o['token']}: {before} → {o['hp']}")
            if not o.get("hidden"):
                event(st, f"{name}: {who(o)} is healed, +{o['hp'] - before} HP [{who(o)}: {status(o)}]")
        return "\n".join(out)
    # damage, conditions or single-target healing: resolved like a spell
    ns = argparse.Namespace(command="sla", area=None, at=args.at, toward=args.toward, target=args.target, save=None,
                            dmg=None, half=False, heal=None, cond=None, cond_rounds=None, dc=None,
                            light_at=None, light_on=None, rounds=None)
    apply_effect_data(ns, spec, c, st, name)
    ns.sr = False   # supernatural and extraordinary abilities ignore spell resistance
    out += _spell_effect(ns, st, c, name, ns.dc)
    if not c.get("hidden"):
        event(st, f"{who(c)} uses {name}")
    return "\n".join(out)


def cast_pc(args: Args, st: State, c: Token) -> str:
    """A PC casts: the effect from the library at the PC's caster level and the player's DC; slots are
    the player's business (their sheet). Provoking stays a question for the table: the concentration
    roll is the player's, so the effect only lands once the casting held."""
    prof = c.get("profile") or {}
    cl = args.cl or prof.get("caster_level") or 1
    system = campaign_system(args.campaign)
    try:
        lib, where = R.library_spell_effect(args.spell, system)
        data = R.resolve_effect(lib, int(cl), system) if lib and not lib.get("utility") else None
    except ValueError as e:
        raise CombatError(str(e))
    threatened = [o["token"] for o in st["tokens"] if threatens(o, c)]
    if threatened and not args.no_provoke and not args.defensive:
        raise CombatError(f"{c['token']} is threatened by {', '.join(threatened)}: casting provokes. Resolve that first "
                          f"(`provoke {c['token']} --reason \"casting {args.spell}\"`, then the player's concentration "
                          f"check if hit), then cast with --no-provoke; or --defensive once the player's concentration "
                          f"check (DC 15 + 2 x spell level) succeeded")
    if data and is_buff(data):
        effect = apply_buff(st, c, data, args.spell, args.target)
    else:
        apply_effect_data(args, data, c, st, args.spell)
        if args.save and args.dc is None:
            raise CombatError(f"{args.spell} allows a save: give the DC from {c['name']}'s sheet (--dc N)")
        if getattr(args, "touch_attack", None) and args.touch_attack[0] is None and args.total is None:
            raise CombatError(f"{args.spell} needs a touch attack: ask the player for it (d20 + their ranged/melee touch "
                              f"bonus) and pass total N (nothing was applied)")
        rolls = [x for x in (args.dmg, getattr(args, "heal", None)) if x]
        if rolls and getattr(args, "amount", None) is None:   # the player's roll: hit or miss first, then it waits
            args.defer_roll = (rolls[0], "damage" if args.dmg else "healing")
        args.sr_cl = cl
        if getattr(args, "sr", None) is None:
            args.sr = True
        effect = _spell_effect(args, st, c, args.spell, args.dc) + effect_notes(data)
        if not data and not (args.dmg or args.save or args.heal or getattr(args, "cond", None)):
            effect.append(f"  (no effect data in {where}: give the effect in the command, or add a spell-effect block)")
    if not c.get("hidden"):
        event(st, f"{who(c)} casts a spell")
    out = [f"{c['token']} casts {args.spell} (CL {cl}" + (f", DC {args.dc}" if args.dc else "") + ")"] + effect
    if not st.get("turn") or st.get("turn") == c["token"]:
        out.append(action_status(st, c))
    return "\n".join(out)


def cmd_cast(args: Args, st: State) -> str:
    """An NPC casts a spell: check and spend the slot or prepared copy, provoke or cast defensively, then the effect.
    A PC's spell goes to cast_pc."""
    c = token(st, args.token)
    if c["side"] == "pc":
        return cast_pc(args, st, c)
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
    effects = {k.lower(): v for k, v in (sc.get("effects") or {}).items()}
    data = effects.get(spell)
    if data and is_buff(data):
        buff_targets(st, c, data, args.target)   # before the slot is spent: a missing target fails cleanly
    else:
        apply_effect_data(args, data, c, st, args.spell)   # before the slot is spent: a missing aim fails cleanly
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
    args.sr_cl = sc.get("cl")
    if getattr(args, "sr", None) is None:
        args.sr = True   # a spell without a Spell Resistance line in its data: most spells allow it
    if not c.get("hidden"):
        event(st, f"{who(c)} casts a spell" + ("" if ok else ", but loses it"))
    head = f"{c['token']} casts {args.spell} ({sc['class']} {lvl}, CL {sc['cl']}, save DC {dc}): {'OK' if ok else 'LOST'}"
    effect = ([] if not ok else apply_buff(st, c, data, args.spell, args.target) if data and is_buff(data)
              else _spell_effect(args, st, c, args.spell, dc) + effect_notes(data))
    return "\n".join([head] + ([f"  {left_note}"] if left_note else []) + lines + effect)


# Spell resistance (library/pf1e/rules/spell-resistance.md, CRB pg. 217): spells and spell-like abilities
# whose effect says "sr": true (the library's Spell Resistance line; an SLA without one: yes) must beat
# each target's SR with a caster level check, 1d20 + CL (+2 Spell Penetration, +2 more Greater), ties
# succeed. A target that resists is unaffected; the others are affected as usual. Supernatural and
# extraordinary abilities ignore SR. Rays and touch spells: the touch attack first, then the check.
# A harmless spell on an ally: the ally lowers its SR (table simplification: no action spent).
# A PC's caster level check is the player's roll (--sr-check), like their saves.

def target_sr(t: Token) -> int:
    """The creature's spell resistance (0: none)."""
    return int((t.get("profile") or {}).get("sr") or t.get("sr") or 0)


def resists(st: State, c: Token, t: Token, args: Args, shown: str) -> tuple[bool, list[str]]:
    """Spell resistance against one target: (whether it resists, report lines)."""
    sr = target_sr(t)
    if not sr or not getattr(args, "sr", False):
        return False, []
    if getattr(args, "sr_harmless", False) and (t["side"] in FRIENDLY) == (c["side"] in FRIENDLY):
        return False, [f"  {label(t)}: spell resistance lowered for a harmless effect from an ally"]
    if c["side"] == "pc":
        total = getattr(args, "sr_check", None)
        if total is None:
            raise CombatError(f"{t['token']} has spell resistance: ask the player for a caster level check "
                              f"(d20 + caster level, + Spell Penetration), then repeat with sr_check N (nothing was applied)")
        how = f"reported {total}"
    else:
        feats = _feats(c)
        pen = 2 * ("spell penetration" in feats) + 2 * ("greater spell penetration" in feats)
        cl = int(getattr(args, "sr_cl", None) or 1)
        total, detail, _ = _roll(f"1d20+{cl + pen}")
        how = f"1d20+{cl + pen} → {detail} = {total}"
    ok = total >= sr
    lines = [f"  {label(t)} spell resistance {sr}: caster level check {how} → {'overcome' if ok else 'RESISTED: unaffected'}"]
    if not ok and not t.get("hidden"):
        event(st, f"{shown}: {who(t)} is unaffected")
    return not ok, lines


def defer_roll(st: State, args: Args, c: Token, t: Token | None, name: str, mult: int, resolved: bool) -> list[str]:
    """A PC's spell whose damage or healing the player rolls: once its touch attack hit (and spell
    resistance is overcome), or before an area is resolved, the rest waits for their roll
    (`damage TOKEN N`), with the question set so the turn can't end first. `resolved`: the touch
    attack and spell resistance are done, so the replay skips them."""
    expr, what = args.defer_roll
    keep: dict[str, Any] = {}
    for k, v in vars(args).items():
        if k in ("defer_roll", "touch_attack"):
            continue
        try:
            json.dumps(v)
        except TypeError:
            continue
        keep[k] = v
    st["pending_damage"] = {"attacker": c["token"], "target": t["token"] if t else None, "spell": keep,
                            "name": name, "resolved": resolved, "mult": mult}
    crit = f", critical hit: roll the dice ×{mult}" if mult > 1 else ""
    st["awaiting"] = f"{c['name']}: roll {what} for the spell ({expr}{crit})"
    head = ("CRITICAL HIT. " if mult > 1 else "HIT. ") if getattr(args, "touch_attack", None) else ""
    return [f"{head}Ask the player for the {what} ({expr}{crit}), then `damage {c['token']} N` (question set). "
            f"Nothing else was applied yet. Don't roll it yourself."]


def spell_roll(args: Args, st: State, pend: dict[str, Any]) -> str:
    """The player's damage or healing roll for a spell that waited for it (defer_roll): the rest of
    the spell's effect, as if the roll had come with the cast."""
    c = token(st, pend["attacker"])
    ns = argparse.Namespace(**pend["spell"])
    ns.amount, ns.touch_attack, ns.defer_roll = args.amount, None, None
    if pend.get("resolved"):
        ns.sr = False   # spell resistance was already overcome
    st.pop("pending_damage", None)
    if str(st.get("awaiting", "")).startswith(f"{c['name']}: roll"):
        st.pop("awaiting", None)
    return "\n".join(_spell_effect(ns, st, c, pend["name"], ns.dc))


def _spell_effect(args: Args, st: State, c: Token, name: str, dc: int | None) -> list[str]:
    """The effect part of cast/sla: an area template or a single target, with save and damage.
    The player's log and questions say "the spell" / "the ability": naming it is a Spellcraft matter."""
    out = []
    shown = "the ability" if args.command == "sla" else "the spell"
    if name.lower() in V.SOURCES and (args.light_at or args.light_on):
        out.append("  " + add_light(st, name.lower(), args.light_at, args.light_on, rounds=args.rounds, by=c["token"]))
    if args.area:
        m = re.match(r"^\s*(burst|cone|line)\s+(\d+)\s*$", args.area)
        if not m:
            raise CombatError('--area must look like "cone 15", "burst 20" or "line 60"')
        if getattr(args, "defer_roll", None):
            return out + defer_roll(st, args, c, None, name, 1, resolved=False)
        ns = argparse.Namespace(shape=m.group(1), feet=int(m.group(2)), at=args.at, frm=c["token"],
                                toward=args.toward, save=args.save, dc=dc, dmg=args.dmg, half=args.half,
                                name=name, no_slot=True, log_name=shown, cond=getattr(args, "cond", None), cond_rounds=getattr(args, "cond_rounds", None),
                                cond_mods=getattr(args, "cond_mods", None), immunity=immunity_of(args),
                                sr=getattr(args, "sr", False), sr_cl=getattr(args, "sr_cl", None),
                                sr_harmless=getattr(args, "sr_harmless", False), sr_check=getattr(args, "sr_check", None),
                                amount=getattr(args, "amount", None))
        out.append(cmd_area(ns, st))
    elif args.target:
        t = token(st, args.target)
        V.reveals_senses(st, c, t)
        mark_target(st, c, t, "help" if getattr(args, "heal", None) or (t["side"] in FRIENDLY) == (c["side"] in FRIENDLY)
                    else "spell")
        mult = 1
        if getattr(args, "touch_attack", None):   # rays and touch spells: roll to hit first
            hit, mult, lines = touch_attack(args, st, c, t, shown)
            out += lines
            if not hit:
                return out
        blocked, lines = resists(st, c, t, args, shown)
        out += lines
        if blocked:
            return out
        if getattr(args, "defer_roll", None):
            return out + defer_roll(st, args, c, t, name, mult, resolved=True)
        if getattr(args, "heal", None):   # cure spells and the like: roll it and heal the target
            amount, detail = _rolled(args, args.heal)
            before = t["hp"]
            t["hp"] = min(t.get("max_hp", t["hp"] + amount), t["hp"] + amount)
            healed(st, t, before)
            if t.get("nonlethal"):
                t["nonlethal"] = max(0, t["nonlethal"] - amount)
            out.append(f"{name}: heals {args.heal} → {detail} = {amount}: {t['token']} HP {before} → {t['hp']}/{t.get('max_hp')}")
            if not t.get("hidden"):
                event(st, f"{shown}: {who(t)} is healed, +{t['hp'] - before} HP [{who(t)}: {status(t)}]")
        elif not (args.dmg or args.save or args.light_at or args.light_on or getattr(args, "cond", None)):
            out.append(f"  NOTE: no effect was applied to {t['token']}: the slot is spent, nothing else happened. "
                       f"Give the effect in the same command (--heal 1d8+3, --dmg, --save), or add a condition "
                       f"with `cond` after it")
        dmg = 0
        if args.dmg:
            dmg, detail = _rolled(args, args.dmg)
            if mult == 2 and getattr(args, "amount", None) is None:   # a critical touch spell: the dice twice
                extra, detail2, _ = _roll(args.dmg)
                dmg, detail = dmg + extra, f"{detail} + {detail2}"
            out.append(f"{name}: damage {args.dmg} → {detail} = {dmg}")
        if args.save:
            if dc is None:
                raise CombatError("--save needs a DC: pass --dc")
            if t["side"] == "pc":
                st.setdefault("pending_saves", {})[t["token"]] = {
                    "kind": args.save, "dc": dc, "dmg": dmg, "half": args.half, "name": shown,
                    "cond": getattr(args, "cond", None), "cond_rounds": getattr(args, "cond_rounds", None),
                    "cond_mods": getattr(args, "cond_mods", None), "immunity": immunity_of(args)}
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
                if not ok:
                    out += spell_condition(st, t, getattr(args, "cond", None), getattr(args, "cond_rounds", None), shown, getattr(args, "cond_mods", None))
                out += grant_immunity(st, t, immunity_of(args), affected=not ok)
            if t["side"] == "pc":
                out += grant_immunity(st, t, immunity_of(args), affected=False)   # "targeted": now; "affected": after the save
        elif dmg:
            apply_damage(t, dmg)
            if not t.get("hidden"):
                event(st, f"{shown}: {who(t)} takes {dmg} damage [{who(t)}: {status(t)}]")
        if not args.save:   # no save allowed: the condition just applies
            out += spell_condition(st, t, getattr(args, "cond", None), getattr(args, "cond_rounds", None), shown, getattr(args, "cond_mods", None))
            out += grant_immunity(st, t, immunity_of(args), affected=True)
    return out


def cmd_sla(args: Args, st: State) -> str:
    """An NPC uses a spell-like ability: check and spend a use, provoke or use it defensively, then the effect."""
    c = token(st, args.token)
    name = args.name.lower()
    entry = next((s for s in (c.get("profile") or {}).get("sla") or [] if s["name"].lower() == name), None)
    if not entry:
        raise CombatError(f"{c['token']} has no spell-like ability {args.name!r}")
    if is_buff(entry.get("effect")):
        buff_targets(st, c, entry["effect"], args.target)
    else:
        apply_effect_data(args, entry.get("effect"), c, st, args.name)
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
    args.sr_cl = entry.get("cl")
    if getattr(args, "sr", None) is None:
        args.sr = True   # spell-like abilities are subject to SR unless the effect says otherwise
    if not c.get("hidden"):
        event(st, f"{who(c)} uses a spell-like ability" + ("" if ok else ", but loses it"))
    dc_val = args.dc or entry.get("dc")
    dc = f", DC {dc_val}" if dc_val else ""
    head = f"{c['token']} uses {args.name} (SLA, CL {entry.get('cl', '?')}{dc}): {'OK' if ok else 'LOST'}"
    if ok and (args.area or args.target) and args.save and not dc_val:
        raise CombatError(f"{args.name} has no DC in the profile: pass --dc")
    effect = ([] if not ok else apply_buff(st, c, entry["effect"], args.name, args.target) if is_buff(entry.get("effect"))
              else _spell_effect(args, st, c, args.name, dc_val) + effect_notes(entry.get("effect")))
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
    feet, route, end_parity = path_route_parity(st, c, dest)
    frm = fmt_pos(c["x"], c["y"])
    out = []
    speed = c.get("speed") or 30
    charged = not (args.out_of_turn or args.override)   # forced movement and overrides cost no actions
    mode = args.as_
    if args.step:
        if feet != 5:
            raise CombatError(f"a 5-foot step moves exactly one square (this move costs {feet} ft)")
        if c.get("moved") or c.get("stepped"):
            raise CombatError(f"{c['token']} already moved this turn; no 5-foot step allowed")
        if charged and c.get("move_mode") in ("run", "withdraw", "charge"):
            raise CombatError(f"no 5-foot step in a round with a {c['move_mode']}")
        c["stepped"] = True
    elif charged:
        if c.get("stepped"):
            raise CombatError(f"{c['token']} took a 5-foot step this turn, so it can't move any further distance")
        if mode == "charge":
            if c.get("move_mode") == "charge":
                raise CombatError(f"{c['token']} is already charging: a charge is one straight move, then the attack")
            if not args.target:
                raise CombatError(f"a charge names its target: `move {c['token']} {args.pos} --as charge --target TOKEN`")
            t = token(st, args.target)
            why = charge_problem(st, c, t, dest)
            if why:
                raise CombatError(f"{c['token']} can't charge {t['token']} to {fmt_pos(*dest)}: {why} (nothing moved). "
                                  f"`options {c['token']}` lists its charge lanes")
            if c["size"] == 1:
                route = straight_route(c, dest)
            c["charge_at"] = t["token"]
        if mode:
            limit = {"charge": 2, "withdraw": 2, "run": 4}[mode] * speed
            if c.get("move_mode") not in (None, mode):
                raise CombatError(f"{c['token']} is already moving as part of a {c['move_mode']}")
            if c.get("move_mode") != mode:
                if c.get("moved"):
                    raise CombatError(f"a {mode} is a full-round action: {c['token']} already moved this turn")
                spend(st, c, "full", mode)
                c["move_mode"], c["mode_feet"] = mode, 0
            if c["mode_feet"] + feet > limit:
                raise CombatError(f"a {mode} moves at most {limit} ft ({c['mode_feet'] + feet} ft)")
            c["mode_feet"] += feet
        else:
            if c.get("move_mode"):
                raise CombatError(f"{c['token']} is moving as part of a {c['move_mode']}: add --as {c['move_mode']}")
            # one stretch of movement: it can't be split around a standard action, so moving again
            # after one starts a new stretch, with its own move action(s)
            if c.pop("move_closed", None):
                c["chain_feet"], c["chain_moves"] = 0, 0
            chain = c.get("chain_feet", 0) + feet
            need = -(-chain // speed)
            if need > 2:
                raise CombatError(f"{chain} ft in one go is more than a double move ({2 * speed} ft); a run is `--as run`")
            extra = need - c.get("chain_moves", 0)
            ta = turn_actions(c)
            if extra > 0 and ta.get("combinable") and not ta.get("combined"):
                ta["combined"] = True   # it drew or sheathed with that move action: the movement rides on it
                ta["move"][ta["move"].index(next(m for m in ta["move"] if m.startswith(("draw", "sheathe"))))] += " + movement"
                extra -= 1
            if extra > 0:
                spend_moves(st, c, extra, "movement")
            c["chain_feet"], c["chain_moves"] = chain, max(need, c.get("chain_moves", 0))
    # attacks of opportunity for every threatened square it leaves along the way (not on a 5-foot
    # step; a withdraw's first square isn't threatened by foes it can see). "Moving out of more than
    # one square threatened by the same opponent in the same round doesn't count as more than one
    # opportunity for that opponent." If an AoO drops it, it falls where it was.
    if not args.step:
        rnd = st.get("round", 1)
        seen = c.get("aoo_opportunities") or {}
        given = set(seen.get("by", [])) if seen.get("round") == rnd else set()
        withdraw_start = mode == "withdraw" and c.get("mode_feet", 0) == feet
        for i, sq in enumerate(route[:-1]):
            if i == 0 and withdraw_start:
                continue
            c["x"], c["y"] = sq
            fresh = [o for o in st["tokens"] if o["token"] not in given and threatens(o, c)]
            if not fresh:
                continue
            given |= {o["token"] for o in fresh}
            lines, _dmg = provoke_aoos(st, c, args.no_aoo, f"moving out of a threatened square ({fmt_pos(*sq)})", only=fresh)
            out += lines
            if c["hp"] <= 0:
                c["aoo_opportunities"] = {"round": rnd, "by": sorted(given)}
                if st.get("turn") == c["token"] and i:
                    c.setdefault("turn_path", []).extend(list(q) for q in route[1:i + 1])
                out.insert(0, f"{c['token']} is dropped by an attack of opportunity at {fmt_pos(*sq)}"
                              + (f" ({5 * i} ft into its move)" if i else " and doesn't move"))
                return "\n".join(out)
        c["aoo_opportunities"] = {"round": rnd, "by": sorted(given)}
    c["x"], c["y"] = dest
    if st.get("turn") == c["token"] and not args.out_of_turn:   # the diagonal count goes on next time it moves
        c["diag_parity"] = end_parity
    if st.get("turn") == c["token"]:   # its own movement this turn, for the map's movement line
        marks_for(st, c)
        tp = c.setdefault("turn_path", [])
        tp += [list(sq) for sq in (route if not tp or tuple(tp[-1]) != route[0] else route[1:])]
    if not args.step:
        c["moved"] = c.get("moved", 0) + feet
    warn = ""
    if mode == "run" and "run" not in _feats(c) and not R.has(c, "running"):
        R.add_condition(st, c, "running", rounds=1)
        warn = "  (running: loses its Dex bonus to AC until its next turn)"
    elif mode:
        warn = f"  (part of a {mode}: {c['mode_feet']} ft so far)"
    elif c.get("moved", 0) > speed:
        warn = f"  (double move: {c['moved']} ft this turn)"
    kind = "5-foot step" if args.step else "moves"
    out.insert(0, f"{c['token']} {kind} {frm} → {fmt_pos(*dest)}: {feet} ft{warn}")
    return "\n".join(out)


# ---------- action economy ----------
# Rules: library/pf1e/rules/actions-in-combat.md (Core Rulebook pg. 178-189). Per turn: a standard
# and a move action (or two moves), or one full-round action; plus one swift action (an immediate
# action used outside the creature's turn takes the swift of its next turn), free actions, and one
# 5-foot step if it doesn't otherwise move. Restricted (surprise round, staggered): one standard or
# move. Nauseated: one move. Actions taken with --out-of-turn (readied, forced) or --override
# (a feat or ability that changes the economy, e.g. Spring Attack) aren't charged.

ACTION_KINDS = ("standard", "move", "full", "swift", "immediate", "free")


def turn_actions(c: Token) -> dict[str, Any]:
    """The token's action record for its current turn (reset by `next`)."""
    return c.setdefault("turn_actions", {"standard": None, "move": [], "full": None, "swift": None})


def restriction(st: State, c: Token) -> str | None:
    """Why the token is limited to a single action this turn, if it is."""
    if R.has(c, "nauseated"):
        return "nauseated (a single move action)"
    if st.get("surprise"):
        return "surprise round (a standard or move action)"
    if R.has(c, "staggered") or (c["hp"] == 0 and c["side"] in FRIENDLY):
        return "staggered or disabled (a standard or move action)"
    return None


def can_take(st: State, c: Token, kind: str) -> str | None:
    """None if the token can take this kind of action now, else why not."""
    a = turn_actions(c)
    used_main = a["standard"] or a["move"] or a["full"]
    limit = restriction(st, c)
    if kind == "free":
        return None
    if kind in ("swift", "immediate"):
        if a["swift"]:
            return f"its swift/immediate action is already used ({a['swift']})"
        if kind == "immediate" and not c.get("acted"):
            return "it's flat-footed (hasn't acted yet): no immediate actions"
        return None
    if a["full"]:
        return f"it took a full-round action ({a['full']})"
    if limit and used_main:
        return f"it can take only one action this turn: {limit}"
    if kind == "full":
        if limit:
            return f"no full-round actions: {limit}"
        if a["standard"] or a["move"]:
            return f"it already used {', '.join(filter(None, [a['standard'] and 'its standard action'] + (['a move action'] if a['move'] else [])))}"
        return None
    if limit and limit.startswith("nauseated") and kind == "standard":
        return f"no standard actions: {limit}"
    if kind == "standard":
        if a["standard"]:
            return f"its standard action is already used ({a['standard']})"
        return None
    if kind == "move":
        if not a["move"]:
            return None
        if a["standard"]:
            return "its move action and its standard action are both used"
        return None   # a second move action uses the standard action
    raise CombatError(f"unknown action kind {kind}")


def take_action(st: State, c: Token, kind: str, what: str) -> None:
    """Record an action (call can_take first)."""
    a = turn_actions(c)
    if kind == "move":
        if a["move"]:
            a["standard"] = f"a second move action ({what})"
        a["move"].append(what)
    elif kind in ("swift", "immediate"):
        a["swift"] = what
    elif kind != "free":
        a[kind] = what
    if kind in ("standard", "full"):
        c["move_closed"] = True   # movement after this needs a new move action (no splitting)


def spend(st: State, c: Token, kind: str, what: str) -> None:
    """Check and record an action in one go.

    Raises:
        CombatError: if the token can't take it this turn.
    """
    why = can_take(st, c, kind)
    if why:
        raise CombatError(f"{c['token']} can't take a {kind} action ({what}) now: {why}. "
                          f"If a feat or ability allows it, add --override")
    take_action(st, c, kind, what)


def actions_left(st: State, c: Token) -> str:
    """e.g. 'move, swift, 5-foot step', or 'nothing but free actions'."""
    a = turn_actions(c)
    left = [k for k in ("standard", "move", "swift") if not can_take(st, c, k)]
    if a["move"] and "standard" in left:   # one move used: the other slot is the standard (or a 2nd move)
        left = ["standard (or a second move)"] + [k for k in left if k not in ("standard", "move")]
    if not can_take(st, c, "full"):
        left.append("or a full-round action instead")
    if not c.get("moved") and not c.get("stepped") and not R.condition_names(c, ("no_move",)) \
            and c.get("move_mode") not in ("run", "withdraw", "charge"):
        left.append("5-foot step")
    return ", ".join(left) or "nothing but free actions"


def action_status(st: State, c: Token) -> str:
    """The line every action command adds for the creature whose turn it is."""
    return f"  actions left for {c['token']}: {actions_left(st, c)}"


def charge_action(st: State, args: Args, c: Token) -> str | None:
    """What an action command costs the actor: an action kind, or None (nothing to charge).
    Movement is charged in cmd_move, by distance."""
    cmd = args.command
    if getattr(args, "out_of_turn", False) or getattr(args, "override", False) or getattr(args, "aoo", False):
        return None
    if cmd == "flee":
        return "full"
    if cmd in ("cast", "sla"):
        t = getattr(args, "time", None) or "standard"
        return "full" if t in ("full", "round") else t
    if cmd == "area":
        return "standard" if args.frm else None
    if cmd == "ability":
        try:
            name, spec = find_ability(c, args.name)
        except CombatError:
            return None   # the command itself reports it
        return "full" if ability_action(c, name, spec) == "full" else ability_action(c, name, spec)
    if cmd == "attack":
        if args.charge:
            return None if c.get("move_mode") == "charge" else "full"
        if args.full:
            return "full"
        return "attack"
    if cmd == "maneuver":
        if args.kind == "release":
            return "free"
        if args.charge and args.kind in ("bull-rush", "overrun"):
            return None if c.get("move_mode") == "charge" else "full"
        if args.kind in ("trip", "disarm", "sunder"):
            return "attack"
        if args.kind == "grapple" and _grapple(st, c["token"], args.target) and "greater grapple" in _feats(c):
            return "move"
        return "standard"
    return None


def charge_attack(st: State, c: Token, what: str) -> None:
    """A single attack: the standard action, or, for a second attack in the same turn, a full attack
    (allowed when it hasn't moved: "after your first attack, you can decide to take a move action
    instead of making your remaining attacks", and the reverse needs no move)."""
    a = turn_actions(c)
    if a.get("full", "") and str(a["full"]).startswith("full attack"):
        return   # more attacks of a full attack
    if a["standard"] and a.get("attacked") and not a["move"]:
        a["standard"], a["full"] = None, f"full attack ({what})"
        return
    spend(st, c, "standard", what)
    a["attacked"] = True


def cmd_act(args: Args, st: State) -> str:
    """Any other action: draw a weapon, stand up, drink a potion, total defense, … Charges the
    action, and resolves what's deterministic: standing up removes prone and provokes."""
    c = token(st, args.token)
    what = args.what or args.kind
    out = []
    off_turn = st.get("turn") != c["token"]
    total_def = "total defense" in what.lower()
    if total_def and args.kind != "standard":   # CRB Table 8-2: a standard action that doesn't provoke
        out.append(f"(total defense is a standard action, not {args.kind}: charged as standard)")
        args.kind = "standard"
    if args.kind == "immediate" and off_turn:
        if c.get("immediate_used") or turn_actions(c)["swift"]:
            raise CombatError(f"{c['token']} already used its immediate/swift action until after its next turn")
        if not c.get("acted"):
            raise CombatError(f"{c['token']} is flat-footed (hasn't acted yet): no immediate actions")
        c["immediate_used"] = what   # takes the swift action of its next turn
        out.append(f"{c['token']} uses an immediate action: {what} (its next turn has no swift action)")
    elif off_turn and args.kind == "free":
        out.append(f"{c['token']}: free action: {what}")
    elif off_turn and not args.override:
        turn = st.get("turn")
        raise CombatError((turn_message(st, c["token"], turn) if turn else "the fight hasn't started its first turn yet.")
                          + " Off-turn, only immediate and free actions work (or --override).")
    elif not args.override:
        spend(st, c, args.kind, what)
        out.append(f"{c['token']}: {args.kind} action: {what}")
    else:
        out.append(f"{c['token']}: {what} (not charged: --override)")
    stand = what.lower().strip() in ("stand up", "stand", "get up")
    if args.provokes or stand:   # the AoOs come first: standing up provokes while it's still prone
        lines, _ = provoke_aoos(st, c, reason=what)
        out += lines
    if stand and c["hp"] > 0:
        if not R.remove_condition(c, "prone"):
            out.append("  (it wasn't prone)")
        else:
            event(st, f"{who(c)} gets up")
    if total_def:   # +4 dodge AC until its next turn, and no attacks of opportunity
        R.add_condition(st, c, "total defense", rounds=1)
        out.append(f"  {c['token']}: total defense, +4 dodge AC and no AoOs until its next turn "
                   f"(3+ ranks of Acrobatics: +6, `cond {c['token']} \"total defense\" --ac 6 --rounds 1`)")
    if args.log:
        event(st, f"{who(c)}: {args.log}")
    if c["side"] == "pc":
        out.append("  (the player rolls any dice this involves, healing, damage or checks: ask for the result, "
                   "never roll it for them)")
    if not off_turn:
        out.append(action_status(st, c))
    return "\n".join(out)


def unaware_tokens(st: State, spec: str | list[str]) -> list[str]:
    """Tokens from a list or a comma list, where "party" means every PC and ally, "enemies" every enemy."""
    names = spec if isinstance(spec, list) else [x.strip() for x in str(spec).split(",") if x.strip()]
    out: list[str] = []
    for n in names:
        if n.lower() in ("party", "pcs"):
            out += [c["token"] for c in st["tokens"] if c["side"] in FRIENDLY]
        elif n.lower() == "enemies":
            out += [c["token"] for c in st["tokens"] if c["side"] not in FRIENDLY]
        else:
            out.append(token(st, n)["token"])
    return sorted(set(out))


def cmd_surprise(args: Args, st: State) -> str:
    """The surprise round (CRB pg. 178): the creatures that were unaware of their foes when the fight
    began get no turn in it and stay flat-footed until their first turn; the aware ones get one standard
    or move action each (plus free and swift). It ends when the next round starts."""
    if args.mode == "off":
        st.pop("surprise", None)
        return "surprise round: off"
    if not args.unaware:
        raise CombatError("who was unaware? `surprise on --unaware C,k1` (or party / enemies); the others act in it")
    unaware = unaware_tokens(st, args.unaware)
    live = [c for c in st["tokens"] if in_fight(c)]
    aware = [c["token"] for c in live if c["token"] not in unaware]
    if not aware or not any(c["token"] in unaware for c in live):
        raise CombatError("no surprise round: one happens only if some, but not all, combatants are aware of their foes")
    st["surprise"] = {"unaware": unaware}
    note = "" if st.get("round", 1) == 1 else " (note: it's already past round 1)"
    return (f"surprise round on{note}: unaware (no turn, flat-footed until they act): {', '.join(unaware)}; "
            f"aware (one standard or move action each): {', '.join(aware)}. It ends when the next round starts.")


def action_ok(st: State, c: Token, kind: str) -> str | None:
    """None if an action of this kind (or "attack": a single attack) is possible now, else why not."""
    a = turn_actions(c)
    if kind == "attack":
        if str(a["full"] or "").startswith("full attack") or (a["standard"] and a.get("attacked") and not a["move"]):
            return None   # further attacks of a full attack
        return can_take(st, c, "standard")
    if kind == "full" and a.get("attacked") and a["standard"] and not a["move"] and not a["full"]:
        return None       # the first attack turns into a full attack
    return can_take(st, c, kind)


def record_action(st: State, c: Token, kind: str, what: str) -> None:
    """Record an action whose command succeeded (action_ok was checked before)."""
    a = turn_actions(c)
    if kind == "attack":
        charge_attack(st, c, what)
    elif kind == "full" and a.get("attacked") and a["standard"] and not a["move"] and not a["full"]:
        a["standard"], a["full"] = None, f"full attack ({what})"
    else:
        take_action(st, c, kind, what)


def spend_moves(st: State, c: Token, n: int, what: str) -> None:
    """Charge n move actions, all or nothing."""
    backup = json.loads(json.dumps(turn_actions(c)))
    try:
        for _ in range(n):
            spend(st, c, "move", what)
    except CombatError:
        c["turn_actions"] = backup
        raise


# ---------- weapons in hand ----------
# What a creature holds decides what it can attack with and whether it threatens (CRB pg. 180-182,
# Table 8-2; library/pf1e/rules/actions-in-combat.md). Natural attacks and unarmed strikes are always
# at hand; manufactured weapons have to be drawn (a move action; with BAB +1 or more it rides along
# with a move action spent on movement; Quick Draw: free) and take one or two hands. A creature only
# threatens with something it can make a melee attack with: a bow in hand gives no attacks of opportunity.

NATURAL_HINTS = ("bite", "claw", "slam", "gore", "tail", "tentacle", "sting", "talon", "wing", "hoof", "pincer",
                 "horn", "hoove", "tusk", "rake", "touch")
ABILITY_HINTS = ("bolt", "ray", "blast", "breath", "spit", "spray", "beam")   # with touch: a Su/Sp attack, nothing held
TWO_HANDED_HINTS = ("bow", "crossbow", "great", "halberd", "glaive", "guisarme", "lance", "longspear", "quarterstaff",
                    "ranseur", "scythe", "pike", "bardiche", "staff")


def weapon_kind(name: str, w: dict[str, Any]) -> str:
    """'natural', 'unarmed', 'ability' (a Su/Sp attack like a ray: always at hand, takes no hands,
    never threatens; the profile flag is "supernatural", since "ability" on an attack is the ability
    score behind its roll) or 'weapon'."""
    n = name.lower()
    if "unarmed" in n:
        return "unarmed"
    if w.get("supernatural") is True or (w.get("supernatural") is None and w.get("type") == "ranged" and w.get("touch")
                                          and any(h in n for h in ABILITY_HINTS)):
        return "ability"
    if w.get("natural") or (w.get("natural") is None and any(h in n for h in NATURAL_HINTS)):
        return "natural"
    return "weapon"


def weapons(c: Token) -> dict[str, dict[str, Any]]:
    """The creature's attacks with their kind, type and hands: {name: {kind, type, hands, reach}}.
    Creatures: the profile's attacks; PCs: the sheet's optional `weapons` map."""
    prof = c.get("profile") or {}
    src = prof.get("attacks") if prof.get("kind") != "pc" else prof.get("weapons")
    out = {}
    for name, w in (src or {}).items():
        kind = weapon_kind(name, w)
        n = name.lower()
        default = 0 if kind != "weapon" else (2 if any(h in n for h in TWO_HANDED_HINTS) or n == "spear" else 1)
        out[name] = {"kind": kind, "type": w.get("type", "melee"), "hands": w.get("hands", default), "reach": w.get("reach")}
    return out


def tracks_weapons(c: Token) -> bool:
    """Whether the script keeps track of what this creature holds (it has manufactured weapons)."""
    return any(w["kind"] == "weapon" for w in weapons(c).values())


def wielding(c: Token) -> list[str]:
    """What the creature holds, ready to attack with (set when it joins the fight)."""
    if "wielding" not in c:
        c["wielding"] = default_wielding(c)
    return c["wielding"]


def inventory_wielding(campaign: str, c: Token) -> list[str] | None:
    """For a party member whose sheet has a container in players/inventory.json: its equipped weapons
    that are attacks in its profile (an empty list: it starts with empty hands). None otherwise."""
    ref = str(c.get("ref") or "")
    inv_file = PROJECT / "campaigns" / campaign / "players" / "inventory.json"
    if not ref or not inv_file.exists():
        return None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import gear
        inv = json.loads(inv_file.read_text(encoding="utf-8"))
        sheet = ref.split(f"campaigns/{campaign}/", 1)[-1]
        box = next((x for x in inv.get("containers", {}).values() if x.get("sheet") == sheet), None)
        if box is None:
            return None
        names = {gear.load_item(campaign, e["item"])["name"].lower() for e in box["items"] if e.get("equipped")}
    except Exception:   # the inventory is a convenience here: never block adding a combatant
        return None
    return [n for n, w in weapons(c).items() if w["kind"] == "weapon" and n.lower() in names]


def default_wielding(c: Token) -> list[str]:
    """At the start of a fight: the profile's `wielding`, else its first manufactured weapon."""
    prof = c.get("profile") or {}
    ws = weapons(c)
    if prof.get("wielding"):
        return [n for n in prof["wielding"] if n in ws]
    first = next((n for n, w in ws.items() if w["kind"] == "weapon"), None)
    return [first] if first else []


def at_hand(c: Token, name: str) -> bool:
    """Whether the creature can attack with that attack right now (natural, unarmed, or held)."""
    w = weapons(c).get(name)
    return w is None or w["kind"] != "weapon" or name in wielding(c)


def free_hands(c: Token) -> int:
    ws = weapons(c)
    return max(0, 2 - sum(ws.get(n, {}).get("hands", 1) for n in wielding(c)))


def threat_reach(c: Token) -> int | None:
    """How far the creature threatens with what it has at hand, or None if it threatens nothing
    (only ranged weapons in hand, or unarmed without Improved Unarmed Strike)."""
    if not tracks_weapons(c):
        return c.get("reach", 5)
    reaches = []
    for n, w in weapons(c).items():
        if w["type"] != "melee":
            continue
        if w["kind"] == "natural" or (w["kind"] == "weapon" and n in wielding(c)) or \
                (w["kind"] == "unarmed" and "improved unarmed strike" in _feats(c)):
            reaches.append(w["reach"] or c.get("reach", 5))
    return max(reaches) if reaches else None


def drop_item(st: State, c: Token, name: str, at: Square | None = None, why: str = "drops") -> str:
    """The creature lets go of a held weapon: it lies on the ground (its square, or `at`)."""
    if name in wielding(c):
        c["wielding"].remove(name)
    sq = at or (c["x"], c["y"])
    st.setdefault("ground", []).append({"item": name, "owner": c["token"], "at": list(sq)})
    if not c.get("hidden"):
        event(st, f"{who(c)} {why} {'their' if c['side'] == 'pc' else 'its'} {name}")
    return f"{c['token']} {why} its {name} (on the ground at {fmt_pos(*sq)})"


def find_weapon(c: Token, name: str) -> str:
    """A weapon of the creature by name (exact, then unique prefix or part).

    Raises:
        CombatError: no such weapon (the message lists them).
    """
    ws = [n for n, w in weapons(c).items() if w["kind"] == "weapon"]
    key = name.lower()
    for test in (lambda n: n.lower() == key, lambda n: n.lower().startswith(key), lambda n: key in n.lower()):
        hits = [n for n in ws if test(n)]
        if len(hits) == 1:
            return hits[0]
    raise CombatError(f"{c['token']} has no weapon {name!r} (its weapons: {', '.join(ws) or 'none tracked'})")


def hand_action(st: State, c: Token, what: str, args: Args) -> str:
    """Charge a draw or sheathe: free with Quick Draw (draw only); with BAB +1 or more a DRAW combines
    with a move action spent on movement this turn (before or after; CRB: not a sheathe); otherwise a
    move action."""
    if getattr(args, "out_of_turn", False) or getattr(args, "override", False) or st.get("turn") != c["token"]:
        return "not charged"
    if what.startswith("draw") and "quick draw" in _feats(c):
        return "free (Quick Draw)"
    a = turn_actions(c)
    bab = (c.get("profile") or {}).get("bab", 1)
    drawing = what.startswith("draw")
    if drawing and bab >= 1 and "movement" in a["move"] and not a.get("combined"):
        a["combined"] = True
        return "combined with its move"
    spend(st, c, "move", what)
    if drawing and bab >= 1:
        a["combinable"] = True   # a move it makes later this turn rides on this move action
    return "a move action"


def cmd_wield(args: Args, st: State) -> str:
    """Draw a weapon (and drop or sheathe what's in the way first)."""
    c = token(st, args.token)
    name = find_weapon(c, args.weapon)
    out = []
    if name in wielding(c):
        return f"{c['token']} already holds its {name}"
    if any(g["item"] == name and g["owner"] == c["token"] for g in st.get("ground", [])):
        raise CombatError(f"{c['token']}'s {name} lies on the ground: `pickup {c['token']} \"{name}\"` (a move action, provokes)")
    if args.drop:
        out.append(drop_item(st, c, find_weapon(c, args.drop)) + " (a free action)")
    if args.sheathe:
        other = find_weapon(c, args.sheathe)
        if other in wielding(c):
            cost = hand_action(st, c, f"sheathe {other}", args)
            c["wielding"].remove(other)
            out.append(f"{c['token']} sheathes its {other} ({cost})")
            if cost != "not charged":   # sheathing a weapon provokes (CRB Table 8-2)
                lines, _ = provoke_aoos(st, c, reason=f"sheathing its {other}")
                out += lines
                if c["hp"] <= 0:
                    return "\n".join(out)
    need = weapons(c)[name]["hands"]
    if need > free_hands(c):
        held = ", ".join(wielding(c))
        raise CombatError(f"{c['token']} needs {need} free hand(s) for its {name} but holds {held}: add --drop {wielding(c)[0]!r} "
                          f"(free, it falls to the ground) or --sheathe (a move action)")
    cost = hand_action(st, c, f"draw {name}", args)
    c["wielding"].append(name)
    if not c.get("hidden"):
        event(st, f"{who(c)} draws {'their' if c['side'] == 'pc' else 'its'} {name}")
    out.append(f"{c['token']} draws its {name} ({cost}); in hand: {', '.join(wielding(c))}")
    return "\n".join(out)


def cmd_pickup(args: Args, st: State) -> str:
    """Pick up an item from the ground (its square or next to it): a move action that provokes."""
    c = token(st, args.token)
    ground = st.get("ground", [])
    here = [g for g in ground if args.item.lower() in g["item"].lower()
            and max(abs(g["at"][0] - c["x"]), abs(g["at"][1] - c["y"])) <= 1]
    if not here:
        raise CombatError(f"no {args.item!r} on the ground in or next to {c['token']}'s square"
                          + (f" (on the ground: {', '.join(g['item'] + ' at ' + fmt_pos(*g['at']) for g in ground)})" if ground else ""))
    g = here[0]
    out = []
    if st.get("turn") == c["token"] and not (args.out_of_turn or args.override):
        spend(st, c, "move", f"pick up {g['item']}")
        lines, _ = provoke_aoos(st, c, reason=f"picking up {g['item']}")
        out += lines
        if c["hp"] <= 0:
            return "\n".join(out)
    ground.remove(g)
    ws = weapons(c)
    if g["item"] in ws and ws[g["item"]]["hands"] <= free_hands(c):
        c["wielding"].append(g["item"])
        out.insert(0, f"{c['token']} picks up the {g['item']} and holds it ready; in hand: {', '.join(wielding(c))}")
    else:
        c.setdefault("carrying", []).append(g["item"])
        out.insert(0, f"{c['token']} picks up the {g['item']} (carried, not ready: no free hand or not its weapon)")
    if not c.get("hidden"):
        event(st, f"{who(c)} picks up the {g['item']}")
    return "\n".join(out)


# ---------- tactical options ----------
# `options g1`: the geometry of a creature's turn, so the DM decides tactics without counting
# squares: where it can reach, where it threatens and flanks its targets, what it needs on the
# d20 from there (the same modifiers attack_mods applies), what provokes, charge lanes, ranged
# positions, area placements and retreat squares. DM only.

@contextlib.contextmanager
def _holding(c: Token, names: list[str] | None) -> Any:
    """Temporarily imagine the creature holding these weapons (None: as it is), for planning a draw."""
    if names is None:
        yield c
        return
    old = list(wielding(c))
    c["wielding"] = list(names)
    try:
        yield c
    finally:
        c["wielding"] = old


@contextlib.contextmanager
def _placed(c: Token, sq: Square) -> Any:
    """Temporarily put a token on another square (all the rules code then sees it there)."""
    old = (c["x"], c["y"])
    c["x"], c["y"] = sq
    try:
        yield c
    finally:
        c["x"], c["y"] = old


def reach_map(st: State, c: Token, max_feet: int, routes: dict[Square, list[Square]] | None = None) -> dict[Square, int]:
    """Every square the token can end its movement on within max_feet, with the cost in feet.
    With `routes`, also fills in the cheapest route to each of them (start and end included)."""
    import heapq
    start = (c["x"], c["y"])

    def fits(x: int, y: int, final: bool) -> bool:
        for cx, cy in cells(c, (x, y)):
            if cost(st, cx, cy) is None or blocked_by_hostile(st, c, cx, cy):
                return False
            if final and occupied(st, c, cx, cy):
                return False
        return True

    p0 = diag_parity(st, c)
    best = {(start, p0): 0}
    out = {start: 0}
    came: dict[tuple[Square, int], tuple[Square, int]] = {}
    end_key: dict[Square, tuple[Square, int]] = {start: (start, p0)}
    heap = [(0, start, p0)]
    while heap:
        feet, (x, y), parity = heapq.heappop(heap)
        if feet > best.get(((x, y), parity), 10 ** 9):
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not fits(nx, ny, False):
                    continue
                diag = dx != 0 and dy != 0
                if diag and any(cost(st, cx, cy) is None for q in ((x + dx, y), (x, y + dy)) for cx, cy in cells(c, q)):
                    continue   # a wall's corner blocks a diagonal; a creature's doesn't (CRB p. 192)
                mult = max(cost(st, cx, cy) or 1 for cx, cy in cells(c, (nx, ny)))
                squares, npar = ((mult + mult // 2 if mult > 1 else (1 if parity == 0 else 2)), 1 - parity) if diag else (mult, parity)
                nf = feet + 5 * squares
                if nf > max_feet or nf >= best.get(((nx, ny), npar), 10 ** 9):
                    continue
                best[((nx, ny), npar)] = nf
                came[((nx, ny), npar)] = ((x, y), parity)
                heapq.heappush(heap, (nf, (nx, ny), npar))
                if fits(nx, ny, True) and nf < out.get((nx, ny), 10 ** 9):
                    out[(nx, ny)] = nf
                    end_key[(nx, ny)] = ((nx, ny), npar)
    if routes is not None:
        for sq, key in end_key.items():
            route = [sq]
            while key in came:
                key = came[key]
                route.append(key[0])
            routes[sq] = route[::-1]
    return out


def _foes(st: State, c: Token) -> list[Token]:
    """Active creatures on the other side, nearest first."""
    return sorted(V.enemies(st, c), key=lambda o: feet_between(c, o))


def path_provokers(st: State, c: Token, route: list[Square], memo: dict[Square, list[str]]) -> list[str]:
    """Who would get an attack of opportunity on this route: everyone threatening a square it leaves
    (the same rule `move` applies). `memo` caches who threatens each square."""
    out: list[str] = []
    for sq in route[:-1]:
        if sq not in memo:
            with _placed(c, sq):
                memo[sq] = _threatened_by(st, c)
        out += [t for t in memo[sq] if t not in out]
    return out


def _threatened_by(st: State, c: Token) -> list[str]:
    """Enemies that threaten the token where it stands and could make an AoO."""
    return [o["token"] for o in _foes(st, c) if threatens(o, c) and not aoo_blocked(o)
            and V.concealment(st, o, c)[0] < 50]


def _needs(st: State, a: Token, t: Token, w: dict[str, Any], kind: str, charge: bool = False) -> tuple[int, int, list[str]]:
    """(d20 roll needed to hit, miss chance %, notes) for one attack from where `a` stands."""
    delta, ac, notes, _dm, miss = attack_mods(st, a, t, kind, bool(w.get("touch")), charge, w)
    b = w["bonus"][0] if isinstance(w.get("bonus"), list) else (w.get("bonus") or 0)
    return max(2, min(20, ac - (b + delta))), miss, notes


def charge_problem(st: State, c: Token, t: Token, dest: Square) -> str | None:
    """Why `c` can't charge `t` by moving to dest, or None. CRB pg. 198: at least 10 ft, at most
    double speed, directly toward the opponent along a clear path (nothing that hinders movement,
    no creature in the way, allies included), ending in the closest space from which it can attack."""
    start = (c["x"], c["y"])
    d = 5 * R.sq_dist(start, dest)
    if d < 10:
        return "a charge moves at least 10 ft"
    if d > 2 * (c.get("speed") or 30):
        return f"a charge moves at most double its speed ({2 * (c.get('speed') or 30)} ft)"
    with _placed(c, dest):
        if not threatens(c, t):
            return f"it couldn't attack {t['token']} from there"
    if not _straight_clear(st, c, dest):
        return "the line isn't clear (difficult terrain, an obstacle or a creature, allies included, is in the way)"
    closest = charge_squares(st, c, t)
    if dest not in closest:
        return (f"a charge ends on the closest square from which it can attack ({', '.join(fmt_pos(*q) for q in sorted(closest))}"
                f", {5 * R.sq_dist(start, next(iter(closest)))} ft)") if closest else "no square to attack it from"
    return None


def charge_squares(st: State, c: Token, t: Token) -> set[Square]:
    """The squares closest to `c` from which it could attack `t` (free, passable footprint)."""
    start, best = (c["x"], c["y"]), None
    found: set[Square] = set()
    for x in range(st["w"] - c["size"] + 1):
        for y in range(st["h"] - c["size"] + 1):
            q = (x, y)
            d = R.sq_dist(start, q)
            if q == start or (best is not None and d > best):
                continue
            if any(cost(st, *cell) is None or occupied(st, c, *cell) for cell in cells(c, q)):
                continue
            with _placed(c, q):
                if not threatens(c, t):
                    continue
            if best is None or d < best:
                best, found = d, set()
            found.add(q)
    return found


def straight_route(c: Token, dest: Square) -> list[Square]:
    """The squares a straight move from c's square to dest passes, in order (a charge; one-square
    creatures; a larger one keeps its path, which _straight_clear has checked)."""
    with _placed(c, dest):
        p2 = R.center(c)
    route = [(c["x"], c["y"])]
    for sq in R.segment_cells(R.center(c), p2, 0.1) + [dest]:
        if sq != route[-1]:
            route.append(sq)
    return route


def _straight_clear(st: State, c: Token, dest: Square) -> bool:
    """A charge lane: every square between here and dest passable, not difficult, and empty."""
    with _placed(c, dest):
        p2 = R.center(c)
        dest_cells = set(cells(c))
    with _placed(c, (c["x"], c["y"])):
        p1 = R.center(c)
        own = set(cells(c))
    for cell in set(R.segment_cells(p1, p2, 0.1)) | dest_cells:
        if cell in own:
            continue
        if (cost(st, *cell) or 99) != 1:
            return False
        if any(o is not c and not o.get("removed") and o["hp"] > 0 and cell in cells(o) for o in st["tokens"]):
            return False
    return True


# ---------- turn plans (expected values) ----------
# Each plan is a whole turn (a move and an action) with rough expected values: damage it deals,
# support it gives (flanking for an ally, buffs, healing), and damage it risks (the AoOs it provokes,
# and what the enemies can do to it where it ends up). The numbers make trade-offs visible; the DM
# or runner still decides by the creature's nature, morale and knowledge.

COND_VALUE = {"asleep": 6, "helpless": 6, "paralyzed": 6, "unconscious": 6, "stunned": 5, "dazed": 5, "nauseated": 4,
              "panicked": 4, "frightened": 3, "confused": 3, "blinded": 3, "entangled": 2, "shaken": 2, "sickened": 2,
              "staggered": 3, "dazzled": 1, "prone": 2}


def dice_avg(expr: str | None) -> float:
    """The average of a dice expression like '2d6+3' (at least 1 per hit)."""
    if not expr:
        return 0.0
    total, sign = 0.0, 1
    for tok in re.findall(r"[+-]|\d+d\d+|\d+", expr.replace(" ", "")):
        if tok in "+-":
            sign = -1 if tok == "-" else 1
        elif "d" in tok:
            n, d = tok.split("d")
            total += sign * int(n) * (int(d) + 1) / 2
        else:
            total += sign * int(tok)
    return max(1.0, total)


def avg_rounds(v: Any) -> float:
    """A duration's expected rounds (dice durations averaged)."""
    return dice_avg(v) if isinstance(v, str) else float(v or 1)


def p_hit(need: int, miss: int = 0) -> float:
    """The chance to hit with a d20 roll of `need`+, after a miss chance."""
    return max(0.05, min(0.95, (21 - need) / 20)) * (1 - miss / 100)


def p_fail_save(t: Token, kind: str | None, dc: int | None) -> float:
    """The chance a creature fails a save (its profile bonus; +4 if unknown)."""
    if not kind or dc is None:
        return 1.0
    bonus = R.save_bonus(t, kind)
    bonus = 4 if bonus is None else bonus
    return 1 - max(0.05, min(0.95, (21 - (dc - bonus)) / 20))


def _attack_ev(st: State, a: Token, t: Token, weapons: list[tuple[str, dict[str, Any], int]], kind: str,
               charge: bool = False) -> tuple[float, list[str]]:
    """Expected damage of a set of attacks (name, weapon, bonus) from where `a` stands, and roll notes."""
    ev, notes = 0.0, []
    for name, w, bonus in weapons:
        delta, ac, _n, _d, miss = attack_mods(st, a, t, kind, bool(w.get("touch")), charge, w)
        need = max(2, min(20, ac - (bonus + delta)))
        dmg = dice_avg(w.get("damage")) + R.total(a, "dmg") + R.str_damage_change(a, w, kind)
        sneak, _ = sneak_attack(st, a, t, kind, miss)
        ev += p_hit(need, miss) * (max(1.0, dmg) + dice_avg(sneak) if sneak else max(1.0, dmg))
        notes.append(f"{need}+" + (f" (+{sneak} sneak)" if sneak else "") + (f" {miss}% miss" if miss else ""))
    return ev, notes


def _weapons(prof: dict[str, Any], kind: str, full: bool) -> list[tuple[str, dict[str, Any], int]]:
    """The attacks of one action: the best single attack, or a full attack (full_attack list or iteratives)."""
    attacks = {n: w for n, w in (prof.get("attacks") or {}).items() if w.get("type", "melee") == kind}
    if not attacks:
        return []
    if full:
        seq: list[tuple[str, dict[str, Any], int]] = []
        names = [n for n in (prof.get("full_attack") or []) if n in attacks]
        if names:
            for n in names:
                b = attacks[n]["bonus"]
                seq.append((n, attacks[n], b[0] if isinstance(b, list) else b))
        else:
            for n, w in attacks.items():
                if isinstance(w["bonus"], list):
                    seq += [(n, w, b) for b in w["bonus"]]
                    break
        if seq:
            return seq
    best = max(attacks.items(), key=lambda kv: dice_avg(kv[1].get("damage")) + (kv[1]["bonus"][0] if isinstance(kv[1]["bonus"], list) else kv[1]["bonus"]))
    b = best[1]["bonus"]
    return [(best[0], best[1], b[0] if isinstance(b, list) else b)]


SPOT_VALUE = 1.5   # finding an enemy that slipped out of sight again (a turn's worth of not losing it)
PC_GUESS = 3.0   # a PC's expected damage per round when its profile lists no attacks (hits half the time for ~6)


def _can_go_after(st: State, f: Token, o: Token) -> bool:
    """Whether foe `f` could attack `o` next round: reach it with a move, or see it to shoot."""
    if feet_between(f, o) - (f.get("reach") or 5) <= (f.get("speed") or 30):
        return True
    return V.concealment(st, V.presumed(f, o), o)[0] < 50


def _incoming(st: State, c: Token, sq: Square, memo: dict[Square, float]) -> float:
    """Expected damage the enemies can deal `c` at sq next round: each enemy's best single attack, if
    it can reach it or see it there, shared out over everyone on c's side that enemy could go after
    (one guard facing three of them hits c a third of the time)."""
    if sq in memo:
        return memo[sq]
    total = 0.0
    friendly = c["side"] in FRIENDLY
    side = [o for o in st["tokens"] if o is not c and not o.get("removed") and o["hp"] > 0
            and (o["side"] in FRIENDLY) == friendly]
    with _placed(c, sq):
        for f in _foes(st, c):
            prof = f.get("profile") or {}
            best = 0.0
            share = 1 / (1 + sum(1 for o in side if _can_go_after(st, f, o)))
            if not prof.get("attacks"):   # a PC sheet: guess, nearer is worse
                near = feet_between(f, c) - 5 <= (f.get("speed") or 30)
                total += share * (PC_GUESS if near else (PC_GUESS / 2 if V.concealment(st, V.presumed(f, c), c)[0] < 50 else 0.0))
                continue
            mel = _weapons(prof, "melee", False)
            if mel and feet_between(f, c) - (f.get("reach") or 5) <= (f.get("speed") or 30):
                _n, w, b = mel[0]
                ac = (R.defenses(c)["ac"] or 10) + R.total(c, "ac")
                best = p_hit(max(2, min(20, ac - b))) * dice_avg(w.get("damage"))
            rng = _weapons(prof, "ranged", False)
            if rng and V.concealment(st, V.presumed(f, c), c)[0] < 50:
                ev, _ = _attack_ev(st, f, c, rng, "ranged")
                best = max(best, ev)
            total += share * best
    memo[sq] = total
    return total


def _aoo_risk(st: State, c: Token, provokers: list[str]) -> float:
    """Expected damage from the attacks of opportunity a move provokes."""
    risk = 0.0
    for tok in provokers:
        f = next((o for o in st["tokens"] if o["token"] == tok), None)
        mel = _weapons((f or {}).get("profile") or {}, "melee", False)
        if f and not ((f.get("profile") or {}).get("attacks")):
            risk += PC_GUESS
        elif f and mel:
            ev, _ = _attack_ev(st, f, c, mel[:1], "melee")
            risk += ev
    return risk


def _ally_attacks(o: Token) -> tuple[int, float]:
    """An ally's attacks per round and average damage per hit (its best melee or ranged routine), for
    valuing support. A PC sheet lists no attacks: one attack for ~6 is assumed."""
    prof = o.get("profile") or {}
    ws = _weapons(prof, "melee", True) or _weapons(prof, "ranged", True)
    if ws:
        return len(ws), sum(dice_avg(w.get("damage")) for _n, w, _b in ws) / len(ws)
    return (1, 6.0) if o["side"] == "pc" else (0, 0.0)


def _ally_attack_avg(o: Token) -> float:
    """An ally's average damage per round if every attack hit, for valuing support."""
    n, avg = _ally_attacks(o)
    return n * avg


def _threat_of(st: State, f: Token, c: Token) -> tuple[float, float]:
    """(chance to hit, average damage) of `f`'s attack of opportunity on `c`."""
    if not (f.get("profile") or {}).get("attacks"):
        return 0.5, 6.0
    mel = _weapons(f.get("profile") or {}, "melee", False)
    if not mel:
        return 0.0, 0.0
    _n, w, b = mel[0]
    delta, ac, _no, _d, miss = attack_mods(st, f, c, "melee", False, False, w)
    return p_hit(max(2, min(20, ac - (b + delta))), miss), dice_avg(w.get("damage"))


def p_check(bonus: int, dc: int) -> float:
    """The chance a d20 check with that bonus meets the DC."""
    return max(0.0, min(1.0, (21 - (dc - bonus)) / 20))


PLAN_KINDS = ("melee", "ranged", "spell", "buff", "heal", "defense", "retreat")


def tactics_weights(st: State, c: Token) -> tuple[dict[str, float], str]:
    """The creature's preference weights from its profile's `tactics` (personality), plus the morale
    weights once morale breaks (HP at or below `hp` of its maximum, or `allies_down` of its side down).
    Returns (weights by plan kind, a note for the report)."""
    tac = (c.get("profile") or {}).get("tactics") or {}
    weights = {k: float(v) for k, v in (tac.get("weights") or {}).items()}
    notes = [", ".join(f"{k} {v:+g}" for k, v in weights.items())] if weights else []
    mor = tac.get("morale") or {}
    why = []
    if mor.get("hp") is not None and c["hp"] <= mor["hp"] * (c.get("max_hp") or c["hp"]):
        why.append(f"HP {c['hp']}/{c.get('max_hp')}")
    side = [o for o in st["tokens"] if o is not c and not o.get("removed") and o["side"] == c["side"]]
    if mor.get("allies_down") is not None and side:
        down = sum(1 for o in side if o["hp"] <= 0 or is_dead(o))
        if down / len(side) >= mor["allies_down"]:
            why.append(f"{down}/{len(side)} of its side down")
    if why and mor.get("weights"):
        for k, v in mor["weights"].items():
            weights[k] = weights.get(k, 0.0) + float(v)
        notes.append(f"MORALE BREAKS ({'; '.join(why)}): " + ", ".join(f"{k} {v:+g}" for k, v in mor["weights"].items())
                     + (f" — {mor['note']}" if mor.get("note") else ""))
    return weights, "; ".join(notes)


# Dropping a weapon to draw another is free, but the weapon lies on the ground: getting it back is a
# move action that provokes, and it may be lost for good. Plans that drop one pay for it (in points of
# expected damage), more when it was the creature's only melee weapon (it then threatens no one).
DROP_COST = 1.0
RELIEF = 0.5       # the share of a foe's threat to an ally that hitting it is worth (scaled by the HP it takes)
RELIEF_PC = 1.5    # an ally the foe threatens counts more when it's the player's character
DROP_LAST_MELEE = 1.5


def drop_cost(c: Token, dropped: list[str]) -> float:
    """The plan penalty for letting go of these held weapons."""
    if not dropped:
        return 0.0
    ws = weapons(c)
    on_ground = {g for g in dropped}
    melee_left = [n for n, w in ws.items() if w["type"] == "melee" and n not in on_ground
                  and (w["kind"] == "weapon" or w["kind"] == "natural"
                       or (w["kind"] == "unarmed" and "improved unarmed strike" in _feats(c)))]
    lost_melee = any(ws.get(n, {}).get("type") == "melee" for n in dropped) and not melee_left
    return DROP_COST * len(dropped) + (DROP_LAST_MELEE if lost_melee else 0.0)


def turn_plans(st: State, c: Token, one: dict[Square, int], routes: dict[Square, list[Square]],
               provokers: Any, two: dict[Square, int] | None = None, routes2: dict[Square, list[Square]] | None = None,
               limit: int = 9) -> list[str]:
    """Ranked whole-turn plans for `c` (see the section comment)."""
    prof = c.get("profile") or {}
    start = (c["x"], c["y"])
    friendly = c["side"] in FRIENDLY
    foes = _foes(st, c)[:4]
    allies = [o for o in st["tokens"] if o is not c and not o.get("removed") and in_fight(o)
              and (o["side"] in FRIENDLY) == friendly]
    memo: dict[Square, float] = {}
    plans: list[tuple[float, str]] = []
    weights, wnote = tactics_weights(st, c)
    head: list[str] = []
    if wnote:
        head.append(f"  (its tactics: {wnote})")
    fear = next((n for n in ("cowering", "panicked", "frightened") if R.has(c, n)), None)
    if fear == "cowering":
        return ["  COWERING: it can take no actions this turn."]
    if fear:
        head.append(f"  {fear.upper()}: it must flee from the source of its fear as well as it can"
                    + (", dropping what it holds; it can't attack" if fear == "panicked"
                       else "; it fights only if cornered") + ". Only flight is listed.")
    attackable = [] if fear else foes
    # its standard action is spent this turn, a move is left: only where to move (or stay) matters
    ta = turn_actions(c) if st.get("turn") == c["token"] else {}
    move_only = bool(ta.get("standard")) and not ta.get("full") and not c.get("moved") and not c.get("stepped") \
        and can_take(st, c, "move") is None
    if move_only:
        head.append("  ITS STANDARD ACTION IS SPENT: only its move action is left (move, or stay put).")
        attackable = []
        two, routes2 = one, routes   # "advance" and "withdraw" become single moves
    # A single action this turn (surprise round, staggered; nauseated: only a move): it acts where it
    # stands or after a 5-foot step, or it moves, not both. Plans that act use only those squares;
    # "advance" and "withdraw" become single moves.
    limited = None if move_only else restriction(st, c)
    if limited:
        head.append(f"  ONE ACTION THIS TURN ({limited}): it acts where it stands (or after a 5-foot step) "
                    "or it moves, not both.")
        if R.has(c, "nauseated"):
            attackable = []
        two, routes2 = one, routes
        one = {q: f for q, f in one.items() if q == start or (f == 5 and R.sq_dist(start, q) == 1)}
    single = move_only or bool(limited)

    def add(kind: str, deal: float, support: float, sq: Square, provoked: list[str], text: str,
            extra: str = "", exposure: float = 1.0, idle: float = 0.0, lose: float = 0.0) -> None:
        risk_aoo = _aoo_risk(st, c, provoked)
        risk_next = _incoming(st, c, sq, memo) * exposure
        w = weights.get(kind, 0.0)
        score = deal + support - risk_aoo - 0.5 * risk_next + w - idle - lose
        parts = [f"deals ~{deal:.1f}" if deal else "", f"support ~{support:.1f}" if support else "",
                 f"AoO risk ~{risk_aoo:.1f} ({', '.join(provoked)})" if provoked else "",
                 f"takes ~{risk_next:.1f} next round there", f"{kind} {w:+g}" if w else "",
                 f"a wasted turn −{idle:g}" if idle else "", f"a dropped weapon −{lose:g}" if lose else ""]
        plans.append((score, f"[{score:+.1f}] {text}" + (f" {extra}" if extra else "") + " — " + ", ".join(p for p in parts if p)))

    def where(sq: Square, feet: int) -> str:
        if sq == start:
            return "stay, "
        how = "5-ft step to " if feet == 5 and R.sq_dist(start, sq) == 1 else f"move {feet} ft to "
        return how + fmt_pos(*sq) + ", "

    # --- relief: hitting a foe that threatens an ally takes pressure off that ally. Worth what the foe
    # would deal that ally next round (×1.5 for the PC), times the share of the foe's HP the attack takes
    # (a likely kill relieves the most), counted at half. Breaks ties like "both guards, 14+" in favour of
    # the one standing over the wizard.
    relief_memo: dict[str, tuple[float, str]] = {}

    def relief(t: Token) -> tuple[float, str]:
        if t["token"] not in relief_memo:
            best_r: tuple[float, str] = (0.0, "")
            t_ws = [x for x in _weapons(t.get("profile") or {}, "melee", True) if at_hand(t, x[0])]
            for o in allies:
                if t_ws and o["hp"] >= 0 and not o.get("removed") and threatens(t, o):
                    ev_o, _n = _attack_ev(st, t, o, t_ws, "melee")
                    val = ev_o * (RELIEF_PC if o["side"] == "pc" else 1.0)
                    if val > best_r[0]:
                        best_r = (val, o["token"])
            relief_memo[t["token"]] = best_r
        return relief_memo[t["token"]]

    # --- attacks ---
    attacked: set[str] = set()   # foes with a melee attack plan this turn
    for t in attackable:
        unseen = V.concealment(st, c, t)[0] >= 50
        for kind in ("melee", "ranged"):
            best: tuple[float, Any] | None = None
            sheathe_plan: tuple[float, list[str], str, Any] | None = None
            for sq, feet in one.items():
                step = sq == start or (feet == 5 and R.sq_dist(start, sq) == 1)
                ws = [x for x in _weapons(prof, kind, step and not limited) if ammo_left(c, x[0]) != 0 and at_hand(c, x[0])]
                draw = ""
                dropped: list[str] = []
                if not ws and limited:   # drawing takes the move action, and the attack would be a second one
                    break
                if not ws:   # nothing of this kind in hand: draw one (the move action: no full attack this turn)
                    ws = [x for x in _weapons(prof, kind, False) if ammo_left(c, x[0]) != 0][:1]
                    if not ws:
                        break
                    need = weapons(c).get(ws[0][0], {}).get("hands", 1)
                    dropped = list(wielding(c)) if need > free_hands(c) and wielding(c) else []
                    drop = f" (dropping its {', '.join(dropped)})" if dropped else ""
                    draw = f"draw {ws[0][0]}{drop}, "
                with _placed(c, sq), _holding(c, [ws[0][0]] if draw else None):
                    if kind == "melee" and not threatens(c, t):
                        continue
                    ev, notes = _attack_ev(st, c, t, ws, kind)
                    flank_gift = 0.0
                    gifted = []
                    if kind == "melee":
                        for o in allies:
                            if can_act(o) and threatens(o, t) and flanks(c, o, t):
                                n_att, avg = _ally_attacks(o)
                                gain = n_att * 0.1 * avg
                                osneak = (o.get("profile") or {}).get("sneak_attack")
                                gain += 0.5 * dice_avg(osneak) if osneak else 0
                                flank_gift += gain
                                gifted.append(o["token"])
                    shoot_threat = _threatened_by(st, c) if kind == "ranged" else []
                provoked = sorted(set(([] if step else provokers(sq)) + shoot_threat))
                if dropped and sq == start and not move_only and sheathe_plan is None:
                    # the alternative: sheathe (a move action, provokes) and draw (the other move): no attack
                    # this turn, the weapon kept; next round it attacks from here (counted at half)
                    sheathe_plan = (ev, dropped, ws[0][0], _threatened_by(st, c))
                full = step and len(ws) > 1
                label_ = (f"{where(sq, feet)}{draw}{'full attack' if full else 'attack'} {t['token']} "
                          f"({'/'.join(n for n, _w, _b in ws[:3])}{'…' if len(ws) > 3 else ''}: hits on {', '.join(notes[:3])})"
                          + (" [can't see it: guess its square]" if unseen else ""))
                extra = f"gives {', '.join(gifted)} flanking" if gifted else ""
                pressure, eased = relief(t)
                eases = RELIEF * pressure * min(1.0, ev / max(1, t["hp"])) if pressure else 0.0
                if eases >= 0.05:
                    extra = ", ".join(x for x in (extra, f"takes pressure off {eased}") if x)
                lose = drop_cost(c, dropped)
                score = ev + flank_gift + eases - _aoo_risk(st, c, provoked) - lose
                if best is None or score > best[0]:
                    best = (score, (ev, flank_gift + eases, sq, provoked, label_, extra, lose))
            if best:
                ev, gift, sq, provoked, label_, extra, lose = best[1]
                add(kind, ev, gift, sq, provoked, label_, extra, lose=lose)
                if kind == "melee":
                    attacked.add(t["token"])
            if sheathe_plan and not limited:
                ev_s, held, drawn, threats = sheathe_plan
                add(kind, 0.5 * ev_s, 0.0, start, threats,
                    f"stay, sheathe its {', '.join(held)} and draw its {drawn} (two move actions, no attack now)",
                    f"(next round: attacks {t['token']} ~{ev_s:.1f}, counted at half)")

    # --- advance: a melee creature that can't reach a foe this turn closes in (a double move) ---
    melee_ws = _weapons(prof, "melee", True)
    if two and routes2 and melee_ws:
        memo2: dict[Square, list[str]] = {}
        for t in [o for o in attackable if o["token"] not in attacked][:3]:
            spots = []
            melee_held = [n for n, _w, _b in melee_ws if at_hand(c, n)]
            imagined = None if melee_held else [melee_ws[0][0]]   # it would draw its melee weapon on the way
            let_go = (list(wielding(c)) if imagined and weapons(c).get(imagined[0], {}).get("hands", 1) > free_hands(c)
                      else [])   # …letting go of what's in its hands (sheathing would cost the second move)
            for q, feet in two.items():
                with _placed(c, q), _holding(c, imagined):
                    if threatens(c, t):
                        spots.append(q)
            if not spots:   # too far even so: as close as it gets
                spots = [min(two, key=lambda q: (min(R.sq_dist(q, cc) for cc in cells(t)), two[q]))]
            spots = [q for q in spots if q != start] or spots
            if spots == [start]:
                continue
            prov_of = {q: path_provokers(st, c, routes2.get(q, [start, q]), memo2) for q in spots}
            q = min(spots, key=lambda q: (_aoo_risk(st, c, prov_of[q]), _incoming(st, c, q, memo), two[q]))
            unseen_now = V.concealment(st, c, t)[0] >= 50
            with _placed(c, q), _holding(c, imagined):
                reach_next = threatens(c, t)
                ev_next, _n = _attack_ev(st, c, t, melee_ws, "melee")
                hidden = c.get("hidden") and all(V.hidden_from(st, c, V.presumed(f, c)) for f in foes)
                in_view = unseen_now and V.concealment(st, c, t)[0] < 50
            how = f"move {two[q]} ft" if single else f"move {one[q]} ft" if q in one else f"double move {two[q]} ft"
            if move_only and q not in one:
                continue
            spot = SPOT_VALUE if in_view else 0.0   # an enemy back in sight: it (and its allies) can strike next round
            add("melee", 0.5 * ev_next if reach_next else 0.0, spot, q, prov_of[q],
                f"{how} to {fmt_pos(*q)}" + (f", drawing its {imagined[0]}" if imagined else "")
                + (f" (dropping its {', '.join(let_go)})" if let_go else "") + f", closing on {t['token']}"
                + (" (stays hidden)" if hidden else "") + (" (it comes into view there)" if in_view else ""),
                f"(next round: full attack ~{ev_next:.1f}, counted at half)" if reach_next else "(still out of reach)",
                lose=drop_cost(c, let_go))

    # --- spells, spell-like abilities and special abilities with effect data ---
    sp = _spent(c)
    near_foes = sorted((sq for sq in one if sq != start),
                       key=lambda q: min((R.sq_dist(q, (f["x"], f["y"])) for f in foes), default=0))[:6]
    candidates = [start] + near_foes
    # (label, effect, DC, spell level, concentration bonus, provokes)
    castables: list[tuple[str, dict[str, Any], int | None, int, int, bool]] = []
    for sc in prof.get("spellcasting") or []:
        effects = {k.lower(): v for k, v in (sc.get("effects") or {}).items()}
        for lvl, names in (sc.get("spells") or {}).items():
            for nm in dict.fromkeys(names):
                data = effects.get(nm.lower())
                if not data:
                    continue
                if spell_left(c, sc, lvl, nm):
                    castables.append((f"cast {nm}", data, data.get("dc") or sc["dc_base"] + int(lvl), int(lvl),
                                      sc.get("concentration", sc.get("cl", 1)), True))
    for s_ in prof.get("sla") or []:
        if s_.get("effect") and sla_left(c, s_):
            castables.append((f"use {s_['name']}", s_["effect"], s_["effect"].get("dc") or s_.get("dc"), s_.get("level", 1),
                              s_.get("concentration", s_.get("cl", 1) + 3), True))
    for nm, spec in (prof.get("abilities") or {}).items():
        used = sp.get("abilities", {}).get(nm, 0)
        if spec.get("uses") is None or used < spec["uses"]:
            castables.append((f"ability {nm}", spec, spec.get("dc"), 0, 0, False))   # Su/Ex: no AoO

    if fear or move_only or (limited and R.has(c, "nauseated")):
        castables = []

    def casting(q: Square, lvl: int, conc: int, provokes: bool) -> tuple[float, list[str], str]:
        """Casting at q: (chance the effect happens, who it provokes, a note). Threatened, a spell
        provokes and a hit can break it; casting defensively avoids the AoO but needs a check."""
        if not provokes:
            return 1.0, [], ""
        with _placed(c, q):
            threats = _threatened_by(st, c)
            if not threats:
                return 1.0, [], ""
            keep_open = 1.0
            for tok in threats:
                f = token(st, tok)
                ph, avg = _threat_of(st, f, c)
                keep_open *= 1 - ph * (1 - p_check(conc, 10 + round(avg) + lvl))
        keep_def = p_check(conc, 15 + 2 * lvl)
        risk = _aoo_risk(st, c, threats)
        if keep_def * 10 >= keep_open * 10 - risk:   # rough: is the AoO worth dodging?
            return keep_def, [], f" (cast defensively: kept {keep_def:.0%})"
        return keep_open, threats, f" (provokes; kept {keep_open:.0%})"

    for label_, data, dc, lvl, conc, provokes in castables:
        name = label_.split(" ", 1)[1]
        if is_buff(data):   # a buff: per round, for every ally it reaches
            if data.get("maintain") and c.get("performing") == name:
                head.append(f"  (keeps up {name} with a {data['maintain']} action alongside any plan below)")
                continue
            reach = data.get("range")
            hit = [o for o in allies + [c] if can_act(o) and (reach is None or feet_between(c, o) <= reach)]
            if data.get("target") == "self":
                hit = [c]
            elif data.get("target") == "one":
                hit = sorted((o for o in hit if o is not c), key=lambda o: -_ally_attack_avg(o))[:1]
            bonus = buff_mods(data)
            per_round = 0.0
            for o in hit:
                n_att, avg = _ally_attacks(o)
                per_round += n_att * (0.05 * bonus.get("atk", 0) * avg + 0.6 * bonus.get("dmg", 0))
                per_round += 0.15 * bonus.get("ac", 0) * PC_GUESS + 0.1 * bonus.get("save", 0)
            rounds = 2 if data.get("maintain") else min(3.0, avg_rounds(data.get("buff_rounds", 1)))
            keep, prov, note = casting(start, lvl, conc, provokes)
            if per_round > 0:
                add("buff", 0, per_round * rounds * keep, start, prov,
                    f"stay, {label_} on {len(hit)} {'ally' if len(hit) == 1 else 'allies'}{note}",
                    f"(~{per_round:.1f}/round{', kept up for free after' if data.get('maintain') == 'free' else ''})")
            continue
        if data.get("heal"):
            amount = dice_avg(data["heal"])
            wounded = [o for o in st["tokens"] if not o.get("removed") and not is_dead(o)   # the dying too
                       and (o["side"] in FRIENDLY) == friendly and o["hp"] < o.get("max_hp", o["hp"])]

            def heal_value(o: Token) -> float:
                return min(amount, o.get("max_hp", 0) - o["hp"]) + (8.0 if o["hp"] < 0 else 0.0)   # dying: back on its feet
            if data.get("target") == "area":
                radius = int((data.get("area") or "burst 30").split()[1])
                value = sum(heal_value(o) for o in wounded if feet_between(c, o) <= radius)
                keep, prov, note = casting(start, lvl, conc, provokes)
                if value > 0:
                    add("heal", 0, value * keep, start, prov, f"stay, {label_} (heals ~{amount:.0f} each){note}")
                continue
            for o in sorted(wounded, key=lambda o: -heal_value(o))[:2]:
                rng = max(data.get("range") or 0, 5)
                spots = [q for q in one if 5 * min(R.sq_dist(q, cc) for cc in cells(o)) <= rng]
                if not spots:   # out of reach this turn: get there now, heal next round
                    if move_only or not (two and routes2):
                        continue
                    later = [q for q in two if 5 * min(R.sq_dist(q, cc) for cc in cells(o)) <= rng]
                    if not later:
                        later = [min(two, key=lambda q: (min(R.sq_dist(q, cc) for cc in cells(o)), two[q]))]
                    q = min(later, key=lambda q: (_incoming(st, c, q, memo), two[q]))
                    if q == start:
                        continue
                    prov = path_provokers(st, c, routes2.get(q, [start, q]), {})
                    state_ = "dying" if o["hp"] < 0 else f"{o['hp']}/{o.get('max_hp')} HP"
                    reached = 5 * min(R.sq_dist(q, cc) for cc in cells(o)) <= rng
                    add("heal", 0, 0.5 * heal_value(o) if reached else 0.25 * heal_value(o), q, prov,
                        f"{'move' if q in one or single else 'double move'} {two[q]} ft to {fmt_pos(*q)}, toward {o['token']} ({state_}) "
                        f"to {label_.split(' ', 1)[0]} {label_.split(' ', 1)[1]} next round",
                        "(counted at half)" if reached else "(still not there: counted at a quarter)")
                    continue
                q = min(spots, key=lambda q: (len([] if q == start else provokers(q)), _incoming(st, c, q, memo), one[q]))
                keep, prov, note = casting(q, lvl, conc, provokes)
                state_ = "dying" if o["hp"] < 0 else f"{o['hp']}/{o.get('max_hp')} HP"
                add("heal", 0, heal_value(o) * keep, q, sorted(set(([] if q == start else provokers(q)) + prov)),
                    f"{where(q, one.get(q, 0))}{label_} on {o['token']} ({state_}){note}")
            continue
        per_dmg = dice_avg(data.get("dmg")) if data.get("dmg") else 0.0
        cond_v = COND_VALUE.get(str(data.get("cond", "")).lower(), 2 if data.get("cond") else 0) * min(3.0, avg_rounds(data.get("cond_rounds", 1)))

        spec_imm = data.get("immunity")
        imm = {"name": name.lower(), "from": c["token"] if (spec_imm or {}).get("from") == "caster" else None} if spec_imm else None

        def value_of(targets: list[Token]) -> float:
            v = 0.0
            for o in targets:
                if is_immune(st, o, imm):   # it wouldn't work on this one right now
                    continue
                pf = p_fail_save(o, data.get("save"), dc)
                dmg_v = per_dmg * (pf + (1 - pf) * (0.5 if data.get("half") else 0.0))
                sign = 1 if (o["side"] in FRIENDLY) != friendly else -1
                v += sign * (dmg_v + pf * cond_v)
            return v

        best_s: tuple[float, str, Square] | None = None
        for q in candidates:
            with _placed(c, q):
                if data.get("target") == "one":
                    for t in foes:
                        rng = data.get("range")
                        if rng is not None and feet_between(c, t) > max(rng, 5):
                            continue
                        v = value_of([t])
                        note = ""
                        if data.get("touch") and data.get("attack") is not None:   # a ray or touch: it must hit
                            kind = "ranged" if (data.get("range") or 0) > 0 else "melee"
                            delta, ac, _n, _d, miss = attack_mods(st, c, t, kind, True)
                            need = max(2, min(20, ac - (data["attack"] + delta)))
                            v *= p_hit(need, miss)
                            note = f" (touch, hits on {need}+)"
                        if best_s is None or v > best_s[0]:
                            best_s = (v, f"{label_} on {t['token']}{note}", q)
                elif data.get("target") == "area" and data.get("area"):
                    shape, ft = data["area"].split()
                    aims: list[tuple[str, list[Square]]] = []
                    if shape == "burst" and data.get("center") == "self":
                        aims.append((f"--at {fmt_pos(*q)}", R.area_cells(st, "burst", int(ft), origin=q)))
                    elif shape == "burst":
                        for t in foes:
                            if data.get("range") is None or feet_between(c, t) <= data["range"]:
                                aims.append((f"--at {fmt_pos(t['x'], t['y'])}", R.area_cells(st, "burst", int(ft), origin=(t["x"], t["y"]))))
                    else:
                        for t in foes:
                            aims.append((f"--toward {fmt_pos(t['x'], t['y'])}", R.area_cells(st, shape, int(ft), frm=c, toward=(t["x"], t["y"]))))
                    for aim, area_sq in aims:
                        hit = [o for o in R.tokens_in(st, area_sq) if o is not c and not o.get("removed") and in_fight(o)]
                        v = value_of(hit)
                        if hit and (best_s is None or v > best_s[0]):
                            names = ", ".join(o["token"] for o in hit)
                            best_s = (v, f"{label_} {aim} (hits {names})", q)
        if best_s and best_s[0] > 0:
            v, text, q = best_s
            keep, prov, note = casting(q, lvl, conc, provokes)
            add("spell", v * keep, 0, q, sorted(set(([] if q == start else provokers(q)) + prov)),
                f"{where(q, one.get(q, 0))}{text}{note}")

    # --- first aid: a dying ally next to it, or one move away (Heal DC 15, a standard action, provokes) ---
    if not move_only and not fear and not (limited and R.has(c, "nauseated")):
        aid_bonus = first_aid_bonus(c)
        aid_chance = max(0.05, min(1.0, (21 - (FIRST_AID_DC - aid_bonus)) / 20))
        for o in [o for o in allies if needs_first_aid(o)][:2]:
            ox, oy = o["x"], o["y"]
            spots = [q for q in one if max(abs(q[0] - ox), abs(q[1] - oy)) <= 1 and q != (ox, oy)]
            if not spots:
                continue

            def aid_risk(q: Square) -> list[str]:
                with _placed(c, q):
                    return sorted(set(([] if q == start else provokers(q)) + _threatened_by(st, c)))
            q = min(spots, key=lambda q: (_aoo_risk(st, c, aid_risk(q)), _incoming(st, c, q, memo), one[q]))
            worth = FIRST_AID_PC if o["side"] == "pc" else FIRST_AID_ALLY
            add("heal", 0, aid_chance * worth, q, aid_risk(q),
                f"{where(q, one[q])}first aid on {o['token']} (dying, {o['hp']} HP; Heal {aid_bonus:+d} vs DC {FIRST_AID_DC}: {aid_chance:.0%})",
                "(`combat_first_aid`)")

    # --- defense: total defense here or on the safest square in one move (+4 AC: ~20% fewer hits) ---
    # Holding back is a wasted turn unless it's in danger, its morale broke, or it's afraid: total
    # defense where no enemy can reach it defends against nothing.
    danger = _incoming(st, c, start, memo) >= 0.25 * max(1, c["hp"]) or bool(_threatened_by(st, c))
    holding_ok = danger or fear or "MORALE BREAKS" in wnote
    IDLE = 1.5

    def defend_idle(sq: Square) -> float:
        return 0.0 if holding_ok and _incoming(st, c, sq, memo) > 0 else IDLE

    if move_only:
        add("defense", 0, 0, start, [], "stay where it is")
    elif not fear:
        add("defense", 0, 0, start, [], "stay, total defense", exposure=0.8, idle=defend_idle(start))
    safest = min(one, key=lambda q: (_incoming(st, c, q, memo), one[q]))
    if safest != start:
        add("defense", 0, 0, safest, provokers(safest), f"{where(safest, one[safest])}"
            + ("to the safest square in one move" if move_only else "total defense (safest square in one move)"),
            exposure=1.0 if move_only else 0.8, idle=0.0 if move_only else defend_idle(safest))
    # --- retreat: withdraw (full-round double move; leaving the first square doesn't provoke) ---
    if fear and two and routes2 and foes:   # a run (×4 speed) would go further; the withdraw is the safe minimum
        head.append("  (it may also run: `move … --as run`, four times its speed, away from the source)")
    if two and routes2 and foes:
        def far(q: Square) -> tuple[float, int]:
            return (_incoming(st, c, q, memo), -min(R.sq_dist(q, (f["x"], f["y"])) for f in foes))
        dest = min(two, key=far)
        if dest != start:
            route = routes2.get(dest, [start, dest])
            prov = path_provokers(st, c, route[1:], {}) if len(route) > 2 else []
            with _placed(c, dest):
                out_of_sight = all(V.concealment(st, V.presumed(f, c), c)[0] >= 50 for f in foes)
            if single:
                prov = provokers(dest)
            add("retreat", 0, 0, dest, prov, (f"move {two[dest]} ft away to " if single else f"withdraw {two[dest]} ft to ")
                + fmt_pos(*dest) + (" (out of their sight)" if out_of_sight else "") + ("" if single else " (full-round)"),
                idle=0.0 if holding_ok else IDLE)
        # toward the map edge, the only place it can flee the battlefield from (house rule)
        here_edge = edge_dist(st, c)
        exit_sq = min(two, key=lambda q: (edge_dist(st, c, q), _incoming(st, c, q, memo)))
        if here_edge > 0 and exit_sq not in (start, dest) and edge_dist(st, c, exit_sq) < here_edge:
            route = routes2.get(exit_sq, [start, exit_sq])
            prov = provokers(exit_sq) if single else (path_provokers(st, c, route[1:], {}) if len(route) > 2 else [])
            at_edge = edge_dist(st, c, exit_sq) == 0
            add("retreat", 0, 0, exit_sq, prov, (f"move {two[exit_sq]} ft to " if single else f"withdraw {two[exit_sq]} ft to ")
                + fmt_pos(*exit_sq) + (" (at the map edge: it can flee from there next turn)" if at_edge
                                       else " (toward the map edge, to flee from there)") + ("" if single else " (full-round)"),
                idle=0.0 if holding_ok else IDLE)
    # --- flee the battlefield (house rule): only from the map edge, where no enemy threatens it; it
    # stands there until its next turn, then it's gone (half the exposure: it won't be back for more) ---
    if foes and not single and edge_dist(st, c) == 0 and not _threatened_by(st, c) and not R.has(c, "fleeing") and action_ok(st, c, "full") is None:
        add("retreat", 0, 0, start, [], f"flee the battlefield (`flee {c['token']}`: full-round; gone at the start of its "
            f"next turn unless a hit or a grapple stops it)", exposure=0.5, idle=0.0 if holding_ok else IDLE)
    plans.sort(key=lambda p: -p[0])
    return head + [f"  {i + 1}. {text}" for i, (_s, text) in enumerate(plans[:limit])]


def tactical_options(st: State, c: Token, area: str | None = None, area_range: int | None = None,
                     only: str | None = None, per_target: int = 3) -> str:
    """The options report (see the section comment)."""
    prof = c.get("profile") or {}
    speed = c.get("speed") or 30
    start = (c["x"], c["y"])
    routes: dict[Square, list[Square]] = {}
    one = reach_map(st, c, speed, routes)
    routes2: dict[Square, list[Square]] = {}
    two = reach_map(st, c, 2 * speed, routes2)
    threat_memo: dict[Square, list[str]] = {}

    def provokers(sq: Square) -> list[str]:
        return path_provokers(st, c, routes.get(sq, [start, sq]), threat_memo)
    here_threat = _threatened_by(st, c)
    out = [f"Options for {c['token']} ({c['name']}) at {fmt_pos(*start)}: speed {speed} ft "
           f"({len(one)} squares in one move, {len(two)} in a double move), reach {c.get('reach', 5)} ft. "
           + (f"Threatened here by {', '.join(here_threat)}: moving away provokes (a 5-foot step doesn't)."
              if here_threat else "Not threatened here.")]
    out.append("Turn plans, ranked by rough expected value [deals + support − AoO risk − ½ of what it takes next round "
               "+ its tactics weights]; PCs without listed attacks count as ~3 a round; pick by its nature and morale, "
               "not just the top line:")
    out += turn_plans(st, c, one, routes, provokers, two, routes2) or ["  (no attack, spell or ability reaches an enemy this turn)"]
    out.append("Details:")
    attacks = prof.get("attacks") or {}
    melee = [(n, w) for n, w in attacks.items() if w.get("type", "melee") == "melee"]
    ranged = [(n, w) for n, w in attacks.items() if w.get("type") == "ranged"]
    full = prof.get("full_attack") or [n for n, w in melee if isinstance(w.get("bonus"), list)]
    foes = [o for o in _foes(st, c) if not only or o["token"] == only][:3]
    for t in foes:
        unseen = V.concealment(st, c, t)[0] >= 50
        line = f"vs {t['token']} ({t['name']}, {feet_between(c, t)} ft away, AC {t.get('ac')}, {t['hp']}/{t['max_hp']} HP)"
        out.append(line + (": it can't see it from here (50% miss chance, has to guess the square)" if unseen else ":"))
        if melee:
            name, w = melee[0]
            rows = []
            for sq, feet in one.items():
                with _placed(c, sq):
                    if not threatens(c, t):
                        continue
                    need, miss, notes = _needs(st, c, t, w, "melee")
                    others = [o for o in _threatened_by(st, c) if o != t["token"]]
                    flank = flanking(st, c, t)
                step = sq == start or (feet == 5 and R.sq_dist(start, sq) == 1)
                provokes = [] if step else provokers(sq)
                act = (("full attack" if full else "attack") + (" after a 5-foot step" if sq != start else " from where it stands")
                       if step else f"attack after moving {feet} ft")
                score = need + (0 if step and full else 3) + 4 * len(provokes) + 2 * len(others) + feet / 30
                rows.append((score, f"    {name} from {fmt_pos(*sq)}: {act}, hits on {need}+"
                                    + (f", {miss}% miss" if miss else "") + (" [flanking]" if flank else "")
                                    + (f"; provokes from {', '.join(provokes)}" if provokes else "")
                                    + (f"; also threatened there by {', '.join(others)}" if others else "")))
            rows.sort()
            out += [r for _, r in rows[:per_target]] or [f"    {name}: can't reach a square threatening it this turn (double move: "
                                                         f"{'yes' if any(_reach_threat(st, c, t, sq) for sq in two) else 'no'})"]
            lanes = []
            for sq, feet in two.items():
                d = 5 * R.sq_dist(start, sq)
                if d < 10:
                    continue
                with _placed(c, sq):
                    if not threatens(c, t):
                        continue
                if charge_problem(st, c, t, sq):
                    continue
                with _placed(c, sq):
                    need, miss, _ = _needs(st, c, t, w, "melee", charge=True)
                lanes.append((need, d, sq, miss))
            if lanes:
                need, d, sq, miss = min(lanes)
                out.append(f"    charge: to {fmt_pos(*sq)} ({d} ft, straight and clear), hits on {need}+ (incl. +2)"
                           + (f", {miss}% miss" if miss else "") + "; −2 AC until its next turn; full-round"
                           + (f"; provokes from {', '.join(here_threat)}" if here_threat else "")
                           + f" (`move {c['token']} {fmt_pos(*sq)} --as charge --target {t['token']}`, then `attack … --charge`)")
        for name, w in ranged:
            rrows = []
            for sq, feet in one.items():
                with _placed(c, sq):
                    need, miss, notes = _needs(st, c, t, w, "ranged")
                    threat = _threatened_by(st, c)
                provokes = sorted(set(threat + ([] if sq == start or feet == 5 else provokers(sq))))
                score = need + miss / 10 + 5 * len(provokes) + feet / 30
                where = "from here" if sq == start else f"from {fmt_pos(*sq)} ({feet} ft)"
                rrows.append((score, sq == start, f"    {name} {where}: hits on {need}+" + (f", {miss}% miss" if miss else "")
                             + (f" ({', '.join(n for n in notes if not n.startswith('target'))})" if notes else "")
                             + (f"; provokes from {', '.join(provokes)}" if provokes else "")))
            rrows.sort()
            here = next((r for r in rrows if r[1]), None)
            best = [r for r in rrows if not r[1]][:2]
            out += [r[2] for r in ([here] if here else []) + [b for b in best if not here or b[0] < here[0]]]
    if area:
        out.append(_area_options(st, c, area, area_range))
    safe = []
    for sq, feet in one.items():
        if sq == start:
            continue
        with _placed(c, sq):
            if any(threatens(o, c) for o in _foes(st, c)):
                continue
            hidden = all(V.hidden_from(st, c, V.presumed(o, c)) for o in _foes(st, c))
            unseen = all(V.concealment(st, V.presumed(o, c), c)[0] >= 50 for o in _foes(st, c))
            covered = all(R.cover(st, o, c) for o in _foes(st, c))
        if hidden or covered:
            safe.append((0 if unseen else 1 if covered else 2, feet, fmt_pos(*sq),
                         "unseen" if unseen else "cover" if covered else "concealed"))
    safe.sort()
    if safe:
        out.append("Out of reach and hidden or in cover (one move): "
                   + ", ".join(f"{p} ({how}, {f} ft)" for _, f, p, how in safe[:5])
                   + (f"; leaving provokes from {', '.join(here_threat)}" if here_threat else ""))
    return "\n".join(out)


def _reach_threat(st: State, c: Token, t: Token, sq: Square) -> bool:
    with _placed(c, sq):
        return threatens(c, t)


def _area_options(st: State, c: Token, area: str, area_range: int | None) -> str:
    """The best placements of an area effect: most enemies, fewest allies."""
    m = re.match(r"^\s*(burst|cone|line)\s+(\d+)\s*$", area)
    if not m:
        raise CombatError('--area must look like "burst 20", "cone 15" or "line 60"')
    shape, size = m.group(1), int(m.group(2))
    friendly = c["side"] in FRIENDLY
    seen: set[frozenset[Square]] = set()
    rows = []
    for y in range(st["h"]):
        for x in range(st["w"]):
            if R.blocks_line(st, x, y):
                continue
            if shape == "burst":
                if area_range is not None and 5 * min(R.sq_dist(cc, (x, y)) for cc in cells(c)) > area_range:
                    continue
                sq_cells = R.area_cells(st, "burst", size, origin=(x, y))
                opt = f'--area "burst {size}" --at {fmt_pos(x, y)}'
            else:
                if (x, y) in cells(c):
                    continue
                sq_cells = R.area_cells(st, shape, size, frm=c, toward=(x, y))
                opt = f'--area "{shape} {size}" --toward {fmt_pos(x, y)}'
            key = frozenset(sq_cells)
            if key in seen:
                continue
            seen.add(key)
            hit = [o for o in R.tokens_in(st, sq_cells) if not o.get("removed") and o["hp"] > 0 and o is not c]
            foes = [o["token"] for o in hit if (o["side"] in FRIENDLY) != friendly]
            allies = [o["token"] for o in hit if (o["side"] in FRIENDLY) == friendly]
            if foes:
                rows.append((-len(foes), len(allies), opt, foes, allies))
    rows.sort(key=lambda r: (r[1] > 0, r[0], r[1]))
    if not rows:
        return f"Area {shape} {size}: no placement reaches an enemy" + (f" within {area_range} ft" if area_range else "")
    return f"Area {shape} {size}:\n" + "\n".join(
        f"    {opt}: hits {', '.join(f)}" + (f" — and allies {', '.join(a)}!" if a else "") for _, _, opt, f, a in rows[:3])


def cmd_options(args: Args, st: State) -> str:
    """The tactical options report for a creature (DM only)."""
    return tactical_options(st, token(st, args.token), args.area, args.range, args.target)


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
    if not getattr(args, "aoo", False) and kind not in ("release", "escape"):
        mark_target(st, a, t, "attack")
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
        held_t = [n for n in wielding(t)]
        if ok:
            if not held_t:
                return f"{who(t)} holds nothing to drop"
            if args.item:
                try:
                    chosen = [find_weapon(t, args.item)]
                except CombatError:
                    chosen = held_t[:1]
            else:
                chosen = held_t[:1]
            drops = held_t if margin >= 10 else chosen   # 10+ over its CMD: both hands
            unarmed = not any(n in wielding(a) for n in weapons(a))
            far = "greater disarm" in _feats(a)
            for n in drops:
                if unarmed and not far and free_hands(a) > 0 and n == drops[0]:   # disarmed with bare hands: it can grab it
                    t["wielding"].remove(n)
                    a.setdefault("carrying", []).append(n)
                    dm.append(f"{a['token']} grabs the {n} (carried)")
                else:
                    dm.append(drop_item(st, t, n, why="is disarmed of"))
            where = " (it lands 15 ft away)" if far else ""
            return f"{who(t)} drops {' and '.join(drops)}{where}"
        if margin <= -10:
            own = next((n for n in wielding(a)), None)
            if own:
                dm.append(drop_item(st, a, own, why="fumbles and drops"))
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


def add_light(st: State, kind: str, at: str | None, on: str | None, toward: str | None = None,
              rounds: int | None = None, magic: int | None = None, radius: int | None = None,
              increased: int | None = None, by: str | None = None) -> str:
    """Add a light source or darkness effect from the catalog (vision.SOURCES), at a square or carried."""
    if kind not in V.SOURCES and radius is None:
        raise CombatError(f"unknown light source '{kind}' (known: {', '.join(V.SOURCES)}); or give --radius/--increased")
    if bool(at) == bool(on):
        raise CombatError("give exactly one of --at SQUARE or --on TOKEN")
    src: dict[str, Any] = dict(V.SOURCES.get(kind, {"radius": radius or 0, "increased": increased or radius or 0,
                                                   "lit": V.NORMAL, "cap": V.NORMAL, "magic": None}))
    for k, v in (("radius", radius), ("increased", increased), ("magic", magic)):
        if v is not None:
            src[k] = v
    L = V.light_state(st)
    n = 1 + max([int(x["id"][1:]) for x in L["sources"] if x["id"][1:].isdigit()] or [0])
    src.update(id=f"l{n}", kind=kind)
    if on:
        token(st, on)
        src["on"] = on
    else:
        src["at"] = list(parse_pos(at or "", st))
    if src.get("cone"):
        if not toward:
            raise CombatError(f"a {kind} shines in a cone: give --toward SQUARE")
        src["toward"] = list(parse_pos(toward, st))
    if rounds:
        src["expires"] = {"round": st.get("round", 1) + rounds, "token": by or st.get("turn") or ""}
    L["sources"].append(src)
    where = f"carried by {on}" if on else f"at {fmt_pos(*src['at'])}"
    if st.get("turn") is not None and not (on and token(st, on).get("hidden")):   # not during setup
        near = f"around {who(token(st, on))}" if on else f"at {fmt_pos(*src['at'])}"
        event(st, f"Darkness falls {near}" if src.get("steps") else f"A {kind} lights up {near}")
    return f"light {src['id']}: {kind} {where}" + (f", {rounds} rounds" if rounds else "")


def cmd_light(args: Args, st: State) -> str:
    """Lighting: ambient level, zones, light sources and darkness effects, and a light map."""
    L = V.light_state(st)
    w = args.what
    if args.action == "ambient":
        if len(w) != 1 or w[0] not in V.LEVELS:
            raise CombatError(f"light ambient LEVEL ({'|'.join(V.LEVELS)})")
        L["ambient"] = w[0]
        event(st, f"The light here is {w[0]}")
        return f"ambient light: {w[0]}"
    if args.action == "add":
        if not w:
            raise CombatError("light add KIND (--at SQUARE | --on TOKEN)")
        return add_light(st, " ".join(w).lower(), args.at, args.on, args.toward, args.rounds, args.magic,
                         args.radius, args.increased)
    if args.action in ("remove", "move"):
        src = next((x for x in L["sources"] if x["id"] in w), None)
        if not src:
            raise CombatError(f"no light source {' '.join(w)} (see `light show`)")
        if args.action == "remove":
            L["sources"].remove(src)
            event(st, f"The {src['kind']} goes out")
            return f"removed {src['id']} ({src['kind']})"
        if args.on:
            token(st, args.on)
            src.pop("at", None)
            src["on"] = args.on
        else:
            cs = V.source_cells(st, src)
            dest = parse_pos(args.at, st) if args.at else (cs[0] if cs else None)
            if dest is None:
                raise CombatError("give --at SQUARE or --on TOKEN")
            src.pop("on", None)
            src["at"] = list(dest)
        if args.toward:
            src["toward"] = list(parse_pos(args.toward, st))
        return f"{src['id']} ({src['kind']}) now " + (f"carried by {src['on']}" if src.get("on") else f"at {fmt_pos(*src['at'])}")
    if args.action == "zone":
        if len(w) != 3 or w[2] not in V.LEVELS + ["ambient"]:
            raise CombatError("light zone FROM TO LEVEL, e.g. light zone A1 C4 dark (or 'ambient' to clear)")
        (x1, y1), (x2, y2) = parse_pos(w[0], st), parse_pos(w[1], st)
        grid = [list(r) for r in (L.get("grid") or ["." * st["w"]] * st["h"])]
        ch = "." if w[2] == "ambient" else {V.DARK: "X", V.DIM: "D", V.NORMAL: "N", V.BRIGHT: "B"}[V.LEVEL_OF[w[2]]]
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for x in range(min(x1, x2), max(x1, x2) + 1):
                grid[y][x] = ch
        L["grid"] = ["".join(r) for r in grid]
        return f"light zone {w[0]}–{w[1]}: {w[2]}"
    # show
    viewer = token(st, args.for_) if args.for_ else None
    chars = "XDNB"
    out = [f"Light ({'as ' + viewer['token'] + ' sees it, ' + V.describe_senses(viewer) if viewer else 'natural'}); "
           f"ambient {L.get('ambient')}"]
    out.append("    " + "".join(f"{chr(ord('A') + i):<3}" for i in range(st["w"])).rstrip())
    for y in range(st["h"]):
        row = []
        for x in range(st["w"]):
            if R.blocks_line(st, x, y):
                row.append("#")
                continue
            if viewer:
                lvl, how = V.seen_level(st, viewer, (x, y))
                row.append("v" if how in ("darkvision", "see in darkness", "blindsight") else chars[lvl])
            else:
                lvl, deep, _ = V.level_at(st, (x, y))
                row.append("S" if deep else chars[lvl])
        out.append(f"{y + 1:>2}  " + "".join(f"{c:<3}" for c in row).rstrip())
    out.append("    X dark  D dim  N normal  B bright" + ("  v seen by darkvision etc." if viewer else "  S supernatural darkness"))
    for src in L["sources"]:
        where = f"carried by {src['on']}" if src.get("on") else f"at {fmt_pos(*src['at'])}"
        out.append(f"  {src['id']} {src['kind']} {where}" + (f" toward {fmt_pos(*src['toward'])}" if src.get("toward") else ""))
    return "\n".join(out)


def cmd_sight(args: Args, st: State) -> str:
    """What a creature sees and how it's seen, where it could hide, and nearby light sources (DM view)."""
    c = token(st, args.token)
    return V.sight_report(st, c, fmt_pos, (c.get("speed") or 30) // 5)


# ---------- prepared encounters ----------
# An encounter file (campaigns/<c>/dm/combat/encounters/<name>.md) holds DM notes plus a
# ```encounter JSON block (library/general/encounter.schema.json). `encounter check` validates it
# at prep time; `setup` builds the whole fight from it in one call at play time.

ENCOUNTER_SCHEMA = PROJECT / "library" / "general" / "encounter.schema.json"


def encounters_dir(campaign: str) -> Path:
    """Where a campaign's prepared encounters live."""
    return PROJECT / "campaigns" / campaign / "dm" / "combat" / "encounters"


def encounter_path(campaign: str, name: str) -> Path:
    """An encounter file by path or by name (the file name without .md).

    Raises:
        CombatError: if there's no such file.
    """
    base = encounters_dir(campaign)
    for c in (Path(name), PROJECT / name, PROJECT / "campaigns" / campaign / name, base / name, base / f"{name}.md"):
        if c.is_file():
            return c.resolve()
    raise CombatError(f"no encounter '{name}' (see `encounter list`)")


def load_encounter(path: Path) -> dict[str, Any]:
    """The ```encounter JSON block of a file."""
    m = re.search(r"```encounter\s*\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S)
    if not m:
        raise CombatError(f"{path.name} has no ```encounter block")
    try:
        enc = json.loads(m.group(1))
    except ValueError as e:
        raise CombatError(f"bad JSON in the encounter block of {path.name}: {e}")
    if not isinstance(enc, dict):
        raise CombatError(f"the encounter block of {path.name} must be a JSON object")
    return enc


def camp_ref(campaign: str, rel: str) -> str:
    """A path from an encounter file, as the project-relative path `add --ref` takes: library/… and
    campaigns/… as they are, everything else relative to the campaign folder."""
    return rel if rel.startswith(("library/", "campaigns/")) else f"campaigns/{campaign}/{rel}"


def pc_sheets(campaign: str) -> list[tuple[str, str, str]]:
    """The campaign's PCs from players/characters/: (sheet ref, name from its '# ' heading, token)."""
    out: list[tuple[str, str, str]] = []
    folder = PROJECT / "campaigns" / campaign / "players" / "characters"
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        if f.name.lower() == "readme.md":
            continue
        m = re.search(r"^#\s+(.+)$", f.read_text(encoding="utf-8"), re.M)
        name = (m.group(1).strip() if m else f.stem.replace("-", " ").title()).split(" (")[0]
        used = {t for _, _, t in out}
        tok = next((ch.upper() for ch in name if ch.isalpha() and ch.upper() not in used), "P")
        out.append((f"campaigns/{campaign}/players/characters/{f.name}", name, tok))
    return out


def plan_encounter(campaign: str, enc: dict[str, Any], inits: dict[str, int] | None = None,
                   place: dict[str, str] | None = None) -> tuple[State | None, list[list[str]], list[str]]:
    """Validate an encounter and turn it into the commands that build it (after `new`).

    Args:
        inits: the PCs' initiative rolls by token; None checks the file without them (prep time).
        place: start squares by token that override the file's (e.g. the PC came from the east).

    Returns:
        (the map's fresh state, the command lines, errors). Nothing is created.
    """
    schema = json.loads(ENCOUNTER_SCHEMA.read_text(encoding="utf-8"))
    errs = R._validate(enc, schema, "encounter", [])
    if errs:
        return None, [], errs
    place = place or {}
    try:
        probe = fresh_state(camp_ref(campaign, enc["map"]) if enc.get("map") else None, enc.get("blank"), enc.get("light"))
    except CombatError as e:
        return None, [], [f"map: {e}"]
    steps: list[list[str]] = []
    system = campaign_system(campaign)

    def square(sq: str, what: str) -> Square | None:
        try:
            return parse_pos(sq, probe)
        except CombatError as e:
            errs.append(f"{what}: {e}")
            return None

    for i, z in enumerate(enc.get("zones") or []):
        if square(z["from"], f"zones[{i}].from") and square(z["to"], f"zones[{i}].to"):
            steps.append(["light", "zone", z["from"], z["to"], z["level"]])

    # every combatant: (token, name, ref, square, side, extra add options)
    entries: list[tuple[str, str, str, str, str, list[str]]] = []
    if enc.get("pcs"):
        for p in enc["pcs"]:
            entries.append((p["token"], p.get("name") or p["token"], camp_ref(campaign, p["ref"]),
                            place.get(p["token"], p["pos"]), "pc", []))
    else:
        sheets = pc_sheets(campaign)
        if not sheets:
            errs.append("no PC sheets in players/characters/ (and no 'pcs' in the encounter)")
        starts = enc.get("pc_start") or []
        for k, (ref, name, tok) in enumerate(sheets):
            pos = place.get(tok) or (starts[k] if k < len(starts) else None)
            if not pos:
                errs.append(f"no start square for {name} ({tok}): add pc_start, or setup --place {tok}=D4")
                continue
            entries.append((tok, name, ref, pos, "pc", []))
    for c in enc["combatants"]:
        n = c.get("count", 1)
        poss = c["pos"] if isinstance(c["pos"], list) else [c["pos"]]
        if len(poss) != n:
            errs.append(f"{c['token']}: count {n} needs {n} squares in pos, got {len(poss)}")
            continue
        extra = ["--init", str(c.get("init", "roll"))]
        extra += ["--hidden"] if c.get("hidden") else []
        extra += ["--hp", str(c["hp"])] if c.get("hp") else []
        extra += ["--cr", c["cr"]] if c.get("cr") else []
        extra += ["--main-dm"] if c.get("dm_plays") else []
        extra += ["--tactics", json.dumps(c["tactics"])] if c.get("tactics") else []
        extra += ["--wielding", ",".join(c["wielding"])] if c.get("wielding") else []
        for k in range(n):
            tok = f"{c['token']}{k + 1}" if n > 1 or not c["token"][-1:].isdigit() else c["token"]
            if n > 1 and len(c["token"]) != 1:
                errs.append(f"{c['token']}: with count, token is a one-letter prefix (g → g1, g2, …)")
                break
            name = f"{c['name']} {k + 1}" if n > 1 else c["name"]
            entries.append((tok, name, camp_ref(campaign, c["ref"]), str(place.get(tok, poss[k])), c.get("side", "enemy"), extra))

    seen: set[str] = set()
    occupied_sq: dict[Square, str] = {}
    for tok, name, ref, pos, side, extra in entries:
        if tok in seen:
            errs.append(f"token {tok} is used twice")
            continue
        seen.add(tok)
        prof = None
        if not (PROJECT / ref).is_file():
            errs.append(f"{tok}: no such file {ref}")
        else:
            try:
                prof = R.load_profile(ref)
                if prof is None:
                    errs.append(f"{tok}: {ref} has no combat-profile block")
            except ValueError as e:
                errs.append(f"{tok}: bad combat-profile block in {ref}: {e}")
            if prof is not None:
                p_errs, _ = R.check_profile(prof, system)
                if side == "pc" and prof.get("kind") != "pc":
                    p_errs.append('a PC profile needs "kind": "pc"')
                errs += [f"{tok} ({ref}): {e}" for e in p_errs]
        at = square(pos, f"{tok} pos")
        if at:
            size = (prof or {}).get("size", 1) if isinstance(prof, dict) else 1
            for cell in cells({"x": at[0], "y": at[1], "size": size}):
                if cost(probe, *cell) is None:
                    errs.append(f"{tok}: {fmt_pos(*cell)} is a wall, pit or off the map")
                elif cell in occupied_sq:
                    errs.append(f"{tok}: {fmt_pos(*cell)} is already taken by {occupied_sq[cell]}")
                else:
                    occupied_sq[cell] = tok
        add = ["add", tok, name, "--pos", pos, "--ref", ref, "--side", side] + extra
        if side == "pc":
            if inits is not None:
                if tok not in inits:
                    errs.append(f"{name} ({tok}) needs the player's initiative roll: setup … --init {tok}=N")
                    continue
                add += ["--init", str(inits[tok])]
        steps.append(add)

    for i, li in enumerate(enc.get("lights") or []):
        kind = li["kind"].lower()
        if kind not in V.SOURCES:
            errs.append(f"lights[{i}]: unknown light source '{li['kind']}' (known: {', '.join(V.SOURCES)})")
            continue
        if bool(li.get("at")) == bool(li.get("on")):
            errs.append(f"lights[{i}]: give exactly one of 'at' or 'on'")
            continue
        if li.get("on") and li["on"] not in seen:
            errs.append(f"lights[{i}]: no combatant '{li['on']}' to carry the {kind}")
        if li.get("at"):
            square(li["at"], f"lights[{i}].at")
        if V.SOURCES[kind].get("cone") and not li.get("toward"):
            errs.append(f"lights[{i}]: a {kind} needs 'toward'")
        steps.append(["light", "add", kind] + [x for k in ("at", "on", "toward") if li.get(k) for x in (f"--{k}", li[k])]
                     + (["--rounds", str(li["rounds"])] if li.get("rounds") else []))
    return probe, steps, errs


def cmd_encounter(args: Args) -> str:
    """List prepared encounters, or check them (all, or the named ones) without creating anything."""
    files = sorted(encounters_dir(args.campaign).glob("*.md")) if args.action == "list" or not args.names else \
        [encounter_path(args.campaign, n) for n in args.names]
    files = [f for f in files if f.name.lower() != "readme.md"]
    if not files:
        return "No prepared encounters in dm/combat/encounters/."
    out = []
    bad = 0
    for f in files:
        rel = f.relative_to(PROJECT / "campaigns" / args.campaign) if f.is_relative_to(PROJECT / "campaigns" / args.campaign) else f
        try:
            enc = load_encounter(f)
        except CombatError as e:
            out.append(f"{rel}: ERROR {e}")
            bad += 1
            continue
        title = enc.get("title") or f.stem
        if args.action == "list":
            n = sum(c.get("count", 1) for c in enc.get("combatants") or [] if isinstance(c, dict))
            out.append(f"{f.stem}: {title} ({n} combatants{', ' + enc['light'] + ' light' if enc.get('light') else ''})")
            continue
        _, _, errs = plan_encounter(args.campaign, enc)
        out.append(f"{rel}: {'OK' if not errs else 'ERRORS'} ({title})")
        out += [f"  {e}" for e in errs]
        bad += bool(errs)
    if args.action == "check" and bad:
        raise CombatError("\n".join(out))
    return "\n".join(out)


def _kv(pairs: list[str] | None, what: str) -> dict[str, str]:
    """Parse ['C=17', 'K=12'] into {'C': '17', 'K': '12'}."""
    out = {}
    for p in pairs or []:
        k, sep, v = p.partition("=")
        if not sep or not k or not v:
            raise CombatError(f"{what} must look like C=17, not {p!r}")
        out[k.strip()] = v.strip()
    return out


def cmd_setup(args: Args) -> str:
    """Build a prepared encounter in one go: map and lighting, every combatant (NPC initiative
    rolled), light sources. Checks everything first, so a broken file creates nothing."""
    path = encounter_path(args.campaign, args.name)
    enc = load_encounter(path)
    try:
        inits = {k: int(v) for k, v in _kv(args.init, "--init").items()}
    except ValueError:
        raise CombatError("--init values must be numbers, e.g. --init C=17")
    probe, steps, errs = plan_encounter(args.campaign, enc, inits, _kv(args.place, "--place"))
    if errs or probe is None:
        raise CombatError(f"{path.name} isn't ready:\n  " + "\n  ".join(errs))
    if state_path(args.campaign).exists() and not args.force:
        raise CombatError("an encounter is already active; 'end' it first or pass --force")
    save(args.campaign, probe)
    rolls = []
    for argv in steps:
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = main(["-c", args.campaign] + argv)
        if rc:
            state_path(args.campaign).unlink(missing_ok=True)   # don't leave a half-built fight
            raise CombatError(f"setup stopped at `{' '.join(argv)}` (nothing was kept): {err.getvalue().strip()}")
        m = re.search(r"initiative (1d20[^→]*→ .*? = -?\d+)", buf.getvalue())
        if m:
            rolls.append(f"{argv[1]}: {m.group(1)}")
    st = load(args.campaign)
    st["encounter"] = {"file": str(path.relative_to(PROJECT)), "title": enc.get("title") or path.stem}
    if enc.get("surprise"):   # true: the encounter's creatures ambush an unaware party; or {"unaware": [...]}
        spec = enc["surprise"].get("unaware", "party") if isinstance(enc["surprise"], dict) else "party"
        st["surprise"] = {"unaware": unaware_tokens(st, spec)}
    save(args.campaign, st)
    first = next_actor(st)
    first_s = f"{first[0]['token']} ({first[0]['name']}{', hidden' if first[0].get('hidden') else ''})" if first else "nobody"
    out = [f"Encounter '{st['encounter']['title']}' is set up ({len(st['tokens'])} combatants, {len(steps)} steps). "
           f"First in initiative: {first_s}. "
           + ("Narrate the opening and the initiative order (only what the PCs know), then stop: the interface "
              "starts the turns right after your reply." if play_mode() else "Start the first turn with `next`."),
           render(st, dm=True)]
    if rolls:
        out.append("NPC initiative: " + "; ".join(rolls))
    for k, label_ in (("tactics", "Tactics"), ("morale", "Morale"), ("exit_ramp", "Exit ramp"), ("notes", "Notes")):
        if enc.get(k):
            out.append(f"{label_} (DM only): {enc[k]}")
    return "\n".join(out)


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
    before = c["hp"]
    c["hp"] = min(c["max_hp"], c["hp"] + delta)
    healed(st, c, before)
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
    nat = None
    if total_reported is None:
        mod = R.ability_mod(c.get("con"))
        total_c, detail, _ = _roll(f"1d20{mod:+d}")
        nat = _natural(detail)
        how = f"1d20{mod:+d} → {detail} = {total_c}"
    else:
        total_c, how = total_reported, f"reported {total_reported}"
    final = total_c + c["hp"]   # hp is negative: the penalty
    if final >= 10 or nat == 20:   # a natural 20 always stabilizes (CRB pg. 190)
        R.add_condition(st, c, "stable")
        c["stable_aided"] = False   # on its own: it still loses HP hourly unless someone helps (first aid)
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


# First aid (library/pf1e/rules/heal-skill.md, CRB pg. 98, Table 8-2): a Heal check, DC 15, a standard
# action that provokes, on a dying creature (negative HP, still losing them; table reading: next to it).
# Success makes it stable with help: no more HP loss. A failure changes nothing and can be retried.
# Taking 10 is impossible in combat. Heal works untrained; a healer's kit adds +2 (the profile's
# skills.heal includes it). A PC's check is the player's roll.
FIRST_AID_DC = 15
FIRST_AID_PC = 8.0     # what stopping a dying PC from bleeding out is worth to the plans (points of expected damage)
FIRST_AID_ALLY = 4.0


def healed(st: State, c: Token, before: int) -> None:
    """After healing: a dying creature cured of even 1 point becomes stable with help (CRB pg. 190);
    at 0 or more HP it isn't dying any more."""
    if c["hp"] > before and before < 0:
        if c["hp"] < 0:
            R.add_condition(st, c, "stable")
            c["stable_aided"] = True
        else:
            R.remove_condition(c, "stable")
            c.pop("stable_aided", None)


def first_aid_bonus(c: Token) -> int:
    """The creature's Heal modifier for first aid (profile skills.heal; untrained +0 if unknown)."""
    return int(((c.get("profile") or {}).get("skills") or {}).get("heal", 0))


def needs_first_aid(c: Token) -> bool:
    """Dying (negative HP, alive) and not yet stable with help: first aid would do something."""
    return c["hp"] < 0 and not is_dead(c) and not c.get("removed") and not (R.has(c, "stable") and c.get("stable_aided", True))


def cmd_first_aid(args: Args, st: State) -> str:
    """A Heal check to stabilize a dying creature next to the healer (a standard action that provokes)."""
    c, t = token(st, args.token), token(st, args.target)
    if not needs_first_aid(t):
        why = ("is dead" if is_dead(t) else "isn't dying" if t["hp"] >= 0 else "is already stable with help")
        raise CombatError(f"{t['token']} {why}: first aid does nothing (nothing was spent)")
    if feet_between(c, t) > 5:
        raise CombatError(f"{t['token']} is {feet_between(c, t)} ft away: first aid needs it next to {c['token']} (move first)")
    if c["side"] == "pc" and args.total is None:
        raise CombatError("first aid is a Heal check, the player's roll: pass --total N (DC 15; no taking 10 in combat)")
    out = []
    if not (args.out_of_turn or args.override):
        spend(st, c, "standard", f"first aid on {t['token']}")
        lines, _ = provoke_aoos(st, c, reason=f"giving first aid to {t['token']}")
        out += lines
        if not can_act(c):
            return "\n".join(out + [f"{c['token']} goes down before finishing the first aid"])
    if args.total is None:
        bonus = first_aid_bonus(c)
        total, detail, _ = _roll(f"1d20{bonus:+d}")
        how = f"Heal 1d20{bonus:+d} → {detail} = {total}"
    else:
        total, how = args.total, f"Heal reported {args.total}"
    ok = total >= FIRST_AID_DC
    if ok:
        R.add_condition(st, t, "stable")
        t["stable_aided"] = True
    out.insert(0, f"{c['token']} gives {t['token']} first aid: {how} vs DC {FIRST_AID_DC}: "
                  + ("success, stable" if ok else "failure, still dying (it can try again)"))
    if not c.get("hidden"):
        event(st, f"{who(c)} gives {who(t)} first aid — " + (f"{who(t)} is stable [{status(t)}]" if ok else "no luck yet"))
    if st.get("turn") == c["token"]:
        out.append(action_status(st, c))
    return "\n".join(out)


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
            event(st, f"{shown} — {'success' if ok else 'failure'}" + ("" if not pending["dmg"] else f": no damage from {pending['name']}"))
        if not ok:
            out += spell_condition(st, c, pending.get("cond"), pending.get("cond_rounds"), pending["name"], pending.get("cond_mods"))
            imm = pending.get("immunity")
            if imm and imm["after"] == "affected":
                out += grant_immunity(st, c, imm, affected=True)
    else:
        event(st, f"{shown} — {'success' if ok else 'failure'}")
    return "\n".join(out)


def rounds_of(rounds: int | str | None) -> int | None:
    """A duration in rounds: a number, or dice rolled now (cause fear's 1d4)."""
    if isinstance(rounds, str):
        return max(1, _roll(rounds)[0])
    return rounds


def spell_condition(st: State, t: Token, cond: str | None, rounds: int | str | None, source: str,
                    mods: dict[str, int] | None = None) -> list[str]:
    """Put a spell's condition on a target that failed its save (or had none). A custom condition
    (evil eye) brings its own modifiers (`cond_mods`). Returns report lines."""
    if not cond:
        return []
    rounds = rounds_of(rounds)
    R.add_condition(st, t, cond, rounds=rounds, mods=mods or None)
    out = [f"  {t['token']}: {cond}" + (f" for {rounds} rounds" if rounds else " (until removed)")]
    if cond.lower() not in R.CONDITIONS and mods is None:
        out.append(f"  NOTE: '{cond}' isn't a known condition, so it's tracked by name only (no automatic effects); "
                   f"known ones: {', '.join(sorted(R.CONDITIONS))}")
    if not t.get("hidden"):
        event(st, f"{source}: {who(t)} is {cond}" + (f" ({rounds} rounds)" if rounds else ""))
    return out


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
    mark_area(st, token(st, args.frm) if args.frm else None, squares)
    out = [f"{args.shape} {args.feet} ft covers {len(squares)} squares; creatures: "
           + (", ".join(label(o) for o in hit) or "none")]
    imm = getattr(args, "immunity", None)
    immune = [o for o in hit if is_immune(st, o, imm)]
    if immune:
        out.append(f"  immune to it right now (unaffected): {', '.join(label(o) for o in immune)}")
        hit = [o for o in hit if o not in immune]
    if getattr(args, "sr", False) and args.frm:   # spell resistance, per creature
        caster, kept = token(st, args.frm), []
        for o in hit:
            blocked, lines = resists(st, caster, o, args, getattr(args, "log_name", None) or args.name or "the spell")
            out += lines
            if not blocked:
                kept.append(o)
        hit = kept
    if not args.save:   # no save: a condition hits everyone in the area
        for o in hit:
            out += spell_condition(st, o, getattr(args, "cond", None), getattr(args, "cond_rounds", None),
                                   args.name or f"the {args.shape}")
            out += grant_immunity(st, o, imm, affected=True)
        return "\n".join(out)
    if args.dc is None:
        raise CombatError("--save needs --dc")
    name = args.name or f"the {args.shape}"
    shown_name = getattr(args, "log_name", None) or name   # what the player's log and questions say
    dmg, detail = _rolled(args, args.dmg) if args.dmg else (0, "no damage")
    out.append(f"{name}: damage {args.dmg} → {detail} = {dmg}")
    if not any(not o.get("hidden") for o in hit):
        event(st, f"{shown_name} hits no one")
    pcs = []
    for o in hit:
        if o["side"] == "pc":
            st.setdefault("pending_saves", {})[o["token"]] = {
                "kind": args.save, "dc": args.dc, "dmg": dmg, "half": args.half, "name": shown_name,
                "cond": getattr(args, "cond", None), "cond_rounds": getattr(args, "cond_rounds", None),
                    "cond_mods": getattr(args, "cond_mods", None), "immunity": imm}
            out += grant_immunity(st, o, imm, affected=False)
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
        if not ok:
            out += spell_condition(st, o, getattr(args, "cond", None), getattr(args, "cond_rounds", None), shown_name, getattr(args, "cond_mods", None))
        out += grant_immunity(st, o, imm, affected=not ok)
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


def cmd_plan(args: Args, st: State) -> str:
    """A combatant's standing orders from the player ("Brenna grapples Dessick"): shown at the top of
    its briefing every step, until cleared. The DM records them; the player decides them."""
    c = token(st, args.token)
    if args.clear:
        c.pop("plan", None)
        return f"{c['token']}: orders cleared"
    if not args.text:
        raise CombatError("give the orders' text, or --clear")
    c["plan"] = args.text.strip()
    return f"{c['token']} ({c['name']}) has orders: {c['plan']}"


def cmd_init(args: Args, st: State) -> str:
    """Change a token's initiative (delay, ready)."""
    token(st, args.token)["init"] = args.value
    return f"{args.token} initiative → {args.value:g}"


def cmd_flee(args: Args, st: State) -> str:
    """Flee the battlefield (house rule, library/pf1e/house-rules/fleeing.md): a full-round action,
    only from the map edge and not while an enemy threatens it. It leaves at the start of its next turn (`next` removes it),
    unless a hit or a grapple stops it first (flight_check). A miss doesn't."""
    c = token(st, args.token)
    if edge_dist(st, c):
        raise CombatError(f"{c['token']} isn't at the map edge ({edge_dist(st, c) * 5} ft away): it can only flee the "
                          f"battlefield from there. Move it to the edge first, then flee on a later turn")
    foes = [o["token"] for o in st["tokens"] if (o["side"] in FRIENDLY) != (c["side"] in FRIENDLY)
            and not o.get("removed") and threatens(o, c)]
    if foes:
        raise CombatError(f"{c['token']} is threatened by {', '.join(foes)}: it can't flee the battlefield from there. "
                          f"Get clear first (a withdraw, `move … --as withdraw`), then flee on a later turn")
    if R.has(c, "fleeing"):
        raise CombatError(f"{c['token']} is already fleeing")
    R.add_condition(st, c, "fleeing")
    if not c.get("hidden"):
        event(st, f"{who(c)} turns to flee the battlefield")
    return (f"{c['token']} flees: gone at the start of its next turn, unless a hit or a grapple stops it first "
            f"(a miss doesn't)")


def edge_dist(st: State, c: Token, at: Square | None = None) -> int:
    """How many squares the creature (at its position, or at `at`) is from the map edge: 0 on it."""
    x, y = at or (c["x"], c["y"])
    return min(x, y, st["w"] - (x + c["size"]), st["h"] - (y + c["size"]))


def flight_check(st: State) -> list[str]:
    """After every command: a fleeing creature that was hit or grappled stops fleeing. Report lines."""
    out = []
    for c in st["tokens"]:
        why = c.pop("flight_stopped", None)
        if not why and R.has(c, "fleeing") and (R.has(c, "grappled") or R.has(c, "pinned")):
            R.remove_condition(c, "fleeing")
            why = "grappled"
        if why:
            out.append(f"  {c['token']} was {why}: its flight is stopped (it stays; it may try again on its turn)")
            if not c.get("hidden"):
                event(st, f"{who(c)} is stopped from fleeing")
    return out


def cmd_flag(args: Args, st: State) -> str:
    """Reveal, hide or remove a token."""
    c = token(st, args.token)
    if args.command == "remove":
        c["removed"] = True
    else:
        if args.command == "hide" and not getattr(args, "force", False):
            seen_by = [p["token"] for p in st["tokens"] if p["side"] == "pc" and not p.get("removed")
                       and p["hp"] >= 0 and not V.hidden_from(st, c, p)]
            if seen_by and st.get("turn") is not None:
                raise CombatError(f"{c['token']} can't hide: {', '.join(seen_by)} sees it clearly (no cover or "
                                  f"concealment). Move it into darkness or cover first, or --force")
        c["hidden"] = args.command == "hide"
        if args.command == "reveal":
            event(st, f"{who(c)} appears!")
    return f"{c['token']}: {args.command}"


def fight_over(st: State) -> str | None:
    """Why the fight is over, or None: no enemy is still in it (hidden ones count as still there;
    fled ones are removed), and no PC or ally is dying (they still roll to stabilize)."""
    foes = [c for c in st["tokens"] if c["side"] not in FRIENDLY]
    if not foes or any(in_fight(c) for c in foes):
        return None
    dying = [c["name"] for c in st["tokens"] if c["side"] in FRIENDLY and not c.get("removed")
             and c["hp"] < 0 and not is_dead(c) and not R.has(c, "stable")]
    if dying:
        return None
    return "no enemy is left standing"


def cmd_end(args: Args, st: State) -> str:
    """End the encounter: summary and XP, PC HP back onto their sheets, the combat log into the session log,
    and archive the state.
    """
    defeated = [c for c in st["tokens"] if c["side"] not in FRIENDLY and (c["hp"] <= 0 or c.get("removed"))]
    xp = sum(XP_BY_CR.get(str(c.get("cr")), 0) for c in defeated)
    out = [f"Encounter over after {st['round']} round(s)."]
    for c in st["tokens"]:
        status = ("fled" if c.get("fled") else "removed") if c.get("removed") else f"HP {c['hp']}/{c['max_hp']}"
        cr = f", CR {c['cr']}" if c.get("cr") else ""
        out.append(f"  {c['token']} {c['name']}: {status}{cr}")
    out.append(f"XP from defeated/removed enemies with CR: {xp} (check removed ones: fled ≠ defeated unless overcome)")
    alone = [c["name"] for c in st["tokens"] if c["side"] in FRIENDLY and c["hp"] < 0 and not is_dead(c)
             and R.has(c, "stable") and c.get("stable_aided") is False]
    if alone:   # stabilized on their own: still losing HP hourly (CRB pg. 190) until someone tends them
        out.append(f"Stable but unaided: {', '.join(alone)}: still at risk (an hourly Con check, 1 HP per failure) "
                   f"until someone gives first aid (Heal DC 15) or any healing.")
    if st.get("ground"):   # dropped and disarmed weapons: still lying where they fell
        names = {t["token"]: t["name"] for t in st["tokens"]}
        out.append("Left on the ground: " + "; ".join(f"{names.get(g['owner'], g['owner'])}'s {g['item']} at {fmt_pos(*g['at'])}"
                                                      for g in st["ground"])
                   + ". The party can pick these up now; anything not recovered is lost (update the sheets).")
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


HP_LINE = re.compile(r"(\*\*HP:\*\*\s*)(-?\d+)(\s*/\s*)(\d+)")


def cmd_sheet_hp(args: Args) -> int:
    """A character's HP outside a fight (healing, rest, a fall, a trap): changes the sheet's HP line
    and logs it in the live session log. In a fight, combat_hp does it (and combat_end writes it back)."""
    camp_dir = PROJECT / "campaigns" / args.campaign
    want = args.character.lower()
    sheets = [p for p in sorted((camp_dir / "players" / "characters").glob("*.md")) if p.name.lower() != "readme.md"]
    hits = [p for p in sheets if want in p.stem or want in p.read_text(encoding="utf-8").splitlines()[0].lower()]
    if len(hits) != 1:
        print(f"combat error: {'several characters match' if hits else 'no character'} {args.character!r} "
              f"(sheets: {', '.join(p.stem for p in sheets)})", file=sys.stderr)
        return 1
    sheet = hits[0]
    st = load(args.campaign) if state_path(args.campaign).exists() else None
    rel = str(sheet.relative_to(PROJECT))
    if st and any((t.get("ref") or "").endswith(rel.split("campaigns/" + args.campaign + "/")[-1]) and not t.get("removed")
                  for t in st.get("tokens", [])):
        print(f"combat error: {sheet.stem} is in the fight: use combat_hp (combat_end writes the HP back to the sheet)", file=sys.stderr)
        return 1
    text = sheet.read_text(encoding="utf-8")
    m = HP_LINE.search(text)
    if not m:
        print(f"combat error: no '**HP:** N / MAX' line on {sheet.name}", file=sys.stderr)
        return 1
    cur, mx = int(m.group(2)), int(m.group(4))
    ch = args.change.strip()
    try:
        new = int(ch[1:]) if ch.startswith("=") else cur + int(ch)
    except ValueError:
        print(f"combat error: the change is +N, -N or =N, not {ch!r}", file=sys.stderr)
        return 1
    new = min(new, mx)
    sheet.write_text(text[:m.start()] + f"{m.group(1)}{new}{m.group(3)}{mx}" + text[m.end():], encoding="utf-8")
    state = ("unconscious and dying unless stable" if new < 0 else "disabled (conscious, a single action)" if new == 0
             else "at full HP" if new == mx else "hurt")
    name = text.splitlines()[0].lstrip("# ").split("—")[0].strip()
    line = f"HP: {name} {cur} → {new}/{mx} ({args.why})"
    logs = sorted((camp_dir / "dm" / "session-log").glob("session-*.md"))
    played = re.search(r"\*\*Sessions played:\*\*\s*(\d+)", (camp_dir / "campaign.md").read_text(encoding="utf-8"))
    live = camp_dir / "dm" / "session-log" / f"session-{(int(played.group(1)) if played else 0) + 1:02d}.md"
    if logs and live.exists():
        log_text = live.read_text(encoding="utf-8")
        lm = re.search(r"^## Log[^\n]*\n(.*?)(?=^## |\Z)", log_text, re.S | re.M)
        if lm:
            body = lm.group(1).rstrip("\n")
            live.write_text(log_text[:lm.start(1)] + body + f"\n- {line}\n\n" + log_text[lm.end(1):], encoding="utf-8")
    print(f"{line}: {state}")
    return 0


XP_LINE = re.compile(r"^- \*\*XP:\*\*[^\n]*\n?", re.M)
XP_TABLE: Path | None = None   # tests point this at their own table (the library's is local data)


def xp_table(campaign: str) -> tuple[str, list[int]]:
    """The campaign's XP track (session zero's "Advancement: … XP track", default medium) and the XP
    needed for levels 2, 3, … from the library's table (library/<system>/rules/xp-and-advancement.md)."""
    zero = PROJECT / "campaigns" / campaign / "players" / "session-zero.md"
    m = re.search(r"\b(slow|medium|fast)\s+XP track", zero.read_text(encoding="utf-8"), re.I) if zero.exists() else None
    track = (m.group(1) if m else "medium").lower()
    table = XP_TABLE or PROJECT / "library" / campaign_system(campaign) / "rules" / "xp-and-advancement.md"
    rows: list[tuple[int, int]] = []
    if table.exists():
        text = table.read_text(encoding="utf-8")
        head = re.search(r"^\|\s*Level\s*\|(.*)$", text, re.M)
        cols = [c.strip().lower() for c in head.group(1).split("|")] if head else []
        if track in cols:
            for lvl, rest in re.findall(r"^\|\s*(\d+)\s*\|(.*)$", text[head.end():] if head else "", re.M):
                cells = [c.strip().replace(",", "") for c in rest.split("|")]
                if cells[cols.index(track)].isdigit():
                    rows.append((int(lvl), int(cells[cols.index(track)])))
    return track, [xp for _lvl, xp in sorted(rows)]


def cmd_sheet_xp(args: Args) -> int:
    """Award XP outside the fight bookkeeping (the close of a session): for each character sheet (or
    the whole party), the sheet's XP line and a changelog line with the session, the reason, the new
    total and HP; it says who can level up. The DM decides the award; this writes it."""
    camp_dir = PROJECT / "campaigns" / args.campaign
    sheets = [p for p in sorted((camp_dir / "players" / "characters").glob("*.md")) if p.name.lower() != "readme.md"]
    if args.characters.lower() not in ("party", "all"):
        wants = [w.strip().lower() for w in args.characters.split(",") if w.strip()]
        picked = []
        for w in wants:
            hits = [p for p in sheets if w in p.stem or w in p.read_text(encoding="utf-8").splitlines()[0].lower()]
            if len(hits) != 1:
                print(f"combat error: {'several characters match' if hits else 'no character'} {w!r} "
                      f"(sheets: {', '.join(p.stem for p in sheets)})", file=sys.stderr)
                return 1
            picked.append(hits[0])
        sheets = picked
    track, needed = xp_table(args.campaign)
    played = re.search(r"\*\*Sessions played:\*\*\s*(\d+)", (camp_dir / "campaign.md").read_text(encoding="utf-8"))
    nn = args.session or (int(played.group(1)) if played else 0) + 1
    out = []
    for sheet in sheets:
        text = sheet.read_text(encoding="utf-8")
        name = text.splitlines()[0].lstrip("# ").split("—")[0].strip()
        old = XP_LINE.search(text)
        if old:
            cur = int(re.search(r"(\d[\d,]*)", old.group(0)[8:]).group(1).replace(",", ""))   # type: ignore[union-attr]
        else:   # first award through the tool: start from the last total in the changelog
            totals = re.findall(r"total (\d[\d,]*)\s*/", text)
            cur = int(totals[-1].replace(",", "")) if totals else 0
        new = cur + args.xp
        lvl_m = re.search(r"\*\*Race / Class / Level:\*\*[^\n]*?(\d+)\s*$", text, re.M)
        level = int(lvl_m.group(1)) if lvl_m else 1
        nxt = needed[level - 1] if needed and level - 1 < len(needed) else None   # needed[0] is level 2
        up = nxt is not None and new >= nxt
        xp_text = f"- **XP:** {new:,} / {nxt:,} ({track} track, level {level + 1} at {nxt:,})" if nxt else f"- **XP:** {new:,}"
        if old:
            text = text[:old.start()] + xp_text + "\n" + text[old.end():]
        else:
            anchor = re.search(r"^- \*\*Race / Class / Level:\*\*[^\n]*\n", text, re.M)
            at = anchor.end() if anchor else len(text.splitlines()[0]) + 1
            text = text[:at] + xp_text + "\n" + text[at:]
        hp = HP_LINE.search(text)
        line = (f"- {datetime.now():%Y-%m-%d}: session {nn} — +{args.xp} XP ({args.why}), total {new:,}"
                + (f"/{nxt:,} toward level {level + 1}" if nxt else "") + (f". HP {hp.group(2)}/{hp.group(4)}" if hp else "")
                + (". CAN LEVEL UP." if up else "."))
        ch = re.search(r"^## Changelog[^\n]*\n", text, re.M)
        if ch:
            nxt_h = re.search(r"^## ", text[ch.end():], re.M)
            end = ch.end() + (nxt_h.start() if nxt_h else len(text) - ch.end())
            text = text[:end].rstrip("\n") + "\n" + line + "\n" + ("\n" + text[end:] if nxt_h else "")
        else:
            text = text.rstrip("\n") + "\n\n## Changelog\n" + line + "\n"
        sheet.write_text(text, encoding="utf-8")
        out.append(f"{name}: +{args.xp} XP → {new:,}" + (f" / {nxt:,}" if nxt else "") + (" — CAN LEVEL UP" if up else ""))
    print("\n".join(out))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the process exit code."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", "--campaign", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    n = sub.add_parser("new"); n.add_argument("mapfile", nargs="?"); n.add_argument("--blank"); n.add_argument("--force", action="store_true")
    n.add_argument("--light", choices=V.LEVELS, help="ambient light (default normal, or the map file's 'ambient:')")
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
    a.add_argument("--main-dm", action="store_true", help="the main DM plays its turns (a boss, a story NPC), not the combat runner")
    a.add_argument("--wielding", help="what it holds at the start, comma-separated (default: the profile's wielding, else its first weapon)")
    a.add_argument("--tactics", help='JSON: preference weights and morale for the turn plans, e.g. \'{"weights": {"ranged": 2}}\'')
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
    bf = sub.add_parser("briefing"); bf.add_argument("token"); bf.add_argument("--round", type=int)
    wl = sub.add_parser("wield"); wl.add_argument("token"); wl.add_argument("weapon")
    wl.add_argument("--drop", help="drop this weapon first (free; it falls to the ground)")
    wl.add_argument("--sheathe", help="sheathe this weapon first (a move action, or rides on a move with BAB +1)")
    pu = sub.add_parser("pickup"); pu.add_argument("token"); pu.add_argument("item")
    dg = sub.add_parser("damage"); dg.add_argument("token"); dg.add_argument("amount", type=int)
    dg.add_argument("--nonlethal", action="store_true")
    ev = sub.add_parser("events"); ev.add_argument("--all", action="store_true")
    s = sub.add_parser("show"); s.add_argument("--dm", action="store_true")
    sub.add_parser("next")
    m = sub.add_parser("move"); m.add_argument("token"); m.add_argument("pos")
    m.add_argument("--step", action="store_true", help="a 5-foot step (no AoO)")
    m.add_argument("--no-aoo", action="store_true", help="don't roll NPC attacks of opportunity")
    sb = sub.add_parser("stabilize"); sb.add_argument("token"); sb.add_argument("--total", type=int)
    sx = sub.add_parser("sheet-xp"); sx.add_argument("characters", help="'party', or names separated by commas")
    sx.add_argument("xp", type=int); sx.add_argument("--why", required=True); sx.add_argument("--session", type=int)
    sh = sub.add_parser("sheet-hp"); sh.add_argument("character"); sh.add_argument("change", help="+N, -N or =N")
    sh.add_argument("--why", required=True)
    fa = sub.add_parser("first-aid"); fa.add_argument("token"); fa.add_argument("target")
    fa.add_argument("--total", type=int, help="a PC healer's Heal check (the player's roll)")
    fa.add_argument("--out-of-turn", action="store_true"); fa.add_argument("--override", action="store_true")
    sv = sub.add_parser("save"); sv.add_argument("token"); sv.add_argument("kind", nargs="?", choices=["fort", "ref", "will"])
    sv.add_argument("--dc", type=int); sv.add_argument("--total", type=int)
    ar = sub.add_parser("area"); ar.add_argument("shape", choices=["burst", "cone", "line"]); ar.add_argument("feet", type=int)
    ar.add_argument("--at"); ar.add_argument("--from", dest="frm"); ar.add_argument("--toward")
    ar.add_argument("--save", choices=["fort", "ref", "will"]); ar.add_argument("--dc", type=int)
    ar.add_argument("--dmg"); ar.add_argument("--half", action="store_true"); ar.add_argument("--name")
    ar.add_argument("--no-slot", action="store_true", help="not a spell/SLA of the caster (e.g. a breath weapon)")
    ar.add_argument("--cond", help="condition on a failed save (or on everyone without a save)")
    ar.add_argument("--cond-rounds", type=int, help="how long the condition lasts, in rounds")
    pf = sub.add_parser("profile"); pf.add_argument("action", choices=["check"]); pf.add_argument("files", nargs="+")
    for nm in ("cast", "sla"):
        cp = sub.add_parser(nm); cp.add_argument("token"); cp.add_argument("spell" if nm == "cast" else "name")
        cp.add_argument("--defensive", action="store_true", help="cast defensively (concentration DC 15 + 2x level)")
        cp.add_argument("--no-provoke", action="store_true", help="it doesn't provoke (e.g. a quickened spell)")
        if nm == "cast":
            cp.add_argument("--level", type=int); cp.add_argument("--class", dest="cls")
            cp.add_argument("--cl", type=int, help="a PC's caster level for the library effect (default: the sheet's caster_level, else 1)")
        cp.add_argument("--area", help='template, e.g. "cone 15", "burst 20", "line 60"')
        cp.add_argument("--at", help="burst center square"); cp.add_argument("--toward", help="cone/line direction square")
        cp.add_argument("--target", help="a single target token")
        cp.add_argument("--save", choices=["fort", "ref", "will"]); cp.add_argument("--dmg")
        cp.add_argument("--half", action="store_true"); cp.add_argument("--dc", type=int, help="override the DC")
        cp.add_argument("--heal", help="healing dice for the --target, e.g. 1d8+3 (cure spells)")
        cp.add_argument("--cond", help="condition on a failed save (or without a save), e.g. asleep, stunned, shaken")
        cp.add_argument("--cond-rounds", type=int, help="how long the condition lasts, in rounds")
        cp.add_argument("--light-at", help="light/darkness spells: the square it's cast on")
        cp.add_argument("--light-on", help="light/darkness spells: the creature/object carrier token")
        cp.add_argument("--rounds", type=int, help="light/darkness spells: duration in rounds (default: the fight)")
        cp.add_argument("--sr-check", type=int, help="a PC's caster level check against spell resistance (the player's d20 + CL)")
        cp.add_argument("--total", type=int, help="a PC's touch spell: the player's touch attack total")
        cp.add_argument("--amount", type=int, help="a PC's spell: the player's rolled damage or healing")
    sub.add_parser("spells").add_argument("token")
    pv = sub.add_parser("provoke"); pv.add_argument("token"); pv.add_argument("--reason", default="provoking")
    pv.add_argument("--no-aoo", action="store_true")
    pl = sub.add_parser("plan"); pl.add_argument("token"); pl.add_argument("text", nargs="?")
    pl.add_argument("--clear", action="store_true")
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
        fp = sub.add_parser(name); fp.add_argument("token")
        if name == "hide":
            fp.add_argument("--force", action="store_true", help="hide even though a PC sees it clearly")
    sub.add_parser("end")
    sub.add_parser("endturn").add_argument("token")
    sub.add_parser("flee", help="flee the battlefield (house rule): full-round, from the map edge, not while threatened").add_argument("token")
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
    mp = sub.add_parser("map"); mp.add_argument("template"); mp.add_argument("--size"); mp.add_argument("--seed", type=int)
    mp.add_argument("--density", default="medium", choices=["sparse", "medium", "dense"])
    mp.add_argument("--time", choices=["day", "dusk", "night", "inside"]); mp.add_argument("--name")
    mp.add_argument("--start", action="store_true", help="begin the encounter on it"); mp.add_argument("--force", action="store_true")
    mp.add_argument("--replace", action="store_true", help="swap it in under the running fight (tokens and turn state kept)")
    mp.add_argument("--width", type=int, help="river: deep water width in squares (2-12)")
    mp.add_argument("--boat", action="store_true", help="river: a flatboat's deck in the water at the crossing")
    tr = sub.add_parser("terrain"); tr.add_argument("paint", nargs="+", help="AREA=TERRAIN, e.g. E5:H9=. C3=W")
    en = sub.add_parser("encounter"); en.add_argument("action", choices=["list", "check"])
    en.add_argument("names", nargs="*", help="check: encounter names or files (default: all)")
    su = sub.add_parser("setup"); su.add_argument("name", help="encounter name (dm/combat/encounters/<name>.md) or file")
    su.add_argument("--init", action="append", help="a PC's initiative roll, e.g. C=17 (repeat per PC)")
    su.add_argument("--place", action="append", help="override a start square, e.g. C=E5")
    su.add_argument("--force", action="store_true", help="replace an active encounter")
    lt = sub.add_parser("light"); lt.add_argument("action", choices=["ambient", "add", "remove", "move", "zone", "show"])
    lt.add_argument("what", nargs="*"); lt.add_argument("--at"); lt.add_argument("--on"); lt.add_argument("--toward")
    lt.add_argument("--rounds", type=int); lt.add_argument("--magic", type=int, help="spell level (magical light)")
    lt.add_argument("--radius", type=int); lt.add_argument("--increased", type=int)
    lt.add_argument("--for", dest="for_", help="show: the light as this creature sees it")
    sub.add_parser("sight").add_argument("token")
    ac_ = sub.add_parser("act"); ac_.add_argument("token"); ac_.add_argument("kind", choices=ACTION_KINDS)
    ac_.add_argument("what", nargs="?", help='e.g. "draw weapon", "stand up", "drink potion", "total defense"')
    ac_.add_argument("--provokes", action="store_true", help="it provokes attacks of opportunity (Table 8-2)")
    ac_.add_argument("--log", help="a line for the player-visible combat log")
    ac_.add_argument("--override", action="store_true", help="don't charge it (a feat or ability)")
    sp_ = sub.add_parser("surprise"); sp_.add_argument("mode", choices=["on", "off"])
    sp_.add_argument("--unaware", help="who was unaware: tokens, comma-separated (or party / enemies)")
    ab = sub.add_parser("ability"); ab.add_argument("token"); ab.add_argument("name")
    ab.add_argument("--target"); ab.add_argument("--at"); ab.add_argument("--toward")
    sub.add_parser("undo", help="take back the player's last command (a corrected roll); NPC rolls stand")
    sub.add_parser("actions").add_argument("token")
    op = sub.add_parser("options"); op.add_argument("token")
    op.add_argument("--area", help='also place an area effect, e.g. "burst 20", "cone 15"'); op.add_argument("--range", type=int, help="burst range in ft")
    op.add_argument("--target", help="only this target")
    m.add_argument("--as", dest="as_", choices=["charge", "withdraw", "run"], help="movement as part of a full-round charge, withdraw or run")
    m.add_argument("--target", help="a charge: whom it charges (the lane must be straight and clear, to the closest square it can attack from)")
    for nm in ("cast", "sla"):
        sub.choices[nm].add_argument("--time", choices=["standard", "full", "round", "swift", "immediate"],
                                     help="casting time (default standard; quickened = swift)")
    for sp in (at, m, mn, ar, ab, wl, pu, sub.choices["cast"], sub.choices["sla"]):
        sp.add_argument("--override", action="store_true", help="don't charge an action (a feat or ability changes the economy)")
    for sp in (at, m, pv, ar, mn, ab, wl, pu, sub.choices["cast"], sub.choices["sla"]):
        sp.add_argument("--out-of-turn", action="store_true",
                        help="the actor isn't the current one: a readied or immediate action, forced movement, setup")
    args = p.parse_args(argv)
    system = campaign_system(args.campaign)
    if system != "pf1e":   # pf1e's catalog is loaded on import
        R.load_conditions(system)

    handlers = {"add": cmd_add, "next": cmd_next, "move": cmd_move, "dist": cmd_dist,
                "threat": cmd_threat, "hp": cmd_hp, "cond": cmd_cond, "init": cmd_init,
                "reveal": cmd_flag, "hide": cmd_flag, "remove": cmd_flag, "end": cmd_end,
                "attack": cmd_attack, "log": cmd_log, "events": cmd_events,
                "ask": cmd_ask, "wield": cmd_wield, "pickup": cmd_pickup, "briefing": cmd_briefing, "damage": cmd_damage, "stabilize": cmd_stabilize, "first-aid": cmd_first_aid, "save": cmd_save, "area": cmd_area,
                "order": cmd_order, "plan": cmd_plan, "terrain": cmd_terrain, "cast": cmd_cast, "sla": cmd_sla, "spells": cmd_spells,
                "provoke": cmd_provoke, "endturn": cmd_endturn, "flee": cmd_flee, "maneuver": cmd_maneuver,
                "light": cmd_light, "sight": cmd_sight, "act": cmd_act, "surprise": cmd_surprise, "ability": cmd_ability,
                "actions": lambda a, st: action_status(st, token(st, a.token)).strip(), "options": cmd_options}
    if args.command == "profile":
        return cmd_profile(args)
    if args.command == "sheet-hp":
        return cmd_sheet_hp(args)
    if args.command == "sheet-xp":
        return cmd_sheet_xp(args)
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
            undo_path(args.campaign).unlink(missing_ok=True)
            print(cmd_new(args))
            return 0
        if args.command == "undo":
            print(cmd_undo(args))
            return 0
        if args.command == "encounter":
            print(cmd_encounter(args))
            return 0
        if args.command == "map":
            print(cmd_map(args))
            return 0
        if args.command == "setup":
            print(cmd_setup(args))
            return 0
        st = load(args.campaign)
        if args.command == "next" and os.environ.get("CLAUDE_DM_MODE") == "play":
            raise CombatError("you ARE in the player interface (web.py), and it advances the turns itself "
                              "when the player presses Next (or says 'next'). Don't run `next`: resolve only the actor "
                              "the current [Combat step] names, or, outside a step, tell the player whose turn it is "
                              "and stop")
        check_actor(args, st)
        if args.command == "show":
            print(render(st, dm=args.dm))
            return 0
        before = json.dumps(st)   # for `undo` (the player's input only)
        if args.command not in ("ask", "dist", "threat", "events", "sight", "actions", "options"):
            st.pop("awaiting", None)   # any real change answers an open question
        actor_tok = getattr(args, ACTOR_ARG.get(args.command, "") or "_", None)
        actor = next((t for t in st["tokens"] if t["token"] == actor_tok), None)
        cost = charge_action(st, args, actor) if actor and st.get("turn") == actor["token"] else None
        if cost and actor:
            why = action_ok(st, actor, cost)
            if why:
                raise CombatError(f"{actor['token']} can't do that now ({'an attack' if cost == 'attack' else 'a ' + cost + ' action'}): "
                                  f"{why}. If a feat or ability allows it, add --override")
        result = handlers[args.command](args, st)
        if cost and actor:
            what = {"attack": f"attack {getattr(args, 'target', '')}", "flee": "flee the battlefield", "maneuver": f"{getattr(args, 'kind', '')} {getattr(args, 'target', '')}",
                    "cast": f"cast {getattr(args, 'spell', '')}", "sla": f"use {getattr(args, 'name', '')}",
                    "area": "area effect"}.get(args.command, args.command)
            record_action(st, actor, cost, what)
        if actor and st.get("turn") == actor["token"] and args.command in ("attack", "maneuver", "cast", "sla", "area", "move", "ability"):
            result += "\n" + action_status(st, actor)
        ended = clean_grapples(st) + reveal_observed(st) + flight_check(st)
        if ended:
            result += "\n" + "\n".join(ended)
        if args.command != "end":
            if args.command in UNDOABLE:
                remember_undo(args, st, before)
            elif args.command not in READ_ONLY:   # anything else moves on: no undoing past it
                undo_path(args.campaign).unlink(missing_ok=True)
            save(args.campaign, st)
        print(result)
    except CombatError as e:
        print(f"combat error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
