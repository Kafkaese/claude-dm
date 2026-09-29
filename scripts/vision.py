"""vision: light levels and what creatures can see (PF1e), for combat.py.

Rules: library/pf1e/rules/vision-and-light.md (Core Rulebook "Vision and Light", the light and
darkness spells, the senses in the universal monster rules). Table rulings (session of 2026-09-29):
  - low-light vision doubles the radii of light SOURCES only; ambient dim light (moonlight) stays dim
  - visibility is judged from the target's square(s); a lit target is seen from the dark
  - a darkness spell switches off nonmagical light in its area (the Paizo blog/FAQ procedure),
    and magical light only works there if its spell level is higher
  - light sensitivity applies in any bright light
Walls block light (a source lights a square only with a clear line to it).

Light levels: 0 dark, 1 dim, 2 normal, 3 bright; "deep" marks supernatural darkness (deeper
darkness), where darkvision doesn't work.
"""
from __future__ import annotations

import json
import math
from typing import Any

import combat_rules as R

Token = R.Token
State = R.State
Square = R.Square

DARK, DIM, NORMAL, BRIGHT = 0, 1, 2, 3
LEVELS = ["dark", "dim", "normal", "bright"]
LEVEL_OF = {n: i for i, n in enumerate(LEVELS)}
GRID_CHARS = {"X": DARK, "D": DIM, "N": NORMAL, "B": BRIGHT}   # light zones in map files; '.' = ambient

# Light sources (CRB Table 7-10 and the spells). radius: the lit radius, where the light is at
# least `lit`; increased: the outer radius of the band that raises the light one step, up to
# `cap`. magic: spell level (None = nonmagical; matters inside darkness spells). Darkness spells
# have `steps` (how many steps they lower the light) instead.
SOURCES: dict[str, dict[str, Any]] = {
    "candle": {"radius": 0, "increased": 5, "lit": DIM, "cap": DIM, "magic": None},
    "torch": {"radius": 20, "increased": 40, "lit": NORMAL, "cap": NORMAL, "magic": None},
    "lamp": {"radius": 15, "increased": 30, "lit": NORMAL, "cap": NORMAL, "magic": None},
    "hooded lantern": {"radius": 30, "increased": 60, "lit": NORMAL, "cap": NORMAL, "magic": None},
    "bullseye lantern": {"radius": 60, "increased": 120, "lit": NORMAL, "cap": NORMAL, "magic": None, "cone": True},
    "sunrod": {"radius": 30, "increased": 60, "lit": NORMAL, "cap": NORMAL, "magic": None},
    "everburning torch": {"radius": 20, "increased": 40, "lit": NORMAL, "cap": NORMAL, "magic": 2},
    "light": {"radius": 20, "increased": 40, "lit": NORMAL, "cap": NORMAL, "magic": 0},
    "dancing lights": {"radius": 20, "increased": 40, "lit": NORMAL, "cap": NORMAL, "magic": 0},
    "continual flame": {"radius": 20, "increased": 40, "lit": NORMAL, "cap": NORMAL, "magic": 2},
    "daylight": {"radius": 60, "increased": 120, "lit": BRIGHT, "cap": BRIGHT, "magic": 3, "daylight": True},
    "darkness": {"radius": 20, "steps": 1, "magic": 2},
    "deeper darkness": {"radius": 60, "steps": 2, "magic": 3},
}


# ---------- state ----------

def light_state(st: State) -> dict[str, Any]:
    """The encounter's lighting: ambient level, optional zone grid, and sources."""
    return st.setdefault("light", {"ambient": "normal", "grid": None, "sources": []})


def has_lighting(st: State) -> bool:
    """Whether the DM set up anything but plain normal light."""
    L = st.get("light") or {}
    return bool(L) and (L.get("ambient") != "normal" or bool(L.get("grid")) or bool(L.get("sources")))


def senses(c: Token) -> dict[str, Any]:
    """The creature's senses from its profile (darkvision, low_light, see_in_darkness, blindsight, …)."""
    return (c.get("profile") or {}).get("senses") or {}


def describe_senses(c: Token) -> str:
    """e.g. 'darkvision 60 ft, low-light vision', or 'normal vision'."""
    s = senses(c)
    out = []
    for k, label in (("darkvision", "darkvision"), ("blindsight", "blindsight"), ("blindsense", "blindsense"),
                     ("tremorsense", "tremorsense")):
        if s.get(k):
            out.append(f"{label} {s[k]} ft")
    if s.get("low_light"):
        out.append("low-light vision")
    if s.get("see_in_darkness"):
        out.append("see in darkness")
    if s.get("scent"):
        out.append("scent")
    if s.get("light_blindness"):
        out.append("light blindness")
    elif s.get("light_sensitivity"):
        out.append("light sensitivity")
    return ", ".join(out) or "normal vision"


def _token(st: State, tok: str) -> Token | None:
    return next((c for c in st["tokens"] if c["token"] == tok), None)


def source_cells(st: State, s: dict[str, Any]) -> list[Square]:
    """Where a source is: its square, or its carrier's squares."""
    if s.get("on"):
        c = _token(st, s["on"])
        if c:
            return R.cells(c)
    return [tuple(s["at"])] if s.get("at") else []


def _source_point(st: State, s: dict[str, Any]) -> tuple[float, float] | None:
    cs = source_cells(st, s)
    if not cs:
        return None
    xs, ys = [c[0] for c in cs], [c[1] for c in cs]
    return (min(xs) + max(xs) + 1) / 2, (min(ys) + max(ys) + 1) / 2


# ---------- geometry ----------

def _clear(st: State, p: tuple[float, float], q: tuple[float, float], ends: set[Square]) -> bool:
    """Whether the segment p→q passes no wall (squares in `ends` don't count)."""
    for cell in R.segment_cells(p, q, 0.2):
        if cell in ends:
            continue
        if R.blocks_line(st, *cell):
            return False
    return True


def _in_cone(st: State, s: dict[str, Any], q: Square) -> bool:
    if not s.get("toward"):
        return True
    p = _source_point(st, s)
    if p is None:
        return False
    tx, ty = s["toward"][0] + 0.5, s["toward"][1] + 0.5
    qx, qy = q[0] + 0.5, q[1] + 0.5
    if (qx, qy) == p or math.dist((qx, qy), p) < 0.8:
        return True
    a1 = math.atan2(ty - p[1], tx - p[0])
    a2 = math.atan2(qy - p[1], qx - p[0])
    d = abs((a2 - a1 + math.pi) % (2 * math.pi) - math.pi)
    return d <= math.pi / 4 + 1e-9


def _reaches(st: State, s: dict[str, Any], q: Square, radius_ft: float) -> bool:
    """Whether the source reaches square q within radius_ft (distance, walls, cone)."""
    cs = source_cells(st, s)
    if not cs:
        return False
    if 5 * min(R.sq_dist(c, q) for c in cs) > radius_ft:
        return False
    if q in cs:
        return True
    p = _source_point(st, s)
    assert p is not None
    return _clear(st, p, (q[0] + 0.5, q[1] + 0.5), set(cs) | {q}) and _in_cone(st, s, q)


# ---------- light levels ----------

_cache: dict[str, Any] = {}


def _key(st: State) -> str:
    L = st.get("light") or {}
    carriers = {s["on"]: [(c["x"], c["y"]) for c in st["tokens"] if c["token"] == s["on"]]
                for s in L.get("sources", []) if s.get("on")}
    return json.dumps([L, carriers, st["grid"]], sort_keys=True, default=str)


def base_level(st: State, q: Square) -> int:
    """Ambient light, or the map's light zone at q."""
    L = light_state(st)
    grid = L.get("grid")
    if grid and q[1] < len(grid) and q[0] < len(grid[q[1]]) and grid[q[1]][q[0]] in GRID_CHARS:
        return GRID_CHARS[grid[q[1]][q[0]]]
    return LEVEL_OF.get(L.get("ambient", "normal"), NORMAL)


def level_at(st: State, q: Square, mult: int = 1) -> tuple[int, bool, list[str]]:
    """The light at square q: (level, supernatural darkness, what shapes it). `mult` doubles light
    source radii for a low-light viewer (it doesn't change the world, only what that viewer sees)."""
    ck = f"{mult}|{q}|{_key(st)}"
    if ck in _cache:
        return _cache[ck]
    if len(_cache) > 20000:
        _cache.clear()
    base = base_level(st, q)
    why = []
    srcs = [s for s in light_state(st).get("sources", []) if source_cells(st, s)]
    darks = [s for s in srcs if s.get("steps") and _reaches(st, s, q, s["radius"])]
    lights = [s for s in srcs if not s.get("steps")]
    days = [s for s in lights if s.get("daylight") and _reaches(st, s, q, s["increased"] * mult)]
    lvl, deep = base, False
    if darks and days:   # daylight and magical darkness negate each other where they overlap
        lights = [s for s in lights if not s.get("daylight")]
        darks = []
        why.append("daylight and darkness cancel")
    if darks:
        dlev = max(s.get("magic") or 0 for s in darks)
        steps = max(s["steps"] for s in darks)
        if steps >= 2:   # deeper darkness: darkvision can't see within it at all
            lvl, deep = (base - 2 if base >= NORMAL else DARK), True
        else:
            lvl = max(DARK, base - 1)
        why.append(", ".join(sorted({s["kind"] for s in darks})))
        lights = [s for s in lights if s.get("magic") is not None and s["magic"] > dlev]
    best = lvl
    for s in lights:
        if _reaches(st, s, q, s["radius"] * mult) and s["radius"] > 0:
            got = max(lvl, s["lit"])
        elif _reaches(st, s, q, s["increased"] * mult):
            got = max(lvl, min(lvl + 1, s["cap"]))
        else:
            continue
        if got > lvl:
            why.append(f"{s['kind']} {s['id']}")
        best = max(best, got)
    if best > lvl:
        deep = False
    res = (best, deep, why)
    _cache[ck] = res
    return res


def natural(st: State, q: Square) -> str:
    """The light at q as a word, e.g. 'dim', 'dark (supernatural)'."""
    lvl, deep, _ = level_at(st, q)
    return LEVELS[lvl] + (" (supernatural)" if deep else "")


def seen_level(st: State, viewer: Token, q: Square) -> tuple[int, str]:
    """How well `viewer` sees square q: (effective level, how). Darkvision, see in darkness and
    blindsight make a dark square count as normal for concealment; low-light vision doubles source radii."""
    s = senses(viewer)
    mult = 2 if s.get("low_light") else 1
    lvl, deep, _ = level_at(st, q, mult)
    d = 5 * min(R.sq_dist(c, q) for c in R.cells(viewer))
    if s.get("blindsight") and d <= s["blindsight"]:
        return max(lvl, NORMAL), "blindsight" if lvl < NORMAL else ""
    if lvl < NORMAL:
        if s.get("see_in_darkness"):
            return NORMAL, "see in darkness"
        if s.get("darkvision") and d <= s["darkvision"] and not deep:
            return NORMAL, "darkvision"
    if mult == 2 and lvl > level_at(st, q)[0]:
        return lvl, "low-light vision"
    return lvl, ""


def has_line(st: State, a: Token, t: Token) -> bool:
    """Whether any corner-to-corner line from a to t is free of walls (no total cover)."""
    a_cells, t_cells = set(R.cells(a)), set(R.cells(t))
    for pa in R.corners(a):
        for pt in R.corners(t):
            if _clear(st, pa, pt, a_cells | t_cells):
                return True
    return False


def concealment(st: State, viewer: Token, target: Token) -> tuple[int, str]:
    """Miss chance (0, 20, 50) the lighting gives `target` against `viewer`, judged from the target's
    best-lit square, and why. No line of sight at all also counts as 50 (the DM handles total cover)."""
    if not has_line(st, viewer, target):
        return 50, "no line of sight"
    best, how = -1, ""
    for q in R.cells(target):
        lvl, h = seen_level(st, viewer, q)
        if lvl > best:
            best, how = lvl, h
    if best >= NORMAL:
        return 0, how
    return (20, "dim light") if best == DIM else (50, "darkness")


def can_see(st: State, viewer: Token, target: Token) -> bool:
    """Whether the viewer can see the target at all (no total concealment from light or walls)."""
    return concealment(st, viewer, target)[0] < 50 and not R.has(target, "invisible")


def enemies(st: State, c: Token) -> list[Token]:
    """Active creatures on the other side."""
    return [o for o in st["tokens"] if not o.get("removed") and o["hp"] > 0
            and (o["side"] in R.FRIENDLY) != (c["side"] in R.FRIENDLY)]


def hidden_from(st: State, c: Token, o: Token) -> bool:
    """Whether `c` could stay hidden from observer `o`: concealment, cover or no line (Stealth needs one)."""
    return concealment(st, o, c)[0] > 0 or R.cover(st, o, c) or R.has(c, "invisible")


# ---------- reports ----------

def sight_report(st: State, c: Token, fmt_pos: Any, speed_squares: int) -> str:
    """The DM's tactical view for one creature: what it sees, how it's seen, where it could hide,
    and light sources nearby."""
    here = (c["x"], c["y"])
    lvl, how = seen_level(st, c, here)
    out = [f"{c['token']} ({c['name']}) at {fmt_pos(*here)}, {describe_senses(c)}; light here: {natural(st, here)}"]
    foes = enemies(st, c)
    for o in foes:
        miss, why = concealment(st, c, o)
        seen = "can't see" if miss >= 50 else f"sees with {miss}% concealment ({why})" if miss else "sees clearly"
        back, bwhy = concealment(st, o, c)
        them = ("can't see it" if back >= 50 else f"sees it with {back}% concealment ({bwhy})" if back
                else "sees it clearly")
        if R.cover(st, o, c) and back < 50:
            them += " (it has cover)"
        out.append(f"  vs {o['token']} ({o['name']}, {describe_senses(o)}): {seen}; {o['token']} {them}")
    if foes:
        hide = all(hidden_from(st, c, o) for o in foes)
        out.append(f"  can hide where it stands: {'yes' if hide else 'no (observed in the open)'}")
        spots = []
        for y in range(st["h"]):
            for x in range(st["w"]):
                if (x, y) == here or R.sq_dist(here, (x, y)) > speed_squares:
                    continue
                probe = dict(c, x=x, y=y)
                if any(R.blocks_line(st, cx, cy) or st["grid"][cy][cx] == "_" for cx, cy in R.cells(probe)):
                    continue
                if any(o is not c and not o.get("removed") and set(R.cells(o)) & set(R.cells(probe)) for o in st["tokens"]):
                    continue
                if all(hidden_from(st, probe, o) for o in foes):
                    total = all(concealment(st, o, probe)[0] >= 50 for o in foes)
                    spots.append((0 if total else 1, R.sq_dist(here, (x, y)), fmt_pos(x, y), total))
        spots.sort()
        if spots:
            out.append("  hiding spots within its speed: " + ", ".join(
                f"{p}{' (unseen)' if total else ' (concealed)'}" for _, _, p, total in spots[:8]))
    near = []
    for s in light_state(st).get("sources", []):
        cs = source_cells(st, s)
        if not cs:
            continue
        d = 5 * min(R.sq_dist(a, b) for a in R.cells(c) for b in cs)
        if d <= 30:
            where = f"carried by {s['on']}" if s.get("on") else f"at {fmt_pos(*s['at'])}"
            near.append(f"{s['id']} {s['kind']} {where} ({d} ft)")
    if near:
        out.append("  light sources within 30 ft: " + "; ".join(near))
    return "\n".join(out)


def player_view(st: State, pc: Token | None) -> dict[str, Any]:
    """Per-square lighting for the map, from the PC's perspective: natural level, the level the PC
    effectively sees, how (darkvision, …), magical darkness, and visible light sources."""
    rows = []
    for y in range(st["h"]):
        row = []
        for x in range(st["w"]):
            lvl, deep, why = level_at(st, (x, y))
            eff, how = seen_level(st, pc, (x, y)) if pc else (lvl, "")
            magic = any(s.get("steps") and _reaches(st, s, (x, y), s["radius"])
                        for s in light_state(st).get("sources", []))
            row.append({"n": lvl, "e": eff, "how": how, "deep": deep, "magic": magic, "why": why})
        rows.append(row)
    return {"ambient": light_state(st).get("ambient", "normal"), "squares": rows}
