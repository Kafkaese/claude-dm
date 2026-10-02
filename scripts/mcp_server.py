#!/usr/bin/env python3
"""mcp_server.py: Claude DM's game tools as a local MCP server (stdio, JSON-RPC 2.0, stdlib only).

Exposes the combat engine (scripts/combat.py), the dice roller (scripts/roll.py) and world turns
(scripts/world.py) as typed tools, so the DM calls `combat_attack(attacker="g1", target="C",
with="spear")` instead of writing shell commands. Arguments are checked against each tool's
schema before anything runs; the scripts themselves stay the single source of truth (each tool
builds the same argument list the command line would and calls the script's main()).

Registered for Claude Code in .mcp.json (server name "dm", so the tools appear as
mcp__dm__combat_attack etc.); web.py / play.py pass it with --mcp-config.

The campaign: every tool takes an optional `campaign`. The server remembers the last one given,
so it's only needed on the first call of a conversation (or when switching).
"""
from __future__ import annotations

import contextlib
import io
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Callable

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import combat  # noqa: E402
import combat_rules as R  # noqa: E402
import roll  # noqa: E402
import world  # noqa: E402

Args = dict[str, Any]
PROTOCOL = "2025-06-18"

# ---------- schema helpers ----------

def S(desc: str, enum: list[str] | None = None) -> dict[str, Any]:
    """A string property."""
    d: dict[str, Any] = {"type": "string", "description": desc}
    if enum:
        d["enum"] = enum
    return d


def I(desc: str) -> dict[str, Any]:  # noqa: E743
    """An integer property."""
    return {"type": "integer", "description": desc}


def B(desc: str) -> dict[str, Any]:
    """A boolean property."""
    return {"type": "boolean", "description": desc}


TOK = "token id, e.g. g1 or C"
SQ = "square, e.g. D4"
SAVES = ["fort", "ref", "will"]
OOT = B("the actor isn't the current one: a readied or immediate action, forced movement, setup")


class Tool:
    """One MCP tool: its schema, and how its arguments become a script command line."""

    def __init__(self, name: str, desc: str, props: dict[str, Any], required: list[str],
                 build: Callable[[Args], list[str]], script: str = "combat") -> None:
        self.name, self.desc, self.script, self.build = name, desc, script, build
        self.props, self.required = props, required

    def schema(self, with_campaign: bool = True) -> dict[str, Any]:
        """The input schema (JSON Schema)."""
        props = dict(self.props)
        if with_campaign:
            props["campaign"] = {"type": "string"}   # explained once, in the server instructions
        return {"type": "object", "properties": props, "required": list(self.required), "additionalProperties": False}


def flags(a: Args, spec: dict[str, str]) -> list[str]:
    """Command-line options from arguments: {arg name: flag}. Booleans become bare flags."""
    out: list[str] = []
    for k, fl in spec.items():
        v = a.get(k)
        if v is None or v is False:
            continue
        out += [fl] if v is True else [fl, str(v)]
    return out


# ---------- tools ----------

EFFECT = {  # the effect options shared by cast and sla
    "area": S('area template, e.g. "cone 15", "burst 20", "line 60"'),
    "at": S("burst center square"), "toward": S("cone/line direction square"),
    "target": S("single target token"), "save": S("save the effect allows", SAVES),
    "dmg": S("damage dice, e.g. 2d6"), "half": B("half damage on a successful save"),
    "dc": I("override the DC (default: from the profile)"),
    "defensive": B("cast defensively (concentration DC 15 + 2x level)"),
    "no_provoke": B("doesn't provoke (e.g. quickened)"),
    "light_at": S("light/darkness spells: the square it's cast on"),
    "light_on": S("light/darkness spells: the carrier token"),
    "rounds": I("light/darkness spells: duration in rounds"), "out_of_turn": OOT,
    "time": S("casting time (default standard; quickened = swift)", ["standard", "full", "round", "swift", "immediate"]),
    "override": B("don't charge an action"),
}
EFFECT_FLAGS = {"area": "--area", "at": "--at", "toward": "--toward", "target": "--target", "save": "--save",
                "dmg": "--dmg", "half": "--half", "dc": "--dc", "defensive": "--defensive",
                "no_provoke": "--no-provoke", "light_at": "--light-at", "light_on": "--light-on",
                "rounds": "--rounds", "out_of_turn": "--out-of-turn", "time": "--time", "override": "--override"}


def _info(a: Args) -> list[str]:
    what, tok = a["what"], a.get("token")
    need = {"sight", "spells", "dist", "threat", "actions"}
    if what in need and not tok:
        raise ValueError(f"'{what}' needs token")
    return {"show": ["show"], "show_dm": ["show", "--dm"], "events": ["events"] + (["--all"] if a.get("all") else []),
            "sight": ["sight", tok or ""], "actions": ["actions", tok or ""], "spells": ["spells", tok or ""],
            "dist": ["dist", tok or "", a.get("other") or ""], "threat": ["threat", tok or ""],
            "light_map": ["light", "show"] + (["--for", tok] if tok else [])}[what]


def _light(a: Args) -> list[str]:
    act = a["action"]
    need = {"ambient": ["level"], "zone": ["from", "to", "level"], "add": ["kind"], "move": ["id"], "remove": ["id"]}
    missing = [k for k in need.get(act, []) if not a.get(k)]
    if missing:
        raise ValueError(f"action {act} needs {', '.join(missing)}")
    if act == "ambient":
        return ["light", "ambient", a["level"]]
    if act == "zone":
        return ["light", "zone", a["from"], a["to"], a["level"]]
    if act == "add":
        return ["light", "add", a["kind"]] + flags(a, {"at": "--at", "on": "--on", "toward": "--toward",
                                                       "rounds": "--rounds", "magic": "--magic",
                                                       "radius": "--radius", "increased": "--increased"})
    if act in ("move", "remove"):
        return ["light", act, a["id"]] + flags(a, {"at": "--at", "on": "--on", "toward": "--toward"})
    return ["light", "show"] + flags(a, {"for": "--for"})


TOOLS: list[Tool] = [
    Tool("combat_new", "Start an encounter from a map file or a blank grid, with its ambient light.",
         {"map": S("map file, e.g. campaigns/<c>/dm/combat/maps/cave.txt"), "blank": S('blank grid "WxH", e.g. "10x8"'),
          "light": S("ambient light", ["dark", "dim", "normal", "bright"]), "force": B("replace an active encounter")},
         [], lambda a: ["new"] + ([a["map"]] if a.get("map") else []) + flags(a, {"blank": "--blank", "light": "--light", "force": "--force"})),
    Tool("combat_setup", "Build a PREPARED encounter (dm/combat/encounters/<name>.md) in one call: map, lighting, every combatant "
         "(NPC initiative rolled), light sources. Checks everything first. Returns the DM view, tactics, morale and exit ramp.",
         {"encounter": S("encounter name or file"), "init": {"type": "object", "additionalProperties": {"type": "integer"},
                                                            "description": "the PCs' initiative rolls by token, e.g. {\"C\": 17}"},
          "place": {"type": "object", "additionalProperties": {"type": "string"},
                    "description": "override start squares by token, e.g. {\"C\": \"E5\"}"},
          "force": B("replace an active encounter")},
         ["encounter"],
         lambda a: ["setup", a["encounter"]] + [x for k, v in (a.get("init") or {}).items() for x in ("--init", f"{k}={v}")]
         + [x for k, v in (a.get("place") or {}).items() for x in ("--place", f"{k}={v}")] + (["--force"] if a.get("force") else [])),
    Tool("combat_encounters", "List the campaign's prepared encounters, or check them (all, or the named ones) without creating anything.",
         {"action": S("what", ["list", "check"]), "names": {"type": "array", "items": {"type": "string"}}},
         ["action"], lambda a: ["encounter", a["action"], *(a.get("names") or [])]),
    Tool("combat_add", "Add a combatant. Numbers come from the combat-profile block in `ref` (a stat block, or a PC's sheet, "
         "which must pass the PC schema). init: a number (the PC's roll) or \"roll\" (from the profile).",
         {"token": S("1-2 chars: PCs uppercase (C), others lowercase+digit (g1)"), "name": S("display name"),
          "pos": S("top-left square, e.g. D4"), "ref": S("stat block or character sheet path"),
          "init": S('initiative value, or "roll"'), "side": S("default enemy", ["enemy", "pc", "ally"]),
          "hidden": B("the PC hasn't noticed it"), "hp": I("override HP"), "cr": S("CR for XP, e.g. 1/3"),
          "size": I("squares per side"), "reach": I("reach in ft"), "speed": I("speed in ft"),
          "main_dm": B("you (the main DM) play its turns, not the combat runner: a boss or story NPC")},
         ["token", "name", "pos"],
         lambda a: ["add", a["token"], a["name"], "--pos", a["pos"]] + flags(a, {
             "ref": "--ref", "init": "--init", "side": "--side", "hidden": "--hidden", "hp": "--hp", "cr": "--cr",
             "size": "--size", "reach": "--reach", "speed": "--speed", "main_dm": "--main-dm"})),
    Tool("combat_move", "Move a token along the cheapest legal path. NPC attacks of opportunity are rolled; a PC's chance opens a question.",
         {"token": S(TOK), "to": S(SQ), "step": B("a 5-foot step (no AoO)"), "no_aoo": B("don't roll NPC AoOs (deliberate exception)"),
          "as": S("movement as part of this full-round action", ["charge", "withdraw", "run"]), "out_of_turn": OOT, "override": B("don't charge move actions")},
         ["token", "to"], lambda a: ["move", a["token"], a["to"]] + flags(a, {"step": "--step", "no_aoo": "--no-aoo", "as": "--as",
                                                                               "out_of_turn": "--out-of-turn", "override": "--override"})),
    Tool("combat_attack", "An attack. NPC: `with` names a profile attack (the script rolls). PC: `total` and `damage` are the player's rolls. "
         "Situational modifiers (flanking, conditions, cover, light, range) are applied automatically.",
         {"attacker": S(TOK), "target": S(TOK), "with": S("attack name from the attacker's profile"),
          "full": B("full attack"), "charge": B("charge (+2)"), "touch": B("touch attack"), "aoo": B("an attack of opportunity"),
          "total": I("PC: the player's attack total"), "damage": I("PC: the player's damage"), "nat": I("PC: natural 1 or 20"),
          "confirm": I("PC: crit confirmation total"), "ranged": B("PC/raw: a ranged attack"), "name": S("weapon label for the log"),
          "roll": S('NPC without profile: e.g. "1d20+5"'), "dmg": S("NPC without profile: damage dice"),
          "crit": I("threat range low end"), "mult": I("crit multiplier"), "nonlethal": B("nonlethal damage"), "out_of_turn": OOT, "override": B("don't charge an action: a feat or ability changes the action economy")},
         ["attacker", "target"],
         lambda a: ["attack", a["attacker"], a["target"]] + flags(a, {
             "with": "--with", "full": "--full", "charge": "--charge", "touch": "--touch", "aoo": "--aoo", "total": "--total",
             "damage": "--damage", "nat": "--nat", "confirm": "--confirm", "ranged": "--ranged", "name": "--name",
             "roll": "--roll", "dmg": "--dmg", "crit": "--crit", "mult": "--mult", "nonlethal": "--nonlethal",
             "out_of_turn": "--out-of-turn", "override": "--override"})),
    Tool("combat_maneuver", "A combat maneuver (NPC rolls its CMB; PC: total). Provokes from the target unless the Improved feat or grab. "
         "Grapple again = maintain (+5, with option). escape: the held creature (attacker) vs its grappler (target). release: let go.",
         {"attacker": S(TOK), "target": S(TOK),
          "kind": S("maneuver", list(combat.MANEUVERS)), "total": I("PC: the player's check (or Escape Artist)"),
          "nat": I("PC: natural 1 or 20"), "charge": B("as part of a charge"), "grab": B("grab: +4, no AoO"),
          "aoo": B("trip/disarm/sunder as an AoO"), "no_provoke": B("doesn't provoke"),
          "aoo_damage": I("damage the provoked AoO dealt (after asking a PC target)"),
          "option": S("maintaining a grapple", ["pin", "damage", "move", "tie"]), "to": S("reposition target square / grapple move square"),
          "place": S("grapple move: the target's square"), "follow": B("bull rush: move with the target"),
          "condition": S("dirty trick", ["blinded", "dazzled", "deafened", "entangled", "shaken", "sickened"]),
          "item": S("disarm/steal/sunder: the item"), "dmg": S("NPC damage dice"), "damage": I("PC damage"),
          "nonlethal": B("nonlethal"), "reverse": B("escape: become the grappler"), "reach": I("reach of the weapon used"),
          "mod": I("other situational modifier"), "out_of_turn": OOT, "override": B("don't charge an action: a feat or ability changes the action economy")},
         ["attacker", "target", "kind"],
         lambda a: ["maneuver", a["attacker"], a["target"], a["kind"]] + flags(a, {
             "total": "--total", "nat": "--nat", "charge": "--charge", "grab": "--grab", "aoo": "--aoo",
             "no_provoke": "--no-provoke", "aoo_damage": "--aoo-damage", "option": "--option", "to": "--to",
             "place": "--place", "follow": "--follow", "condition": "--condition", "item": "--item", "dmg": "--dmg",
             "damage": "--damage", "nonlethal": "--nonlethal", "reverse": "--reverse", "reach": "--reach",
             "mod": "--mod", "out_of_turn": "--out-of-turn", "override": "--override"})),
    Tool("combat_cast", "An NPC casts a spell (or, with sla, uses a spell-like ability): spends the slot or use, provokes or casts "
         "defensively, and applies the effect given here. Every NPC spell and SLA goes through this.",
         {"caster": S(TOK), "spell": S("spell or ability name"), "sla": B("a spell-like ability"),
          "level": I("spell level, if ambiguous"), "class": S("casting class, if several"), **EFFECT},
         ["caster", "spell"],
         lambda a: (["sla", a["caster"], a["spell"]] + flags(a, EFFECT_FLAGS) if a.get("sla") else
                    ["cast", a["caster"], a["spell"]] + flags(a, {"level": "--level", "class": "--class", **EFFECT_FLAGS}))),
    Tool("combat_area", "A non-spell area effect (breath weapon, trap, hazard): who it covers, saves and damage. NPC spells use combat_cast.",
         {"shape": S("template", ["burst", "cone", "line"]), "feet": I("size in feet"), "at": S("burst center"),
          "from": S("cone/line source token"), "toward": S("cone/line direction square"), "save": S("save", SAVES),
          "dc": I("save DC"), "dmg": S("damage dice"), "half": B("half on a save"), "name": S("name for the log"),
          "no_slot": B("not a spell/SLA of the source")},
         ["shape", "feet"],
         lambda a: ["area", a["shape"], str(a["feet"])] + flags(a, {"at": "--at", "from": "--from", "toward": "--toward",
                                                                   "save": "--save", "dc": "--dc", "dmg": "--dmg", "half": "--half",
                                                                   "name": "--name", "no_slot": "--no-slot"})),
    Tool("combat_save", "A saving throw: an NPC's single save (rolled), or a PC's pending save (total = the player's roll).",
         {"token": S(TOK), "kind": S("save", SAVES), "dc": I("DC"), "total": I("PC: the player's total")},
         ["token"], lambda a: ["save", a["token"]] + ([a["kind"]] if a.get("kind") else []) + flags(a, {"dc": "--dc", "total": "--total"})),
    Tool("combat_stabilize", "A dying creature's stabilization check (a PC's total is required; NPCs roll).",
         {"token": S(TOK), "total": I("PC: the player's total")}, ["token"],
         lambda a: ["stabilize", a["token"]] + flags(a, {"total": "--total"})),
    Tool("combat_condition", "Add a condition or effect (known conditions carry their rules; others: give modifiers), or remove one.",
         {"token": S(TOK), "action": S("add or remove", ["add", "remove"]), "condition": S("e.g. shaken, prone, bless"),
          "rounds": I("duration in rounds (expires by itself)"), "atk": I("attack modifier"), "ac": I("AC modifier"),
          "save": I("save modifier"), "dmg": I("damage modifier"), "check": I("check modifier"), "ongoing": S("ongoing damage dice")},
         ["token", "action", "condition"],
         lambda a: ["cond", a["token"], a["action"], a["condition"]] + flags(a, {"rounds": "--rounds", "atk": "--atk", "ac": "--ac",
                                                                                 "save": "--save", "dmg": "--dmg", "check": "--check",
                                                                                 "ongoing": "--ongoing"})),
    Tool("combat_hp", "Change HP outside an attack (healing +, damage -), and log it.",
         {"token": S(TOK), "delta": I("e.g. -6 or 5"), "why": S("reason for the log")}, ["token", "delta"],
         lambda a: ["hp", a["token"], f"{a['delta']:+d}"] + flags(a, {"why": "--why"})),
    Tool("combat_light", "Lighting: ambient level, zones, light sources and darkness (add/move/remove), or the light map.",
         {"action": S("what to do", ["ambient", "zone", "add", "move", "remove", "show"]),
          "level": S("ambient/zone level", ["dark", "dim", "normal", "bright", "ambient"]), "from": S("zone corner"), "to": S("zone corner"),
          "kind": S("add: torch, sunrod, hooded lantern, bullseye lantern, daylight, darkness, …"), "id": S("move/remove: source id, e.g. l1"),
          "at": S("square"), "on": S("carrier token"), "toward": S("cone direction square"), "rounds": I("duration"),
          "magic": I("spell level"), "radius": I("custom radius ft"), "increased": I("custom increased radius ft"),
          "for": S("show: as this token sees it")},
         ["action"], _light),
    Tool("combat_flag", "Reveal, hide (only after a successful Stealth check) or remove a token.",
         {"token": S(TOK), "action": S("what", ["reveal", "hide", "remove"]), "force": B("hide although a PC sees it clearly")},
         ["token", "action"], lambda a: [a["action"], a["token"]] + (["--force"] if a.get("force") and a["action"] == "hide" else [])),
    Tool("combat_act", "Any other action, charged to the creature's turn: draw a weapon (move), drink a potion (standard, provokes), "
         "total defense (standard), activate boots (swift), speak (free), … \"stand up\" removes prone and provokes. "
         "An immediate action off-turn takes the swift action of its next turn.",
         {"token": S(TOK), "kind": S("action type", ["standard", "move", "full", "swift", "immediate", "free"]),
          "what": S("what it does"), "provokes": B("it provokes attacks of opportunity (Table 8-2)"),
          "log": S("a line for the player-visible combat log"), "override": B("don't charge it")},
         ["token", "kind", "what"],
         lambda a: ["act", a["token"], a["kind"], a["what"]] + flags(a, {"provokes": "--provokes", "log": "--log", "override": "--override"})),
    Tool("combat_surprise", "Turn the surprise round on or off (one standard or move action each; ends when the next round starts).",
         {"on": B("true: surprise round")}, ["on"], lambda a: ["surprise", "on" if a["on"] else "off"]),
    Tool("combat_undo", "Take back the last command if it was the player's own input (e.g. they correct a roll: "
         "forgot flanking), restoring HP, log and actions; then enter the corrected command. NPC rolls stand. "
         "Use this, never override, for corrections.", {}, [], lambda a: ["undo"]),
    Tool("combat_next", "Advance the turn pointer (Claude Code UI / gm-screen only; in web/terminal play the interface does this).",
         {}, [], lambda a: ["next"]),
    Tool("combat_endturn", "The player ended the PC's turn in other words, or together with their actions: the interface plays the next step.",
         {"token": S("the PC's token")}, ["token"], lambda a: ["endturn", a["token"]]),
    Tool("combat_ask", "Set (or clear) the open question that pauses auto-combat until the player answers.",
         {"question": S("the question"), "clear": B("clear it")}, [],
         lambda a: ["ask"] + ([a["question"]] if a.get("question") else []) + (["--clear"] if a.get("clear") else [])),
    Tool("combat_provoke", "Resolve the AoOs a creature provokes now (e.g. a PC casting in melee).",
         {"token": S(TOK), "reason": S('e.g. "casting a spell"'), "no_aoo": B("don't roll NPC AoOs"), "out_of_turn": OOT},
         ["token"], lambda a: ["provoke", a["token"]] + flags(a, {"reason": "--reason", "no_aoo": "--no-aoo", "out_of_turn": "--out-of-turn"})),
    Tool("combat_init", "Change a token's initiative (delay, ready).", {"token": S(TOK), "value": {"type": "number"}},
         ["token", "value"], lambda a: ["init", a["token"], str(a["value"])]),
    Tool("combat_order", "A PC's standing order for attacks of opportunity.",
         {"token": S(TOK), "value": S("order", ["always", "never", "ask"])}, ["token", "value"],
         lambda a: ["order", a["token"], "aoo", a["value"]]),
    Tool("combat_info", "Look things up: show (player view), show_dm (never show it), events (new log lines), sight (what a creature "
         "sees, hiding spots), spells (what's left), dist (token to token/square), threat (who threatens/flanks), light_map.",
         {"what": S("what", ["show", "show_dm", "events", "sight", "spells", "dist", "threat", "light_map", "actions"]),
          "token": S(TOK), "other": S("dist: second token or square"), "all": B("events: all lines")},
         ["what"], _info),
    Tool("combat_options", "A creature's tactical options (DM only): reachable squares that threaten each target with the d20 roll "
         "needed (flanking, cover, light included), what provokes, charge lanes, ranged positions, retreat squares; with area, "
         "the best placements of an area effect (most enemies, no allies).",
         {"token": S(TOK), "area": S('e.g. "burst 20", "cone 15", "line 60"'), "range": I("burst range in ft"), "target": S("only this target")},
         ["token"], lambda a: ["options", a["token"]] + flags(a, {"area": "--area", "range": "--range", "target": "--target"})),
    Tool("combat_log", "Add a free-text line to the player-visible combat log.", {"text": S("the line")}, ["text"],
         lambda a: ["log", a["text"]]),
    Tool("combat_end", "End the encounter: XP summary, PC HP back to the sheets, combat log into the session log, archive.",
         {}, [], lambda a: ["end"]),
    Tool("combat_profile_check", "Validate combat-profile blocks in stat blocks or character sheets.",
         {"files": {"type": "array", "items": {"type": "string"}, "minItems": 1}}, ["files"],
         lambda a: ["profile", "check", *a["files"]]),
    Tool("dice_roll", "Roll dice (every roll the DM makes). rolls: expressions, optionally labeled (\"Goblin init: 1d20+6\"). "
         "hidden for secret rolls. oracle: each roll is a yes/no question answered YES with that % chance. table: each roll is a table file.",
         {"rolls": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "hidden": B("a secret (GM screen) roll"),
          "note": S("context for the roll log"), "times": I("roll each N times"), "oracle": I("yes/no odds in %"),
          "table": B("each roll is a markdown table file")},
         ["rolls"], lambda a: flags(a, {"hidden": "-H", "note": "--note", "times": "-n", "oracle": "--oracle", "table": "--table"}) + list(a["rolls"]),
         script="roll"),
    Tool("world", "World turns (living-world rules as code). turn CLASS: hop, trip, journey, night-safe, night-camp, skip. "
         "Also session (start of a session), day (new in-game day), planned (count a planned event), status, config.",
         {"action": S("what", ["turn", "session", "day", "planned", "status", "config"]),
          "class": S("turn class", list(world.CLASSES)), "table": S("event table, e.g. dm/tables/<region>.md"),
          "region_mod": I("region modifier"), "route": S('repeated route, e.g. "inn>market"'), "settlement": B("in a settlement"),
          "weeks": I("skip: weeks"), "name": S("day: the in-game date"), "text": S("planned: what happens"),
          "pressure": S("config", ["calm", "lively", "relentless"]), "base": I("config: base chance"), "budget": I("config: session budget")},
         ["action"],
         lambda a: [a["action"]] + ([a["class"]] if a["action"] == "turn" and a.get("class") else [])
         + ([a["name"]] if a["action"] == "day" and a.get("name") else []) + ([a["text"]] if a["action"] == "planned" and a.get("text") else [])
         + flags(a, {"table": "--table", "region_mod": "--region-mod", "route": "--route", "settlement": "--settlement",
                     "weeks": "--weeks", "pressure": "--pressure", "base": "--base", "budget": "--budget"}),
         script="world"),
]
INSTRUCTIONS = ("Claude DM's game tools: combat (combat_*), dice (dice_roll) and world turns (world). Every tool takes "
                "an optional `campaign` slug; give it on the first call, after that the server remembers it. Token ids: "
                "PCs uppercase (C), others lowercase+digit (g1); squares like D4. One combat step = one combat_batch call. "
                "Outputs marked DM VIEW, [HIDDEN], show_dm and sight are for the DM only.")
BY_NAME = {t.name: t for t in TOOLS}
BATCHABLE = [t.name for t in TOOLS if t.script == "combat"]
TOOLS.append(Tool(
    "combat_batch", "Several combat actions in ONE call (one combat step: move, then attack, …). Runs them in order and stops at "
    "the first error. Each action is {\"tool\": <combat tool name>, \"args\": {…that tool's arguments}}.",
    {"actions": {"type": "array", "minItems": 1, "items": {
        "type": "object", "required": ["tool"], "additionalProperties": False,
        "properties": {"tool": S("combat tool name", BATCHABLE), "args": {"type": "object"}}}}},
    ["actions"], lambda a: [], script="batch"))
BY_NAME["combat_batch"] = TOOLS[-1]


# ---------- running ----------

class ToolError(Exception):
    """A tool call that couldn't run (bad arguments, no campaign)."""


def _run_script(script: str, argv: list[str]) -> tuple[bool, str]:
    """Run a script's main() in-process, capturing its output. Returns (ok, text)."""
    main = {"combat": combat.main, "roll": roll.main, "world": world.main}[script]
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(argv)
    except SystemExit as e:   # argparse errors
        rc = e.code if isinstance(e.code, int) else 2
    except Exception as e:     # a bug in a script must not kill the server
        return False, f"internal error: {type(e).__name__}: {e}"
    text = (out.getvalue() + ("\n" if out.getvalue() and err.getvalue() else "") + err.getvalue()).strip()
    return rc == 0, text or ("ok" if rc == 0 else "failed")


class Server:
    """The tool dispatcher, with the remembered campaign."""

    def __init__(self) -> None:
        self.campaign: str | None = None

    def _campaign(self, a: Args) -> str:
        camp = a.pop("campaign", None) or self.campaign
        if not camp:
            raise ToolError("no campaign yet: pass campaign=<slug> (once; it's remembered)")
        if not (combat.PROJECT / "campaigns" / camp).is_dir():
            raise ToolError(f"no campaign '{camp}'")
        self.campaign = camp
        return camp

    def _validate(self, tool: Tool, a: Args, with_campaign: bool = True) -> None:
        errs = R._validate(a, tool.schema(with_campaign), tool.name, [])
        if errs:
            raise ToolError("invalid arguments:\n  " + "\n  ".join(errs))

    def _argv(self, tool: Tool, a: Args) -> list[str]:
        try:
            return tool.build(a)
        except (KeyError, ValueError) as e:
            raise ToolError(f"{tool.name}: {e}")

    def call(self, name: str, args: Args) -> tuple[bool, str]:
        """Run one tool. Returns (ok, text)."""
        tool = BY_NAME.get(name)
        if not tool:
            raise ToolError(f"unknown tool {name}")
        a = dict(args or {})
        self._validate(tool, a)
        camp = self._campaign(a)
        if tool.script == "batch":
            parts: list[str] = []
            for i, act in enumerate(a["actions"]):
                sub = BY_NAME[act["tool"]]
                sa = dict(act.get("args") or {})
                try:
                    self._validate(sub, sa, with_campaign=False)
                    argv = self._argv(sub, sa)
                except ToolError as e:
                    return False, "\n".join(parts + [f"[{i + 1}] {act['tool']}: {e}", "(stopped; nothing after this ran)"])
                ok, text = _run_script("combat", ["-c", camp] + argv)
                parts.append(f"[{i + 1}] {act['tool']}: {text}")
                if not ok:
                    return False, "\n".join(parts + ["(stopped at the first error; the actions before it took effect)"])
            return True, "\n".join(parts)
        argv = self._argv(tool, a)
        return _run_script(tool.script, ["-c", camp] + argv)


def tool_list() -> list[dict[str, Any]]:
    """The tools/list payload."""
    return [{"name": t.name, "description": t.desc, "inputSchema": t.schema()} for t in TOOLS]


def handle(server: Server, msg: dict[str, Any]) -> dict[str, Any] | None:
    """Answer one JSON-RPC message (None for notifications)."""
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None   # notifications (initialized, cancelled) need no answer
    if method == "initialize":
        result: Any = {"protocolVersion": params.get("protocolVersion") or PROTOCOL,
                       "capabilities": {"tools": {"listChanged": False}},
                       "serverInfo": {"name": "claude-dm", "version": "1.0"},
                       "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tool_list()}
    elif method == "tools/call":
        try:
            ok, text = server.call(params.get("name", ""), params.get("arguments") or {})
        except ToolError as e:
            ok, text = False, str(e)
        result = {"content": [{"type": "text", "text": text}], "isError": not ok}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(stdin: Any = None, stdout: Any = None) -> None:
    """The stdio loop: one JSON-RPC message per line in, one per line out."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    server = Server()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
            stdout.flush()
            continue
        reply = handle(server, msg)
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()


def cli_equivalent(name: str, args: Args) -> str:
    """The shell command a tool call corresponds to (for docs and debugging)."""
    tool = BY_NAME[name]
    a = dict(args)
    camp = a.pop("campaign", "<campaign>")
    return f"python3 scripts/{tool.script}.py -c {camp} " + " ".join(shlex.quote(x) for x in tool.build(a))


if __name__ == "__main__":
    serve()
