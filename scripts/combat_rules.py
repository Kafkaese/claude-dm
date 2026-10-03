"""combat_rules: the deterministic rules behind combat.py (PF1e).

Profiles, conditions with durations, situational attack modifiers, cover, area templates and
saves. Everything here is plain calculation on the combat state; combat.py calls it and does the
bookkeeping. Rules sources: Core Rulebook, Combat chapter and Conditions appendix (see
library/pf1e/rules/combat-quick-reference.md). Approximations are marked as such.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

Token = dict[str, Any]    # one combatant in the combat state
State = dict[str, Any]    # the whole combat state (dm/combat/current.json)
Square = tuple[int, int]  # (x, y) grid coordinates, 0-based

PROJECT = Path(__file__).resolve().parents[1]
FRIENDLY = {"pc", "ally"}

# ---------- conditions ----------
# Numeric effects of common conditions (Core Rulebook, Conditions appendix; see
# library/pf1e/rules/conditions.md). Keys:
#   atk / dmg / save / check / ac   flat modifiers
#   str / dex                       ability SCORE penalties. They're never added to anything directly:
#                                   the script recomputes what the ability feeds (see ability effects)
#   str_zero / dex_zero             the score is treated as 0 (helpless, paralyzed)
#   flatfooted                      loses Dex bonus to AC (only a positive bonus; a Dex penalty still counts)
#   concealment                     miss chance (%) for attacks against this creature
#   prone                           +4 AC vs ranged, -4 AC vs melee; -4 on its own melee attacks
#   helpless                        melee attacks against it get +4
#   no_move                         can't move on its own (forced movement still works: --out-of-turn)
#   no_aoo                          can't make attacks of opportunity (grappled and pinned by their
#                                   text; the others because they can't act or attack at all)
# The catalog itself is data: library/<system>/conditions.json (names, these keys, and a note).
# Conditions not listed there are tracked by name only, unless they bring their own modifiers.
CONDITIONS: dict[str, dict[str, Any]] = {}
CONDITION_NOTES: dict[str, str] = {}


def load_conditions(system: str = "pf1e") -> None:
    """Load the system's condition catalog into CONDITIONS (in place, so every reference sees it)."""
    path = PROJECT / "library" / system / "conditions.json"
    data = json.loads(path.read_text(encoding="utf-8")).get("conditions", {}) if path.exists() else {}
    CONDITIONS.clear()
    CONDITION_NOTES.clear()
    for name, eff in data.items():
        eff = dict(eff)
        note = eff.pop("note", None)
        CONDITIONS[name.lower()] = eff
        if note:
            CONDITION_NOTES[name.lower()] = note


def catalog_mods(name: str) -> dict[str, int]:
    """The numeric modifiers (atk, dmg, save, check, ac) a catalog condition gives, for valuing it."""
    return {k: v for k, v in CONDITIONS.get(name.lower(), {}).items()
            if k in ("atk", "dmg", "save", "check", "ac") and isinstance(v, int) and not isinstance(v, bool)}


load_conditions()


def conditions(c: Token) -> list[dict[str, Any]]:
    """The token's conditions as dicts (older states stored plain strings)."""
    out = []
    for x in c.get("conditions") or []:
        out.append(x if isinstance(x, dict) else {"name": str(x)})
    c["conditions"] = out
    return out


def cond_effects(cond: dict[str, Any]) -> dict[str, Any]:
    """The effects of one condition: the catalog's built-in ones plus its own `mods`."""
    eff = dict(CONDITIONS.get(cond["name"].lower(), {}))
    for k, v in (cond.get("mods") or {}).items():
        eff[k] = eff.get(k, 0) + v if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    return eff


def total(c: Token, key: str) -> int:
    """Sum of a numeric effect (atk, dmg, save, check, ac) over all of the token's conditions."""
    return sum(cond_effects(x).get(key, 0) for x in conditions(c) if not isinstance(cond_effects(x).get(key, 0), bool))


def flag(c: Token, key: str) -> bool:
    """Whether any of the token's conditions has a boolean effect (flatfooted, prone, helpless)."""
    return any(cond_effects(x).get(key) for x in conditions(c))


def has(c: Token, name: str) -> bool:
    """Whether the token has a condition with this name (case-insensitive)."""
    return any(x["name"].lower() == name.lower() for x in conditions(c))


def labels(c: Token, st: State | None = None) -> list[str]:
    """Display labels, e.g. ['shaken (1 rd)', 'bless']."""
    out = []
    for x in conditions(c):
        lab = x["name"]
        if st and x.get("expires"):
            left = x["expires"]["round"] - st.get("round", 1)
            lab += f" ({left} rd)" if left > 0 else " (ends this round)"
        out.append(lab)
    return out


def add_condition(st: State, c: Token, name: str, rounds: int | None = None, mods: dict[str, int] | None = None, ongoing: str | None = None) -> dict[str, Any]:
    """Add (or refresh) a condition. With rounds, it ends just before the current actor's turn
    comes around again that many rounds later (the usual PF1e 'N rounds' convention)."""
    conds = [x for x in conditions(c) if x["name"].lower() != name.lower()]
    cond: dict[str, Any] = {"name": name}
    if rounds:
        cond["expires"] = {"round": st.get("round", 1) + rounds, "token": st.get("turn") or c["token"]}
    if mods:
        cond["mods"] = mods
    if ongoing:
        cond["ongoing"] = ongoing
    conds.append(cond)
    c["conditions"] = conds
    return cond


def remove_condition(c: Token, name: str) -> bool:
    """Remove a condition by name. Returns whether it was there."""
    before = len(conditions(c))
    c["conditions"] = [x for x in conditions(c) if x["name"].lower() != name.lower()]
    return len(c["conditions"]) < before


def expire(st: State, token_now: str, round_now: int) -> list[tuple[Token, str]]:
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


# ---------- profile validation ----------

def schema_path(system: str = 'pf1e', kind: str | None = None) -> Path:
    """The schema file for a profile kind: combat-profile-pc.schema.json for player characters
    (if the system has one), else combat-profile.schema.json."""
    base = PROJECT / "library" / system
    pc = base / "combat-profile-pc.schema.json"
    return pc if kind == "pc" and pc.exists() else base / "combat-profile.schema.json"


def schema_for(system: str = 'pf1e', kind: str | None = None) -> dict[str, Any] | None:
    """Load the system's schema for this profile kind, or None if the system has no schema."""
    path = schema_path(system, kind)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is_type(v: Any, t: str) -> bool:
    """Whether `v` has JSON Schema type `t` (booleans are not integers)."""
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def _validate(v: Any, s: dict[str, Any], path: str, errs: list[str]) -> list[str]:
    """A small JSON Schema subset: type, enum, required, properties, additionalProperties,
    patternProperties, items, minItems, minimum, maximum, pattern, anyOf."""
    if "anyOf" in s:
        if not any(not _validate(v, sub, path, []) for sub in s["anyOf"]):
            errs.append(f"{path}: doesn't match any allowed form")
        return errs
    t = s.get("type")
    if t and not any(_is_type(v, x) for x in (t if isinstance(t, list) else [t])):
        errs.append(f"{path}: should be {t}, got {type(v).__name__} ({json.dumps(v)[:40]})")
        return errs
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {json.dumps(v)} is not one of {s['enum']}")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{path}: {v} is below the minimum {s['minimum']}")
        if "maximum" in s and v > s["maximum"]:
            errs.append(f"{path}: {v} is above the maximum {s['maximum']}")
    if isinstance(v, str) and "pattern" in s and not re.match(s["pattern"], v):
        errs.append(f"{path}: {v!r} doesn't match {s['pattern']}")
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            errs.append(f"{path}: needs at least {s['minItems']} item(s)")
        if "items" in s:
            for i, x in enumerate(v):
                _validate(x, s["items"], f"{path}[{i}]", errs)
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing required field '{k}'")
        props, pats = s.get("properties", {}), s.get("patternProperties", {})
        for k, x in v.items():
            if "propertyNames" in s:
                _validate(k, s["propertyNames"], f"{path}.{k} (name)", errs)
            if k in props:
                _validate(x, props[k], f"{path}.{k}", errs)
                continue
            pat = next((p for p in pats if re.match(p, k)), None)
            if pat:
                _validate(x, pats[pat], f"{path}.{k}", errs)
            elif s.get("additionalProperties") is False:
                errs.append(f"{path}: unknown field '{k}'" + (f" (allowed: {', '.join(props)})" if props else ""))
            elif isinstance(s.get("additionalProperties"), dict):
                _validate(x, s["additionalProperties"], f"{path}.{k}", errs)
    return errs


# ---------- library spell effects ----------
# A stat block lists its spells; their effects come from the library (library/<system>/spells/
# <name>.md, a ```spell-effect block) worked out at the caster's level. Numbers there may be formulas
# of `cl` ("10*cl"; dice "{min(cl,5)}d4"), ranges keywords (library/<system>/spellcasting.json).
# The stat block's own `effects` entry merges on top: an `attack` bonus for a touch spell,
# `dmg_bonus`, or a whole effect the library lacks.

NUMERIC_FIELDS = ("range", "dc", "cond_rounds", "buff_rounds", "attack")
DICE_FIELDS = ("dmg", "heal", "area")
_FORMULA_FUNCS = {"min": min, "max": max}


def eval_formula(expr: str, values: dict[str, int]) -> int:
    """An integer formula of the given variables: + - * // / ( ), min(), max(); '/' rounds down.

    Raises:
        ValueError: anything else (names, calls, syntax).
    """
    import ast
    import operator
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.FloorDiv: operator.floordiv, ast.Div: operator.floordiv}

    def ev(n: ast.AST) -> int:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.Name) and n.id in values:
            return values[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return int(ops[type(n.op)](ev(n.left), ev(n.right)))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FORMULA_FUNCS and not n.keywords:
            return int(_FORMULA_FUNCS[n.func.id](*(ev(a) for a in n.args)))
        raise ValueError(f"not allowed in a formula: {ast.dump(n)[:60]}")
    try:
        return ev(ast.parse(str(expr).strip(), mode="eval"))
    except SyntaxError as e:
        raise ValueError(f"bad formula {expr!r}: {e.msg}") from None


def spell_ranges(system: str = "pf1e") -> dict[str, str]:
    """Range keywords of the system (touch, close, …) as formulas of cl."""
    path = PROJECT / "library" / system / "spellcasting.json"
    return json.loads(path.read_text(encoding="utf-8")).get("ranges", {}) if path.exists() else {}


def spell_slug(name: str) -> str:
    """The library file name of a spell: 'Cure Light Wounds' → 'cure-light-wounds'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


SPELLS_DIR: Path | None = None   # tests point this at their own spell files (default: library/<system>/spells)


def library_spell_effect(name: str, system: str = "pf1e") -> tuple[dict[str, Any] | None, str]:
    """The ```spell-effect block of a library spell, unresolved, and where it was looked for.

    Raises:
        ValueError: the block isn't valid JSON.
    """
    path = (SPELLS_DIR or PROJECT / "library" / system / "spells") / f"{spell_slug(name)}.md"
    rel = str(path.relative_to(PROJECT)) if path.is_relative_to(PROJECT) else str(path)
    if not path.exists():
        return None, rel
    m = re.search(r"```spell-effect\s*\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return None, rel
    try:
        return json.loads(m.group(1)), rel
    except json.JSONDecodeError as e:
        raise ValueError(f"{rel}: the spell-effect block isn't valid JSON ({e})") from None


def resolve_effect(raw: dict[str, Any], cl: int, system: str = "pf1e") -> dict[str, Any]:
    """An effect at caster level `cl`: formulas evaluated, range keywords turned into feet,
    dmg_bonus folded into the damage.

    Raises:
        ValueError: a formula that doesn't evaluate.
    """
    values = {"cl": cl}
    ranges = spell_ranges(system)
    out = dict(raw)
    for k in NUMERIC_FIELDS:
        v = out.get(k)
        if isinstance(v, str) and k in ("cond_rounds", "buff_rounds") and re.match(r"^\s*\d+d\d+\s*([+-]\s*\d+)?\s*$", v):
            out[k] = v.replace(" ", "")   # dice: rolled when the effect lands
        elif isinstance(v, str):
            out[k] = eval_formula(ranges.get(v.lower(), v), values)
    for k in DICE_FIELDS:
        v = out.get(k)
        if isinstance(v, str) and "{" in v:
            out[k] = re.sub(r"\{([^}]*)\}", lambda m: str(eval_formula(m.group(1), values)), v)
    if isinstance(out.get("allies"), dict):
        out["allies"] = {k: eval_formula(v, values) if isinstance(v, str) else v for k, v in out["allies"].items()}
    imm = out.get("immunity")
    if isinstance(imm, dict) and isinstance(imm.get("rounds"), str) and not re.match(r"^\s*\d+d\d+", imm["rounds"]):
        out["immunity"] = dict(imm, rounds=eval_formula(imm["rounds"], values))
    bonus = out.pop("dmg_bonus", None)
    if bonus and out.get("dmg"):
        out["dmg"] = f"{out['dmg']}{bonus:+d}"
    return out


def resolve_spell_effects(p: dict[str, Any], system: str = "pf1e") -> tuple[dict[str, Any], list[str], list[str]]:
    """The profile with every spell's and SLA's effect filled in from the library at its caster level
    (the stat block's own entries merged on top). Returns (profile, errors, warnings).
    Spells without any effect data are left out, with a warning (utility ones: mark them)."""
    import copy
    out = copy.deepcopy(p)
    errs: list[str] = []
    warns: list[str] = []
    strict_path = PROJECT / "library" / system / "spell-effect.schema.json"
    strict = json.loads(strict_path.read_text(encoding="utf-8")) if strict_path.exists() else None
    missing: list[str] = []

    def one(name: str, own: dict[str, Any] | None, cl: int, where: str) -> dict[str, Any] | None:
        try:
            lib, rel = library_spell_effect(name, system)
        except ValueError as e:
            errs.append(str(e))
            return None
        merged = dict(lib or {})
        merged.update(own or {})
        if not merged:
            missing.append(name)
            return None
        if merged.get("utility"):
            return None
        try:
            eff = resolve_effect(merged, cl, system)
        except ValueError as e:
            errs.append(f"{where}: {e}")
            return None
        if strict:
            errs.extend(_validate(eff, strict, where, []))
        if eff.get("touch") and eff.get("target") == "one" and eff.get("attack") is None:
            warns.append(f"{where}: a touch spell needs this caster's touch attack bonus: "
                         f"\"effects\": {{\"{name}\": {{\"attack\": N}}}} (ranged touch: BAB + Dex + size)")
        return eff

    for i, sc in enumerate(out.get("spellcasting") or []):
        if not isinstance(sc, dict):
            continue
        own = {k.lower(): v for k, v in (sc.get("effects") or {}).items()}
        resolved: dict[str, Any] = {}
        names = list(dict.fromkeys(n.lower() for lst in (sc.get("spells") or {}).values() for n in lst))
        for n in names + [k for k in own if k not in names]:
            eff = one(n, own.get(n), int(sc.get("cl") or 1), f"spellcasting[{i}].effects.{n}")
            if eff is not None:
                resolved[n] = eff
        sc["effects"] = resolved
    for x in out.get("sla") or []:
        if not isinstance(x, dict) or x.get("per_day") == "constant":
            continue
        eff = one(str(x.get("name", "")), x.get("effect"), int(x.get("cl") or 1), f"sla.{x.get('name')}.effect")
        if eff is not None:
            x["effect"] = eff
        else:
            x.pop("effect", None)
    if missing:
        warns.append("no effect data for " + ", ".join(sorted(set(missing))) + ": casting them applies nothing automatic. "
                     "Add a ```spell-effect block to library/<system>/spells/<name>.md (or {\"utility\": true} for a spell "
                     "without a combat effect)")
    return out, errs, warns


def check_profile(p: Any, system: str = 'pf1e') -> tuple[list[str], list[str]]:
    """Returns (errors, warnings) for a combat profile: the schema plus checks it can't express."""
    kind = p.get("kind") if isinstance(p, dict) else None
    schema = schema_for(system, kind)
    errs = _validate(p, schema, "profile", []) if schema else []
    warns = [] if schema else [f"no schema at {schema_path(system, kind).relative_to(PROJECT)}; only basic checks"]
    if not isinstance(p, dict):
        return errs or ["profile: must be a JSON object"], warns
    import random
    from roll import evaluate, RollError
    if p.get("kind") == "creature" and "attacks" not in p:
        errs.append("profile: a creature needs 'attacks' (it may be empty: {})")
    attacks = p.get("attacks") or {}
    for name, a in attacks.items():
        if not isinstance(a, dict):
            continue
        if name != name.lower():
            warns.append(f"attacks.{name}: use lowercase names ({name.lower()!r}) so --with matches easily")
        if isinstance(a.get("damage"), str):
            try:
                evaluate(a["damage"], random.Random(0))
            except (RollError, ValueError) as e:
                errs.append(f"attacks.{name}.damage: {a['damage']!r} isn't a dice expression ({e})")
        if (a.get("type") == "ranged" or a.get("thrown")) and "range" not in a:
            errs.append(f"attacks.{name}: ranged and thrown attacks need 'range' (the range increment from the weapon table)")
    if p.get("spellcasting") or p.get("sla"):
        p, rerrs, rwarns = resolve_spell_effects(p, system)
        errs += rerrs
        warns += rwarns
    effects = [(f"spellcasting[{i}].effects.{k}", v) for i, sc in enumerate(p.get("spellcasting") or []) if isinstance(sc, dict)
               for k, v in (sc.get("effects") or {}).items()]
    effects += [(f"sla.{x.get('name')}.effect", x["effect"]) for x in p.get("sla") or [] if isinstance(x, dict) and x.get("effect")]
    effects += [(f"abilities.{k}", v) for k, v in (p.get("abilities") or {}).items()]
    for where, eff in effects:
        cond = eff.get("cond") if isinstance(eff, dict) else None
        if isinstance(cond, str) and cond.lower() not in CONDITIONS and "cond_mods" not in eff:
            errs.append(f"{where}.cond: {cond!r} isn't a condition the script knows, so it would do nothing. Use a known "
                        f"name ({', '.join(sorted(CONDITIONS))}), or give a custom one its modifiers in cond_mods "
                        f"(e.g. {{\"atk\": -2}}); put rulings the script can't apply in notes")
    for n in p.get("full_attack") or []:
        if n not in attacks:
            errs.append(f"full_attack: '{n}' isn't in attacks ({', '.join(attacks) or 'none'})")
    for k in ("touch", "ff"):
        if isinstance(p.get(k), int) and isinstance(p.get("ac"), int) and p[k] > p["ac"]:
            warns.append(f"{k} {p[k]} is higher than ac {p['ac']}: double-check the stat block")
    if isinstance(p.get("max_hp"), int) and isinstance(p.get("hp"), int) and p["hp"] > p["max_hp"]:
        errs.append(f"hp {p['hp']} is above max_hp {p['max_hp']}")
    for i, sc in enumerate(p.get("spellcasting") or []):
        if not isinstance(sc, dict):
            continue
        slots, spells = sc.get("slots") or {}, sc.get("spells") or {}
        for lvl, lst in spells.items():
            if lvl not in slots:
                errs.append(f"spellcasting[{i}].spells.{lvl}: level {lvl} has spells but no slots")
            elif sc.get("type") == "prepared" and lvl != "0" and len(lst) > slots[lvl]:
                errs.append(f"spellcasting[{i}]: {len(lst)} level-{lvl} spells prepared but only {slots[lvl]} slots")
        for lvl, sp in (sc.get("domain") or {}).items():
            if sp not in (spells.get(lvl) or []):
                warns.append(f"spellcasting[{i}].domain.{lvl}: {sp!r} should also be in the level-{lvl} spell list")
        if sc.get("type") == "prepared" and not spells:
            errs.append(f"spellcasting[{i}]: a prepared caster needs its prepared 'spells'")
    for i, s in enumerate(p.get("sla") or []):
        if isinstance(s, dict) and s.get("per_day") not in ("constant",) and "level" not in s:
            warns.append(f"sla[{i}] {s.get('name')!r}: no 'level', so concentration checks assume level 0")
    return errs, warns


def profile_text_blocks(text: str) -> list[str]:
    """The raw JSON text of every ```combat-profile block in a markdown file."""
    return re.findall(r"```combat-profile\s*\n(.*?)\n```", text, re.S)


# ---------- profiles ----------

def load_profile(ref: str) -> dict[str, Any] | None:
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


def find_attack(profile: dict[str, Any] | None, name: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """Find an attack in a profile by exact name, unique prefix or unique substring.

    With no name, returns the first attack. Returns (None, None) if nothing or more than one matches.
    """
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


def save_bonus(c: Token, kind: str) -> int | None:
    """The token's save bonus ('fort', 'ref', 'will') from its profile plus condition modifiers
    (flat ones, and a changed Dex modifier for Reflex), or None."""
    saves = (c.get("profile") or {}).get("saves") or {}
    if kind not in saves:
        return None
    return saves[kind] + total(c, "save") + (mod_change(c, "dex") if kind == "ref" else 0)


# ---------- ability effects of conditions ----------
# A condition's ability penalty lowers the SCORE; everything that ability feeds is recomputed
# from the new modifier. Profiles store the finished numbers (AC, touch, flat-footed, saves,
# attack bonuses), so the script applies the difference between the old and new modifier.

def scores(c: Token, ab: str) -> tuple[int, int, bool]:
    """(profile score, effective score, whether the profile has the score) for 'str' or 'dex'.
    A missing score is assumed to be 10, which gives the right modifier change for plain
    penalties, but not for armor caps or a score treated as 0."""
    base = (c.get("profile") or {}).get(ab)
    known = base is not None
    b: int = base if base is not None else 10
    eff = 0 if flag(c, f"{ab}_zero") else max(1, b + total(c, ab))   # approximation: floored at 1
    return b, eff, known


def mod_change(c: Token, ab: str) -> int:
    """How much the conditions change the ability's modifier (0 without ability effects)."""
    b, eff, _ = scores(c, ab)
    return ability_mod(eff) - ability_mod(b)


def _dex_to_ac(c: Token, score: int) -> int:
    """The part of AC that comes from Dex at this score, capped by the armor's max Dex bonus."""
    m = ability_mod(score)
    cap = (c.get("profile") or {}).get("max_dex")
    return min(m, cap) if cap is not None else m


def defenses(c: Token) -> dict[str, int | None]:
    """AC, touch AC and flat-footed AC with the Dex effects of conditions applied (flat condition
    modifiers like -2 AC are NOT included; attack_mods adds those). Flat-footed AC only loses a
    positive Dex bonus, so a Dex penalty that turns the modifier negative lowers it too."""
    b, eff, _ = scores(c, "dex")
    old, new = _dex_to_ac(c, b), _dex_to_ac(c, eff)
    d = new - old
    ac, touch, ff = c.get("ac"), c.get("touch"), c.get("ff")
    return {"ac": ac + d if ac is not None else None,
            "touch": touch + d if touch is not None else None,
            "ff": ff + min(0, new) - min(0, old) if ff is not None else None}


def attack_ability(weapon: dict[str, Any] | None, kind: str) -> str:
    """The ability behind an attack roll: the attack's own 'ability', else Str (melee) or Dex (ranged)."""
    return (weapon or {}).get("ability") or ("str" if kind == "melee" else "dex")


def str_damage_change(c: Token, weapon: dict[str, Any] | None, kind: str) -> int:
    """How much the conditions change an attack's damage through Str. The attack's 'str_damage'
    is the Str multiplier (default 1 for melee and thrown, 0 for other ranged attacks; 1.5 for
    two-handed, 0.5 off-hand). A Str penalty applies in full whatever the multiplier."""
    w = weapon or {}
    mult = w.get("str_damage", 1 if kind == "melee" or w.get("thrown") else 0)
    b, eff, _ = scores(c, "str")

    def part(m: int) -> int:
        return m if m < 0 else math.floor(m * mult)

    return part(ability_mod(eff)) - part(ability_mod(b))


def condition_names(c: Token, keys: tuple[str, ...]) -> list[str]:
    """Names of the token's conditions that have any of these effects."""
    return [x["name"] for x in conditions(c) if any(cond_effects(x).get(k) for k in keys)]


def ability_mod(score: int | None) -> int:
    """The ability modifier for a score (0 for None, e.g. a construct's Con)."""
    return (score - 10) // 2 if score is not None else 0


# ---------- geometry helpers ----------

def cells(c: Token, at: Square | None = None) -> list[Square]:
    """The squares a token occupies (size x size), at its position or at `at`."""
    x, y = at or (c["x"], c["y"])
    return [(x + i, y + j) for i in range(c["size"]) for j in range(c["size"])]


def sq_dist(a: Square, b: Square) -> int:
    """Distance in squares between two squares, PF1e style (every second diagonal counts double)."""
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + min(dx, dy) // 2


def feet_between(c1: Token, c2: Token) -> int:
    """Shortest distance in feet between any squares of two tokens."""
    return 5 * min(sq_dist(a, b) for a in cells(c1) for b in cells(c2))


def center(c: Token) -> tuple[float, float]:
    """The center point of a token's space, in grid units."""
    return (c["x"] + c["size"] / 2, c["y"] + c["size"] / 2)


# Terrain that does more than slow movement (house rule: library/pf1e/house-rules/terrain.md; CRB
# Environment chapter, library/pf1e/rules/terrain.md). Movement costs live in combat.py's TERRAIN.
LINE_BLOCKERS = "# O"          # walls, outside, massive trees / boulders / pillars
TERRAIN_FX: dict[str, dict[str, int]] = {
    "T": {"partial_cover": 1},                     # a tree in the square: +2 AC to whoever stands in it
    "Y": {"partial_cover": 1, "concealment": 20},  # a tree in light undergrowth
    '"': {"concealment": 20},                      # light undergrowth, tall grass, crops
    "&": {"concealment": 30},                      # heavy undergrowth
    "-": {"low_obstacle": 1},                      # low wall, fence, fallen log, crates: cover within 30 ft
}


def blocks_line(st: State, x: int, y: int) -> bool:
    """Whether the square blocks line of effect (a wall, a massive tree or boulder, outside the map, or off the grid)."""
    if not (0 <= x < st["w"] and 0 <= y < st["h"]):
        return True
    return st["grid"][y][x] in LINE_BLOCKERS


def terrain_at(st: State, x: int, y: int) -> dict[str, int]:
    """The terrain effects of a square (concealment, partial cover, low obstacle), or {}."""
    if not (0 <= x < st["w"] and 0 <= y < st["h"]):
        return {}
    return TERRAIN_FX.get(st["grid"][y][x], {})


def terrain_concealment(st: State, t: Token) -> int:
    """Concealment (miss chance %) from the vegetation the creature stands in: its whole space has to
    be inside it (the weakest square counts). Darkvision doesn't see through leaves."""
    return min(terrain_at(st, x, y).get("concealment", 0) for x, y in cells(t))


def partial_cover(st: State, t: Token) -> bool:
    """Whether the creature stands in a tree's square (partial cover: +2 AC, +1 Reflex)."""
    return any(terrain_at(st, x, y).get("partial_cover") for x, y in cells(t))


def low_obstacle_cover(st: State, a: Token, t: Token) -> bool:
    """Cover from a low obstacle (low wall, fence, log) between them: only for a target within 30 ft
    (6 squares) of the obstacle, and not if the attacker is closer to it than the target (CRB pg. 195)."""
    for cell in segment_cells(center(a), center(t)):
        if cell in cells(a) or cell in cells(t) or not terrain_at(st, *cell).get("low_obstacle"):
            continue
        dt = min(sq_dist(cell, q) for q in cells(t))
        da = min(sq_dist(cell, q) for q in cells(a))
        if dt <= 6 and da >= dt:
            return True
    return False


def segment_cells(p: tuple[float, float], q: tuple[float, float], step: float = 0.05) -> list[Square]:
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


def corners(c: Token) -> list[tuple[int, int]]:
    """The four grid-intersection corners of a token's space."""
    xs, ys = (c["x"], c["x"] + c["size"]), (c["y"], c["y"] + c["size"])
    return [(x, y) for x in xs for y in ys]


def cover(st: State, a: Token, t: Token) -> bool:
    """PF1e cover from walls and low obstacles: pick the attacker's best corner; if any line from it
    to a corner of the target's space passes through a blocking square, the target has cover (+4 AC).
    A low obstacle (wall, fence, log) between them also gives cover, within its 30 ft."""
    if low_obstacle_cover(st, a, t):
        return True
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


def soft_cover(st: State, a: Token, t: Token) -> bool:
    """Creatures between attacker and target give soft cover against ranged attacks (+4 AC)."""
    occupied = {}
    for o in st["tokens"]:
        if o is a or o is t or o.get("removed"):
            continue
        for cell in cells(o):
            occupied[cell] = o
    return any(cell in occupied for cell in segment_cells(center(a), center(t)))


def in_melee_with_friend_of(st: State, t: Token, attacker: Token) -> bool:
    """Is the target adjacent to a creature on the attacker's side (firing into melee)?"""
    friendly = attacker["side"] in FRIENDLY
    for o in st["tokens"]:
        if o is attacker or o is t or o.get("removed") or o["hp"] <= 0:
            continue
        if (o["side"] in FRIENDLY) == friendly and feet_between(o, t) <= 5:
            return True
    return False


# ---------- area templates (approximations on the square grid) ----------

def area_cells(st: State, shape: str, size_ft: int, origin: Square | None = None, frm: Token | None = None, toward: Square | None = None) -> list[Square]:
    """Squares covered by a burst (radius around a square), a cone (90 degrees, from a creature
    toward a square) or a line (from a creature toward a square). Approximation: distances use
    the 5-10-5 rule from square centers."""
    n = size_ft // 5
    out = []
    if shape == "burst":
        if origin is None:
            raise ValueError("a burst needs an origin square")
        ox, oy = origin
        for y in range(st["h"]):
            for x in range(st["w"]):
                if sq_dist((x, y), (ox, oy)) <= n:
                    out.append((x, y))
        return out
    if frm is None or toward is None:
        raise ValueError(f"a {shape} needs a source creature and a target square")
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


def tokens_in(st: State, squares: list[Square]) -> list[Token]:
    """The tokens (not removed) with at least one square inside `squares`."""
    sq = set(squares)
    return [o for o in st["tokens"] if not o.get("removed") and any(cell in sq for cell in cells(o))]
