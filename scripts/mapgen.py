"""mapgen: battle maps for combat.py, generated from templates that fit the scene.

A spontaneous fight still needs a map that makes sense for where it happens: a roadside ambush has
trees and brush along the road, with the ambushers in cover. Each template builds a seeded,
reproducible grid in combat.py's map characters (see `combat.py -h`, "Map files"), plus:
  - party:  where the party plausibly is when the fight starts (on the road, at the door, …)
  - ambush: squares near that with cover or concealment, ranked, for creatures lying in wait
  - lights: light sources that belong to the scene (a campfire, the hearth, lanterns)
  - notes:  what the map shows, in a line or two

Templates: forest-road, forest, clearing, field, river, village, tavern, cave, ruins, camp, swamp.
Options: size (WxH, at most 26 wide), seed, density (sparse, medium, dense: the CRB forest table),
time (day, dusk, night: the outdoor ambient light).
"""
from __future__ import annotations

import random
from typing import Any, Callable

Grid = list[list[str]]
Square = tuple[int, int]

# CRB pg. 425 forest table: chance per square of a typical tree, a massive tree, light and heavy undergrowth
FOREST = {"sparse": (0.50, 0.00, 0.50, 0.00), "medium": (0.70, 0.10, 0.70, 0.20), "dense": (0.80, 0.20, 0.50, 0.50)}
# scaled down for a playable battle map (a literal 70% trees makes every square a tree); the ratios stay
MAP_SCALE = 0.45
TIME_LIGHT = {"day": "normal", "dusk": "dim", "night": "dark"}
PASSABLE = set('.+=^~T"&Y-m')
COVERING = {"Y": 3, "&": 3, '"': 2, "T": 2}   # how well a square hides or shelters a creature in it


class MapError(ValueError):
    """A template or option that doesn't exist; the message lists the valid ones."""


def blank(w: int, h: int, ch: str = ".") -> Grid:
    return [[ch] * w for _ in range(h)]


def inside(g: Grid, x: int, y: int) -> bool:
    return 0 <= y < len(g) and 0 <= x < len(g[0])


def put(g: Grid, x: int, y: int, ch: str) -> None:
    if inside(g, x, y):
        g[y][x] = ch


def rect(g: Grid, x0: int, y0: int, x1: int, y1: int, ch: str, fill: bool = True) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if fill or y in (y0, y1) or x in (x0, x1):
                put(g, x, y, ch)


def vegetation(g: Grid, rng: random.Random, density: str, keep: set[Square] | frozenset[Square] = frozenset(), scale: float = MAP_SCALE) -> None:
    """Forest per the CRB table (scaled), on every floor square not in `keep`."""
    tree, massive, light, heavy = (p * scale for p in FOREST[density])
    for y, row in enumerate(g):
        for x, ch in enumerate(row):
            if ch != "." or (x, y) in keep:
                continue
            if rng.random() < massive:
                g[y][x] = "O"
                continue
            t, hv, lt = rng.random() < tree, rng.random() < heavy, rng.random() < light
            g[y][x] = "&" if hv else ("Y" if t and lt else "T" if t else '"' if lt else ".")


def wander(rng: random.Random, start: int, length: int, lo: int, hi: int, drift: float = 0.35) -> list[int]:
    """A gently meandering line: one offset per step, kept within [lo, hi]."""
    out, v = [], start
    for _ in range(length):
        out.append(v)
        if rng.random() < drift:
            v = max(lo, min(hi, v + rng.choice((-1, 1))))
    return out


def blob(g: Grid, rng: random.Random, cx: float, cy: float, r: float, ch: str, ragged: float = 0.35) -> list[Square]:
    """An irregular round patch."""
    out = []
    for y in range(int(cy - r - 1), int(cy + r + 2)):
        for x in range(int(cx - r - 1), int(cx + r + 2)):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if inside(g, x, y) and d <= r + rng.uniform(-ragged, ragged) * r:
                g[y][x] = ch
                out.append((x, y))
    return out


def scatter(g: Grid, rng: random.Random, ch: str, n: int, on: str = ".", avoid: set[Square] | frozenset[Square] = frozenset()) -> None:
    cand = [(x, y) for y, row in enumerate(g) for x, c in enumerate(row) if c == on and (x, y) not in avoid]
    for x, y in rng.sample(cand, min(n, len(cand))):
        g[y][x] = ch


# ---------- templates: each returns (party squares, path squares, lights, notes) ----------

Built = tuple[list[Square], set[Square], list[dict[str, Any]], list[str]]


def t_forest_road(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    ys = wander(rng, h // 2, w, 3, h - 5)
    road = {(x, y + k) for x, y in enumerate(ys) for k in range(2)}
    verge = {(x, y + k) for x, y in enumerate(ys) for k in (-1, 2)}
    vegetation(g, rng, density, keep=road | verge)
    for x, y in verge:   # the brush along a road: undergrowth and the odd tree, no massive trunks on the shoulder
        if inside(g, x, y):
            g[y][x] = rng.choice(('"', '"', ".", "Y", "."))
    for _ in range(rng.randint(1, 2)):   # a fallen log or a low stone wall near the road
        x0 = rng.randint(2, w - 6)
        side = rng.choice((-3, 4))
        for x in range(x0, x0 + rng.randint(2, 4)):
            put(g, x, ys[min(x, w - 1)] + side, "-")
    party = [(1, ys[1]), (1, ys[1] + 1), (2, ys[2]), (2, ys[2] + 1)]
    return party, road, [], [f"A road runs west to east through {density} forest, with brush along both verges."]


def t_forest(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    keep: set[Square] = set()
    if rng.random() < 0.5:   # a stream
        xs = wander(rng, w // 2, h, 3, w - 4)
        for y, x in enumerate(xs):
            put(g, x, y, "~")
            keep.add((x, y))
    vegetation(g, rng, density, keep=keep)
    party = [(2, h // 2), (2, h // 2 + 1), (3, h // 2)]
    for x, y in party:
        g[y][x] = "."
    return party, set(party), [], [f"{density.capitalize()} forest" + (", a shallow stream across it." if keep else ".")]


def t_clearing(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    open_ = set(blob(g, rng, w / 2, h / 2, min(w, h) / 3.2, ".", 0.25))
    vegetation(g, rng, density, keep=open_)
    for x, y in rng.sample(sorted(open_), max(1, len(open_) // 30)):   # a stump or boulder in the open
        g[y][x] = rng.choice(("O", "T"))
    party = [(int(w / 2) - 1, int(h / 2)), (int(w / 2), int(h / 2)), (int(w / 2) - 1, int(h / 2) + 1)]
    for x, y in party:
        g[y][x] = "."
    return party, open_, [], ["A clearing in the forest, ringed by trees and brush."]


def t_field(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    ys = wander(rng, h // 2, w, 3, h - 4, 0.2)
    lane = {(x, y) for x, y in enumerate(ys)}
    for y in range(h):
        for x in range(w):
            if (x, y) not in lane and rng.random() < 0.75:
                g[y][x] = '"'   # crops or tall grass
    for _ in range(rng.randint(1, 3)):   # hedgerows and fences between the plots
        if rng.random() < 0.5:
            x = rng.randint(3, w - 4)
            for y in range(rng.randint(0, 3), h - rng.randint(0, 3)):
                if (x, y) not in lane:
                    put(g, x, y, "-")
        else:
            y = rng.randint(1, h - 2)
            for x in range(rng.randint(0, 4), w - rng.randint(0, 4)):
                if (x, y) not in lane:
                    put(g, x, y, "-")
    scatter(g, rng, "T", rng.randint(2, 5), on='"')
    if rng.random() < 0.5:   # a farmhouse
        x0, y0 = rng.randint(2, w - 9), rng.choice((1, h - 6))
        rect(g, x0, y0, x0 + 5, y0 + 4, "#", fill=False)
        rect(g, x0 + 1, y0 + 1, x0 + 4, y0 + 3, ".")
        put(g, x0 + 2, y0 + (4 if y0 == 1 else 0), "+")
    party = [(1, ys[1]), (2, ys[2]), (1, ys[1] + 1)]
    for x, y in party:
        put(g, x, y, ".")
    return party, lane, [], ["Farmland: crops and tall grass, hedgerows and fences, a cart lane through it."]


def t_river(g: Grid, rng: random.Random, density: str, opts: dict[str, Any] | None = None) -> Built:
    """A river north to south with a bridge or ford. Options: width (2-12 squares of deep water),
    boat (a flatboat's deck in the water at the crossing: under the bridge, or by the ford)."""
    opts = opts or {}
    w, h = len(g[0]), len(g)
    width = int(opts.get("width") or rng.randint(2, 3))
    if not 2 <= width <= min(12, w - 6):
        raise MapError(f"river width must be 2-{min(12, w - 6)} squares on a map {w} wide")
    xs = wander(rng, max(3, w // 2 - width // 2), h, 3, max(3, w - width - 3), 0.3)
    river = {(x + k, y) for y, x in enumerate(xs) for k in range(width)}
    for x, y in river:
        g[y][x] = "W"
    for y, x in enumerate(xs):   # shallow banks
        put(g, x - 1, y, "~")
        put(g, x + width, y, "~")
    cy = rng.randint(3, h - 4)
    crossing = "bridge" if rng.random() < 0.6 else "ford"
    for x in range(xs[cy] - 1, xs[cy] + width + 1):
        put(g, x, cy, "=" if crossing == "bridge" else "~")
        if crossing == "ford":
            put(g, x, cy + 1, "~")
    path = {(x, cy) for x in range(w)}
    keep = path | {(x, y) for x, y in river} | {(xs[y] - 1, y) for y in range(h)} | {(xs[y] + width, y) for y in range(h)}
    vegetation(g, rng, density, keep=keep, scale=MAP_SCALE * 0.7)
    notes = [f"A river runs north to south, {width} squares wide; a {crossing} crosses it on row {cy + 1}. Deep water needs swimming."]
    if opts.get("boat"):   # a flatboat: deck squares (floor) in the deep water, along the current
        bw = max(1, min(3, width - 1 if width > 2 else 2))
        top = max(0, min(h - 5, cy - 2))
        bx = xs[cy] + (width - bw) // 2
        deck = [(x, y) for y in range(top, top + 5) for x in range(bx, bx + bw)]
        for x, y in deck:
            if g[y][x] in ("W", "~", "="):
                g[y][x] = "."
        notes.append(f"A flatboat's deck ({bw}x5 squares) lies in the water at {fmt(deck[0])}-{fmt(deck[-1])}"
                     + (", under the bridge" if crossing == "bridge" else "") + ": its squares are floor.")
    party = [(1, cy), (2, cy), (1, cy + 1)]
    for x, y in party:
        put(g, x, y, ".")
    return party, path, [], notes


def t_village(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    sy = h // 2 - 1
    street = {(x, sy + k) for x in range(w) for k in range(3)}
    for side in (0, 1):
        x = rng.randint(0, 2)
        while x < w - 4:
            bw, bh = rng.randint(4, 7), rng.randint(3, sy - 1 if side == 0 else h - sy - 4)
            if bh < 3:
                break
            y0 = sy - 1 - bh if side == 0 else sy + 4
            x1 = min(w - 1, x + bw - 1)
            rect(g, x, y0, x1, y0 + bh - 1, "#", fill=False)
            rect(g, x + 1, y0 + 1, x1 - 1, y0 + bh - 2, ".")
            put(g, rng.randint(x + 1, x1 - 1), y0 + bh - 1 if side == 0 else y0, "+")
            x = x1 + rng.randint(2, 3)   # an alley
    edge = [(x, y) for y in (sy, sy + 2) for x in range(3, w) if g[y][x] == "."]
    for x, y in rng.sample(edge, min(len(edge), rng.randint(4, 7))):   # crates, barrels, a cart along the street's sides
        g[y][x] = "-"
    put(g, w // 2, sy + 1, "O")   # the well in the middle of the street
    party = [(1, sy + 1), (2, sy + 1), (1, sy + 2)]
    middle = {(x, sy + 1) for x in range(w)}   # ambushers lie in wait off the middle of the street
    return party, middle, [{"kind": "lantern", "at": (w // 2 - 3, sy)}], ["A village street between houses; alleys between them, crates and barrels about."]


def t_tavern(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    rect(g, 0, 0, w - 1, h - 1, " ")
    W, H = min(w, 22), min(h, 14)
    rect(g, 0, 0, W - 1, H - 1, "#", fill=False)
    rect(g, 1, 1, W - 2, H - 2, ".")
    kx = W - 7   # the kitchen / back room
    for y in range(1, H - 1):
        put(g, kx, y, "#")
    put(g, kx, H // 2, "+")
    for y in range(2, H - 3):   # the bar counter
        put(g, kx - 2, y, "-")
    for x, y in [(3, 3), (3, 7), (7, 3), (7, 7), (11, 5), (4, H - 4), (9, H - 4)]:   # tables with benches
        if x < kx - 3 and y < H - 2:
            put(g, x, y, "m")
            put(g, x + 1, y, "m")
    for x in (5, kx - 5):   # roof posts
        put(g, x, H // 2, "O")
    put(g, 0, H // 2, "+")   # the front door
    put(g, W - 1, 2, "+")    # the back door
    party = [(1, H // 2), (2, H // 2), (1, H // 2 + 1)]
    lights: list[dict[str, Any]] = [{"kind": "torch", "at": (2, 1)}, {"kind": "torch", "at": (kx - 1, H - 2)},
                                    {"kind": "lamp", "at": (kx + 3, 3)}]
    return party, {(x, H // 2) for x in range(1, kx)}, lights, ["A tavern common room: tables, the bar, roof posts; a back room behind the bar."]


def t_cave(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    cells = [[rng.random() < 0.43 for _ in range(w)] for _ in range(h)]
    for _ in range(4):   # cellular automaton: walls where most neighbours are walls
        nxt = [[False] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                n = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                        if not (0 <= x + dx < w and 0 <= y + dy < h) or cells[y + dy][x + dx])
                nxt[y][x] = n >= 5
        cells = nxt
    for y in range(h):
        for x in range(w):
            g[y][x] = "#" if cells[y][x] else "."
    ys = wander(rng, h // 2, w, 2, h - 3, 0.3)   # make sure there's a way through, west to east
    path = {(x, y) for x, y in enumerate(ys)} | {(x, y + 1) for x, y in enumerate(ys)}
    for x, y in path:
        put(g, x, y, ".")
    scatter(g, rng, "^", (w * h) // 14, avoid=path)   # uneven cave floor
    scatter(g, rng, "O", rng.randint(5, 9), avoid=path)   # stalagmites, pillars
    if rng.random() < 0.6:
        open_ = [(x, y) for y in range(2, h - 2) for x in range(2, w - 2) if g[y][x] == "." and (x, y) not in path]
        if open_:
            px, py = rng.choice(open_)
            for x, y in blob(g, rng, px, py, 1.6, "~"):
                if (x, y) in path or g[y][x] == "#":
                    g[y][x] = "." if (x, y) in path else "#"
    party = [(0, ys[0]), (0, ys[0] + 1), (1, ys[1])]
    return party, path, [], ["A natural cave: uneven floor, stalagmites, side pockets off the main way through."]


def t_ruins(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    for _ in range(rng.randint(3, 5)):   # broken walls of old buildings
        x0, y0 = rng.randint(0, w - 7), rng.randint(0, h - 6)
        x1, y1 = x0 + rng.randint(4, 8), y0 + rng.randint(3, 6)
        for y in range(y0, min(h, y1 + 1)):
            for x in range(x0, min(w, x1 + 1)):
                if (y in (y0, y1) or x in (x0, x1)) and rng.random() < 0.7:
                    g[y][x] = "#" if rng.random() < 0.65 else "-"
    scatter(g, rng, "^", (w * h) // 10)   # rubble
    scatter(g, rng, "O", rng.randint(3, 6))   # columns, fallen blocks
    vegetation(g, rng, "sparse", scale=0.35)
    party = [(0, h // 2), (1, h // 2), (0, h // 2 + 1)]
    for x, y in party:
        g[y][x] = "."
    return party, set(party), [], ["Overgrown ruins: broken walls (some only waist-high), rubble, columns."]


def t_camp(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    cx, cy = w // 2, h // 2
    open_ = set(blob(g, rng, cx, cy, min(w, h) / 3, ".", 0.2))
    vegetation(g, rng, density, keep=open_)
    for dx, dy in [(-4, -2), (3, -3), (-3, 3), (4, 2)]:   # tents (2x2, block sight)
        x, y = cx + dx, cy + dy
        if all(inside(g, x + i, y + j) for i in (0, 1) for j in (0, 1)):
            rect(g, x, y, x + 1, y + 1, "#")
    put(g, cx - 1, cy + 4, "-")   # a wagon, crates
    put(g, cx, cy + 4, "-")
    party = [(1, cy), (2, cy), (1, cy + 1)]
    for x, y in party:
        g[y][x] = "."
    return party, open_, [{"kind": "torch", "at": (cx, cy)}], ["A camp in a clearing: tents, a wagon, a campfire in the middle (torch-bright)."]


def t_swamp(g: Grid, rng: random.Random, density: str) -> Built:
    w, h = len(g[0]), len(g)
    for _ in range(rng.randint(4, 7)):
        blob(g, rng, rng.randint(0, w - 1), rng.randint(0, h - 1), rng.uniform(1.5, 3.5), "W")
    for y in range(h):
        for x in range(w):
            if g[y][x] == "." and any(inside(g, x + dx, y + dy) and g[y + dy][x + dx] == "W" for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                g[y][x] = "~"   # bog around the pools
    ys = wander(rng, h // 2, w, 2, h - 3, 0.4)
    path = {(x, y) for x, y in enumerate(ys)}
    for x, y in path:   # a firmer track through it
        if g[y][x] == "W":
            g[y][x] = "~"
    for y in range(h):
        for x in range(w):
            if g[y][x] == "." and (x, y) not in path:
                r = rng.random()
                g[y][x] = "&" if r < 0.25 else '"' if r < 0.55 else "Y" if r < 0.65 else "."
    party = [(0, ys[0]), (1, ys[1])]
    return party, path, [], ["A swamp: deep pools, bog around them, heavy reeds, a firmer track across."]


TEMPLATES: dict[str, tuple[Callable[[Grid, random.Random, str], Built], tuple[int, int], str]] = {
    # name: (builder, default size, default time)
    "forest-road": (t_forest_road, (24, 14), "day"),
    "forest": (t_forest, (22, 16), "day"),
    "clearing": (t_clearing, (22, 16), "day"),
    "field": (t_field, (24, 14), "day"),
    "river": (t_river, (24, 14), "day"),
    "village": (t_village, (24, 14), "day"),
    "tavern": (t_tavern, (22, 14), "inside"),
    "cave": (t_cave, (24, 14), "inside"),
    "ruins": (t_ruins, (22, 14), "day"),
    "camp": (t_camp, (22, 16), "night"),
    "swamp": (t_swamp, (22, 14), "day"),
}
INSIDE_LIGHT = {"tavern": "dim", "cave": "dark"}   # without its light sources


def ambush_spots(g: Grid, path: set[Square], party: list[Square], n: int = 8) -> list[tuple[Square, str]]:
    """Squares near the path (2-6 squares off it) where a creature has cover or concealment: in
    undergrowth or a tree, or right behind a wall, boulder or low wall. Best first."""
    w, h = len(g[0]), len(g)
    near = path or set(party)
    out = []
    for y in range(h):
        for x in range(w):
            ch = g[y][x]
            if ch not in PASSABLE or (x, y) in near:
                continue
            d, (px, py) = min((max(abs(x - px), abs(y - py)), (px, py)) for px, py in near)
            if not 2 <= d <= 6:
                continue
            score = COVERING.get(ch, 0)
            sx, sy = (px > x) - (px < x), (py > y) - (py < y)   # one square toward the path
            behind = inside(g, x + sx, y + sy) and g[y + sy][x + sx] in "O-"   # a wall would block its view too
            score += 2 if behind else 0
            if score >= 2:
                why = {"Y": "tree in undergrowth", "&": "heavy undergrowth", '"': "undergrowth", "T": "tree"}.get(ch, "")
                why = ", ".join(p for p in (why, "behind cover" if behind else "") if p)
                out.append((score, d, (x, y), why))
    out.sort(key=lambda r: (-r[0], r[1]))
    picked: list[tuple[Square, str]] = []
    for _s, _d, sq, why in out:   # spread them out a little
        if all(max(abs(sq[0] - q[0]), abs(sq[1] - q[1])) >= 2 for q, _ in picked):
            picked.append((sq, why))
        if len(picked) >= n:
            break
    return picked


OPTIONS = {"river": ("width", "boat")}   # template options (the rest take none)


def generate(template: str, size: str | None = None, seed: int | None = None, density: str = "medium",
             time: str | None = None, opts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a map. Returns {grid (list of row strings), ambient, party, ambush, lights, notes, seed, template}.

    Raises:
        MapError: an unknown template, density or time, or a bad size.
    """
    if template not in TEMPLATES:
        raise MapError(f"no template {template!r}; templates: {', '.join(TEMPLATES)}")
    if density not in FOREST:
        raise MapError(f"density must be one of {', '.join(FOREST)}")
    build, (w, h), default_time = TEMPLATES[template]
    if size:
        try:
            w, h = (int(v) for v in size.lower().split("x"))
        except ValueError:
            raise MapError(f"size must look like 24x14, not {size!r}")
    if not (10 <= w <= 26 and 8 <= h <= 30):
        raise MapError("size: 10-26 wide, 8-30 high")
    time = time or default_time
    if time != "inside" and time not in TIME_LIGHT:
        raise MapError(f"time must be one of {', '.join(TIME_LIGHT)}")
    seed = seed if seed is not None else random.randrange(10 ** 6)
    rng = random.Random(seed)
    g = blank(w, h)
    opts = {k: v for k, v in (opts or {}).items() if v not in (None, False)}
    unknown = set(opts) - set(OPTIONS.get(template, ()))
    if unknown:
        raise MapError(f"the {template} template takes no option {', '.join(sorted(unknown))} "
                       f"(options: {', '.join(OPTIONS.get(template, ())) or 'none'})")
    party, path, lights, notes = (build(g, rng, density, opts) if template in OPTIONS   # type: ignore[call-arg]
                                  else build(g, rng, density))
    ambient = INSIDE_LIGHT.get(template, "normal") if time == "inside" else TIME_LIGHT[time]
    return {"template": template, "seed": seed, "grid": ["".join(r) for r in g], "ambient": ambient,
            "party": party, "ambush": ambush_spots(g, path, party), "lights": lights, "notes": notes,
            "density": density, "time": time}


def fmt(sq: Square) -> str:
    return f"{chr(65 + sq[0])}{sq[1] + 1}"


def to_file(m: dict[str, Any]) -> str:
    """The map file text: notes as // lines, the ambient light, the grid."""
    lines = [f"// {m['template']} (seed {m['seed']}, {m['density']}, {m['time']}): " + " ".join(m["notes"]),
             "// party: " + " ".join(fmt(q) for q in m["party"]),
             "// ambush spots: " + ", ".join(f"{fmt(q)} ({why})" for q, why in m["ambush"]),
             ]
    if m["lights"]:
        lines.append("// lights: " + ", ".join(f"{li['kind']} at {fmt(li['at'])}" for li in m["lights"]))
    lines.append(f"ambient: {m['ambient']}")
    return "\n".join(lines + m["grid"]) + "\n"
