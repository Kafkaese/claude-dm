"""combat_rules: the deterministic rules behind combat.py (PF1e).

Profiles, conditions with durations, situational attack modifiers, cover, area templates and
saves. Everything here is plain calculation on the combat state; combat.py calls it and does the
bookkeeping. Rules sources: Core Rulebook, Combat chapter and Conditions appendix (see
library/pf1e/rules/combat-quick-reference.md). Approximations are marked as such.
"""
import json
import math
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
FRIENDLY = {"pc", "ally"}

# ---------- conditions ----------
# Numeric effects of common conditions. Keys:
#   atk / dmg / save / check / ac   flat modifiers
#   flatfooted                      loses Dex bonus to AC (flat-footed AC is used)
#   concealment                     miss chance (%) for attacks against this creature
#   prone                           +4 AC vs ranged, -4 AC vs melee; -4 on its own melee attacks
#   helpless                        melee attacks against it get +4 (Dex 0 is approximated by flat-footed AC)
# Conditions not listed here are tracked by name only (the DM applies them).
CONDITIONS = {
    "shaken": {"atk": -2, "save": -2, "check": -2},
    "frightened": {"atk": -2, "save": -2, "check": -2},
    "panicked": {"atk": -2, "save": -2, "check": -2},
    "sickened": {"atk": -2, "dmg": -2, "save": -2, "check": -2},
    "dazzled": {"atk": -1},
    "entangled": {"atk": -2},
    "grappled": {"atk": -2, "ac": -2},
    "blinded": {"ac": -2, "flatfooted": True},
    "stunned": {"ac": -2, "flatfooted": True},
    "cowering": {"ac": -2, "flatfooted": True},
    "flat-footed": {"flatfooted": True},
    "helpless": {"flatfooted": True, "helpless": True},
    "unconscious": {"flatfooted": True, "helpless": True},
    "paralyzed": {"flatfooted": True, "helpless": True},
    "prone": {"prone": True},
    "invisible": {"concealment": 50},
    "concealed": {"concealment": 20},
    "charged": {"ac": -2},                    # until the start of its next turn
    "fighting defensively": {"atk": -4, "ac": 2},
    "total defense": {"ac": 4},
    "fatigued": {}, "exhausted": {}, "staggered": {}, "nauseated": {}, "stable": {}, "dying": {},
}


def conditions(c):
    """The token's conditions as dicts (older states stored plain strings)."""
    out = []
    for x in c.get("conditions") or []:
        out.append(x if isinstance(x, dict) else {"name": str(x)})
    c["conditions"] = out
    return out


def cond_effects(cond):
    eff = dict(CONDITIONS.get(cond["name"].lower(), {}))
    for k, v in (cond.get("mods") or {}).items():
        eff[k] = eff.get(k, 0) + v if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    return eff


def total(c, key):
    return sum(cond_effects(x).get(key, 0) for x in conditions(c) if not isinstance(cond_effects(x).get(key, 0), bool))


def flag(c, key):
    return any(cond_effects(x).get(key) for x in conditions(c))


def has(c, name):
    return any(x["name"].lower() == name.lower() for x in conditions(c))


def labels(c, st=None):
    """Display labels, e.g. ['shaken (1 rd)', 'bless']."""
    out = []
    for x in conditions(c):
        lab = x["name"]
        if st and x.get("expires"):
            left = x["expires"]["round"] - st.get("round", 1)
            lab += f" ({left} rd)" if left > 0 else " (ends this round)"
        out.append(lab)
    return out


def add_condition(st, c, name, rounds=None, mods=None, ongoing=None):
    """Add (or refresh) a condition. With rounds, it ends just before the current actor's turn
    comes around again that many rounds later (the usual PF1e 'N rounds' convention)."""
    conds = [x for x in conditions(c) if x["name"].lower() != name.lower()]
    cond = {"name": name}
    if rounds:
        cond["expires"] = {"round": st.get("round", 1) + rounds, "token": st.get("turn") or c["token"]}
    if mods:
        cond["mods"] = mods
    if ongoing:
        cond["ongoing"] = ongoing
    conds.append(cond)
    c["conditions"] = conds
    return cond


def remove_condition(c, name):
    before = len(conditions(c))
    c["conditions"] = [x for x in conditions(c) if x["name"].lower() != name.lower()]
    return len(c["conditions"]) < before


def expire(st, token_now, round_now):
    """Remove conditions that end as `token_now` starts its turn in `round_now`."""
    gone = []
    for c in st["tokens"]:
        keep = []
        for x in conditions(c):
            e = x.get("expires")
            if e and (e["round"] < round_now or (e["round"] == round_now and e["token"] == token_now)):
                gone.append((c, x["name"]))
            else:
                keep.append(x)
        c["conditions"] = keep
    return gone


# ---------- profiles ----------

def load_profile(ref):
    """The ```combat-profile JSON block from a stat block or character sheet file."""
    path = Path(ref)
    if not path.is_absolute():
        path = PROJECT / ref
    if not path.exists():
        return None
    m = re.search(r"```combat-profile\s*\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return None
    return json.loads(m.group(1))


def find_attack(profile, name):
    attacks = (profile or {}).get("attacks") or {}
    if not name:
        if not attacks:
            return None, None
        name = next(iter(attacks))
    key = name.lower()
    for k, v in attacks.items():
        if k.lower() == key:
            return k, v
    for test in (lambda k: k.startswith(key), lambda k: key in k):   # unique prefix, then substring
        matches = [(k, v) for k, v in attacks.items() if test(k.lower())]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None, None   # ambiguous: the caller lists the names
    return None, None


def save_bonus(c, kind):
    saves = (c.get("profile") or {}).get("saves") or {}
    if kind not in saves:
        return None
    return saves[kind] + total(c, "save")


def ability_mod(score):
    return (score - 10) // 2 if score is not None else 0


# ---------- geometry helpers ----------

def cells(c, at=None):
    x, y = at or (c["x"], c["y"])
    return [(x + i, y + j) for i in range(c["size"]) for j in range(c["size"])]


def sq_dist(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + min(dx, dy) // 2


def feet_between(c1, c2):
    return 5 * min(sq_dist(a, b) for a in cells(c1) for b in cells(c2))


def center(c):
    return (c["x"] + c["size"] / 2, c["y"] + c["size"] / 2)


def blocks_line(st, x, y):
    if not (0 <= x < st["w"] and 0 <= y < st["h"]):
        return True
    return st["grid"][y][x] in "# "


def segment_cells(p, q, step=0.05):
    """Squares a segment passes through (sampled; endpoints excluded)."""
    n = max(2, int(math.dist(p, q) / step))
    seen = []
    for i in range(1, n):
        t = i / n
        x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
        cell = (math.floor(x), math.floor(y))
        if cell not in seen:
            seen.append(cell)
    return seen


def corners(c):
    xs, ys = (c["x"], c["x"] + c["size"]), (c["y"], c["y"] + c["size"])
    return [(x, y) for x in xs for y in ys]


def cover(st, a, t):
    """PF1e cover from walls: pick the attacker's best corner; if any line from it to a corner
    of the target's space passes through a blocking square, the target has cover (+4 AC)."""
    a_cells, t_cells = set(cells(a)), set(cells(t))
    best_blocked = None
    for pa in corners(a):
        blocked = False
        for pt in corners(t):
            for cell in segment_cells(pa, pt):
                if cell in a_cells or cell in t_cells:
                    continue
                if blocks_line(st, *cell):
                    blocked = True
                    break
            if blocked:
                break
        if not blocked:
            return False
        best_blocked = True
    return bool(best_blocked)


def soft_cover(st, a, t):
    """Creatures between attacker and target give soft cover against ranged attacks (+4 AC)."""
    occupied = {}
    for o in st["tokens"]:
        if o is a or o is t or o.get("removed"):
            continue
        for cell in cells(o):
            occupied[cell] = o
    return any(cell in occupied for cell in segment_cells(center(a), center(t)))


def in_melee_with_friend_of(st, t, attacker):
    """Is the target adjacent to a creature on the attacker's side (firing into melee)?"""
    friendly = attacker["side"] in FRIENDLY
    for o in st["tokens"]:
        if o is attacker or o is t or o.get("removed") or o["hp"] <= 0:
            continue
        if (o["side"] in FRIENDLY) == friendly and feet_between(o, t) <= 5:
            return True
    return False


# ---------- area templates (approximations on the square grid) ----------

def area_cells(st, shape, size_ft, origin=None, frm=None, toward=None):
    """Squares covered by a burst (radius around a square), a cone (90 degrees, from a creature
    toward a square) or a line (from a creature toward a square). Approximation: distances use
    the 5-10-5 rule from square centers."""
    n = size_ft // 5
    out = []
    if shape == "burst":
        ox, oy = origin
        for y in range(st["h"]):
            for x in range(st["w"]):
                if sq_dist((x, y), (ox, oy)) <= n:
                    out.append((x, y))
        return out
    src = frm
    sx, sy = center(src)
    tx, ty = toward[0] + 0.5, toward[1] + 0.5
    ang = math.atan2(ty - sy, tx - sx)
    own = set(cells(src))
    if shape == "cone":
        for y in range(st["h"]):
            for x in range(st["w"]):
                if (x, y) in own:
                    continue
                dx, dy = x + 0.5 - sx, y + 0.5 - sy
                d = min(sq_dist((x, y), c) for c in own)
                if d > n:
                    continue
                diff = abs((math.atan2(dy, dx) - ang + math.pi) % (2 * math.pi) - math.pi)
                if diff <= math.pi / 4 + 1e-9:
                    out.append((x, y))
        return out
    if shape == "line":
        end = (sx + math.cos(ang) * n * 1.0, sy + math.sin(ang) * n * 1.0)
        return [cell for cell in segment_cells((sx, sy), end, step=0.02)
                if cell not in own and 0 <= cell[0] < st["w"] and 0 <= cell[1] < st["h"]]
    raise ValueError(shape)


def tokens_in(st, squares):
    sq = set(squares)
    return [o for o in st["tokens"] if not o.get("removed") and any(cell in sq for cell in cells(o))]
