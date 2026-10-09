"""dm_engine: the core of Claude DM's player-facing interface (web.py).

Runs Claude Code headless (`claude -p`, stream-json) in this repo and turns its event stream
into a few neutral events for a frontend to display. Only the main agent's own text reaches
the player; tool calls, tool results and subagents stay hidden.

Events passed to `on_event(ev)` (dicts):
  {"type": "status", "label": str or None}   something is happening behind the screen / done
  {"type": "text_start"}                      a new block of DM text begins
  {"type": "text", "delta": str}              streamed DM text (markdown)
  {"type": "text_end"}                        the block is complete
  {"type": "turn_end", "solicited": bool}     a reply is complete (False: nobody was waiting,
                                              e.g. a background task woke the DM up)
  {"type": "session", "id": str}
  {"type": "error", "message": str}
  {"type": "debug", "line": str}              only when debug is on
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

Event = dict[str, Any]                  # one engine event, see the module docstring
EventHandler = Callable[[Event], None]

REPO = Path(__file__).resolve().parent
STATE = REPO / ".play"

# The built-in tools the DM process has at all (`--tools`; it also limits its subagents, so the web
# tools stay for dm-researcher and dm-scribe, while the DM itself never uses them). Every built-in
# tool's definition rides along in every model call: the full set costs ~30k tokens per call.
DM_TOOLS = "Bash,Read,Write,Edit,Glob,Grep,Skill,Agent,WebFetch,WebSearch"

ALLOWED_TOOLS = [
    "Read", "Glob", "Grep", "Edit", "Write", "Agent", "Skill",
    "WebFetch", "WebSearch",   # for the research subagents (the allowlist hook limits the sites)
    "mcp__dm",   # the game tools (scripts/mcp_server.py): dice_roll, world, combat_*; the scripts aren't run via Bash here
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)",
    "Bash(sed -n:*)", "Bash(wc:*)", "Bash(find:*)", "Bash(mkdir:*)",
    "Bash(cp -R campaigns/_template:*)",
    "Bash(git status:*)", "Bash(git add:*)", "Bash(git commit:*)",
]

WRAPPER_PROMPT = """You are running inside Claude DM's player-facing web interface.
- The player sees ONLY your own text. Tool calls, tool results, subagent activity and subagent text are hidden from them.
- Do hidden mechanics yourself, with the `dm` tools (dice_roll, world, combat_*; give `campaign` on the first call), and read and write dm/ files directly. Where the docs show a script command line, use the matching tool: `combat.py attack …` = combat_attack, `combat.py do "…" "…"` = ONE combat_batch, `roll.py` = dice_roll, `world.py turn …` = world. Use dm-scribe, dm-researcher and continuity-checker for heavy jobs (prep, research, the continuity check), and always wait for their results.
- Everything you write as text is shown to the player. So never think out loud ("Let me check…", "Now I need…"), never mention files, tools or DM-only content, and write only what the DM says at the table.
- The interface shows the combat map, the initiative order and the combat log after each turn in which the combat state changed. Don't paste the map yourself.
- NARRATION CONTRACT (these override your instincts as a writer):
  - Address the player's character as "you", always in the second person. Never "Corin does…" or "he says…".
  - Never write the PC's words, thoughts, feelings or actions beyond what the player declared. An implied intention isn't a declaration.
    - "I try to read the writing" → give what the character reads and understands ("The glyphs are old Thassilonian: 'Here stands…'"). Don't have them read it aloud, react or comment.
    - "I try to force the door" → resolve the attempt ("The door grinds open, wide enough to pass") and STOP. Don't have them step through.
    - "I attack" → resolve the attack, then say which actions remain. Don't add a move or a line of dialogue.
  - Checks you roll secretly (Perception, Knowledge, Sense Motive, …) are invisible. Never mention them: not that you rolled, not how many, not whether they succeeded (no "All three succeed", no "Perception 21"). Narrate only what the character notices or knows. A failed check simply produces nothing, or the misleading impression.
  - Roll markers: when you roll a check the PLAYER initiated ("I examine the hands" → Perception), put `*(Rolled: Perception)*` on its own line before the result (check name only, never the total or DC), unless session zero turns roll markers off. Secret checks never get a marker.
  - Companions and NPCs speak and act for themselves. The PC doesn't, unless the player says so.
  - No fourth wall: NPCs never mention HP, AC, levels, checks or other game terms (the only exception is a meta character the player asked for in session zero).
  - PLAYER KNOWLEDGE ONLY: write what the character perceived, was told or can conclude, never what you know as DM. The journal test: could the character write this sentence in their own journal?
    - Describe NPC behavior, not their minds: "Mordent gives no sign that anything has changed", never "Mordent doesn't know that you know".
    - Never name a lead, flaw, culprit or connection the character hasn't found, not even as an open question: "you couldn't tell whether the circle was drawn correctly", never "the ritual circle's flaw".
    - No loaded framing that confirms a hidden truth ("whether it was anything but an accident", "the real culprit"). A failed investigation reports what was checked and what it showed, not that something was missed.
- POSSESSIONS AND MONEY go through the gear tool only (loot: add / receive; spending: pay, use; shopping: buy / sell at a shop in dm/shops/, written when the party first visits it; moving things: move). It logs every change; the player sees the gear in the Character and Party stash tabs, generated from the inventory (the sheets have no gear list: gear show tells you who carries what). Details: dm-procedures.md, "Gear, money and shops". HP outside a fight (healing, rest, a trap) goes through character_hp, never by editing the sheet's HP line.
- COMBAT (details: library/general/table-rules/combat.md; the combat tools' descriptions have the options):
  - /start-session doesn't load combat.md: read it when a fight starts, right after the message that calls the fight (with the setup, while the player rolls initiative), unless you've read it in this conversation since the last compaction.
  - The script does all the rule math (modifiers, AoOs, maneuvers, light and vision, durations, dying). Never compute modifiers, count squares or roll attacks yourself. NPCs: combat_attack with `with` (a profile attack); PCs: the player's rolls (combat_attack with `total`, plus `damage` if they gave it; a hit without it waits for their damage: ask, then combat_damage; a PC's spell: combat_cast with total for a touch attack and amount for its damage or healing). Tokens can be named by id or by the creature's name.
  - THE PLAYER ROLLS ALL OF THE PC'S DICE: attacks, damage, healing (a cure spell's 1d8+N), saves, checks. Never call dice_roll for the PC and never make up a PC's number, also not after a tool error: ask for it.
  - Light and vision follow the table's own house rule (library/pf1e/house-rules/vision-and-light.md: e.g. not seeing an attacker in darkness denies the Dex bonus). The script implements it on purpose: don't "correct" it against the Core Rulebook.
  - Every NPC spell or SLA goes through combat_cast (sla=true for SLAs), with its effect in the same call (a profile with effect data for that spell fills it in). Special abilities (bardic performance, channel energy, breath weapons) go through combat_ability. Sneak attack is added automatically. Conditions go in the same call (cond, cond_rounds): they land on failed saves, and a PC's after their roll.
  - The player's battle map, initiative and log only appear once you engage combat in this conversation. When you resume a saved fight (after /start-session), call combat_info what=show first: that brings the fight back on screen.
  - YOU ARE IN THE INTERFACE. When a combat tool says the interface runs the turns, that's this interface: never tell the player to run anything, just follow the tool's advice.
  - Setup: a prepared encounter (combat_encounters action=list) is ONE combat_setup call once the player's initiative is in. Otherwise: every combatant needs a valid combat profile (add one from the stat block first; a PC's sheet must pass the PC schema, so ask the player for missing values). Decide the lighting as part of the encounter. PC tokens use the first letter of the name (Corin → C). After setup, narrate the opening, give the initiative order and stop: the interface starts the turns right after your reply (an enemy that's first plays at once). If the player declares actions before their turn comes, tell them who acts first; their turn follows.
  - THE MAP MUST FIT THE SCENE: if it doesn't (or the player says so), fix it in place: combat_terrain paints squares or rectangles (a boat's deck, a wall, water), combat_map with replace swaps in a new map under the running fight (river: width, boat). Never restart a fight with combat_new to fix a map: it resets the round and creatures act twice.
  - The player's plan for companions and allies ("Brenna grapples Dessick", given before the fight or during it): record each one with combat_plan at setup (and whenever new orders come); the runner plays them by those orders. What everyone holds at the start should fit the scene: party members start with the weapons equipped in their inventory; for anyone else (or a different start) give `wielding` at combat_add / in the encounter. To change or fix what someone holds outside its turn, use combat_wield with out_of_turn: never `override` on an attack.
  - THE COMBAT RUNNER plays most NPC turns: a separate, lean process the interface hands each enemy's step to (it saves most of the tokens). You then get "[Interface recap: …]" in front of the player's next message: what it narrated and the combat log. Treat that as what happened; the player saw it. Creatures you play yourself (a boss, a story NPC: `dm_plays` in the encounter, or combat_add main_dm) still come to you as combat steps; the first time in a session, read library/general/table-rules/combat-npc-turns.md (their spells, tactics, sight, morale).
  - THE PLAYER'S TURNS in a fight go to a second lean process too: it resolves the actions they declare (with their rolls) and narrates them; that shows up in the same recap. It hands you what isn't a combat action (parley, threats and questions to NPCs, lore or rules questions, stunts that need a DC, out-of-character remarks), so a player message during their turn that reaches you is one of those: handle it, and resolve any actions it also declares. [Bracketed] messages always come to you.
  - THE INTERFACE RUNS THE TURN ORDER. Never run `next` (it's refused). A bracketed "[Combat step …]" message names ONE actor, what it can see, and its tactical options (squares, the roll it needs there, what provokes; combat_options with area for area effects): resolve exactly that actor in ONE combat_batch call, narrate only that actor, and stop. Play it by its nature and what it sees. A hidden actor's step: reply "…" unless it gets revealed.
  - SUBMIT WHAT THE PLAYER DECLARED, EXACTLY: never judge yourself whether an action is legal or already used up, the script does. The "Now: round N, …" line in the bracket is the truth about whose turn it is (on the PC's turn: what's left; earlier turns don't count). When it says it's NOT the player's turn, the player is talking between other creatures' turns: answer, but don't resolve their character's actions or hand them the turn. If a tool REFUSES the declared action (e.g. a 5-foot step that costs 10 ft), tell the player plainly why and ask what they do instead. Never substitute another action for them (no full move instead of a refused step).
  - To explain why an NPC did something, show its logged briefing: combat_info what=briefing token=… (round=N). Never move tokens back and forth to recreate an earlier position.
  - Corrections go through combat_undo (the player's last command) or the specific command (combat_hp, combat_condition). NEVER read or edit the combat state files or the engine's code (scripts/, dm_engine.py, web.py; a hook blocks it): if a tool refuses something and you don't see why, or you think the script is wrong, say so out of character and go on with its result, or ask the player how to rule. Don't retry a refused call unchanged, and don't investigate the engine.
  - Every action is charged to the actor's turn, and the tool results say what's left; actions without their own tool (draw a weapon, stand up, drink a potion) are combat_act. On the PC's turn, resolve what the player declares and say which actions remain, from that report. If the player corrects a roll they already gave (a forgotten modifier), call combat_undo and enter the corrected one: never `override` for that. `override` is only for a feat or ability that changes the rules (Spring Attack, Quick Draw). If the player ends the turn in other words or together with their actions, call combat_endturn.
  - Once no enemy is left standing and nobody is dying, the interface leaves the final turn on screen and the player ends the fight (End combat, or their next message); then it runs combat_end and tells you ("[The fight is over …]", with the player's message if they wrote one): narrate the aftermath. End it yourself with combat_end only when it ends otherwise (surrender, flight, parley).
  - When a tool result sets a question (an AoO, a save, a stabilization check) or the player must decide something mid-round, ask them (combat_ask for your own questions). A dying PC rolls their own stabilization checks; never play the fight forward without the player.
  - The interface shows the map, initiative and combat log with all the numbers. Narrate EVERY creature's turn in its own line or lines, matching the log. Never merge turns, skip a creature, or contradict a number.
- Do lookups before you start writing to the player, so you never send the same text twice.
- Before any in-game narration, the /start-session skill must have run in this conversation (it loads the table rules). If the player wants to play and it hasn't, run it first.
- AskUserQuestion isn't available here. Ask questions in plain text, with the options as a short list.
- Keep turns fast. Every tool call costs the player waiting time:
  - put all rolls for a turn in ONE dice_roll call, and all combat actions of a step in ONE combat_batch call
  - don't re-read files you've already read this session
  - log tersely, at scene breaks only: one short Edit to the live log, not one per action
  - read files by section (grep -n '^#' to find the heading, then Read with offset and limit)"""

EFFORTS = ("low", "medium", "high", "xhigh", "max")


def flavor(tool_name: str | None, sub: bool) -> str:
    """The status-line label shown to the player while a tool runs (never the tool itself)."""
    if sub:
        return "working behind the screen"
    return {
        "Bash": "checking notes", "Read": "checking notes", "Grep": "checking notes",
        "Glob": "checking notes", "Edit": "taking notes", "Write": "taking notes",
        "Agent": "working behind the screen", "Task": "working behind the screen",
        "WebFetch": "consulting references", "WebSearch": "consulting references",
        "Skill": "getting ready", "TodoWrite": "planning",
    }.get(tool_name or "", "rolling dice and moving pieces" if (tool_name or "").startswith("mcp__dm__") else "thinking")


def save_session(sid: str | None) -> None:
    """Append a session id to .play/sessions.log (the picker's "continue" finds a campaign's latest there)."""
    if not sid:
        return
    STATE.mkdir(exist_ok=True)
    with (STATE / "sessions.log").open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')} {sid}\n")


# ---------- telemetry ----------
# One JSON line per exchange in .play/telemetry.jsonl (local and gitignored; it contains the DM's
# commands, so it's DM-only). Summarize with: python3 scripts/telemetry.py

TELEMETRY = STATE / "telemetry.jsonl"


def is_combat_tool(name: str, inp: dict[str, Any]) -> bool:
    """Whether a tool call works on the fight: a dm combat tool, or combat.py run through Bash."""
    if name.startswith("mcp__dm__combat_"):
        return name not in ("mcp__dm__combat_profile_check", "mcp__dm__combat_encounters")
    return name == "Bash" and "combat.py" in str(inp.get("command", "")) and " profile check" not in str(inp.get("command", ""))


INTERFACE_PREFIXES = ("[Combat step", "[The player is switching to another campaign", "[Test setup", "[The fight is over", "/compact",
                      "[The session is ending", "[Close the session", "[Session start")
RECAP_PREFIX = "[Interface recap"


COMPACT_PROMPT = ("/compact Keep what running this table needs: the campaign and session number, the current scene and "
                  "situation, any question the player still has to answer (e.g. their initiative roll for a fight just called: their "
                  "next message is that answer), a fight in progress (round, whose turn; the combat tools have the details), of a finished fight only "
                  "its outcome (who fell or fled, injuries, loot, prisoners), what the player's "
                  "character did and said recently and what they're trying to do, NPCs met and what was said, rulings, "
                  "corrections and table preferences from this conversation, open threads touched this session, and anything "
                  "promised to the player. Facts from dm/ files can be dropped: they're in the files (and dm/screen-digest.md).")


# Closing a session (web.py): the interface asks the stars & wishes itself, the playing DM brings
# its live log up to date (FLUSH_PROMPT, one short exchange), and a FRESH conversation runs
# /end-session from the files (close_prompt). The skill's heavy part then reads ~30k tokens of
# context per call instead of the whole session's 200k+.
WISHES_QUESTION = ("Before we wrap up, out of character:\n"
                   "1. **Stars & wishes:** what did you enjoy this session, and what would you like to see more of?\n"
                   "2. **Anything to note:** rulings you disagreed with, or changes to lines and veils?\n\n"
                   "A short answer or \"skip\" is fine. Say \"cancel\" to keep playing instead.")

FLUSH_PROMPT = ("[The session is ending. Another conversation will close it from the files, without this one's memory. "
                "Bring the live log (dm/session-log/session-NN.md) up to date NOW, tersely, with one Edit: everything "
                "since its last entry that only this conversation knows (scenes, hidden rolls and their outcomes, "
                "improvised facts and NPCs, rulings, promises, the exact current situation). Don't write anything "
                "else, and reply only: \"done\".]")


def close_prompt(slug: str, nn: int, wishes: str, transcript: Path | None, fight: bool = False, bundle: str = "") -> str:
    """The fresh closing conversation's first message: run /end-session from the files. `fight`: a fight
    is still in progress (only then is it mentioned: otherwise the DM goes looking for one)."""
    where = (f" The player-visible transcript of the session (what was said and narrated, no DM secrets) is in "
             f"`{transcript.relative_to(REPO) if transcript.is_relative_to(REPO) else transcript}`: use it for the recap, and read it by sections if it's long."
             if transcript else "")
    return (f"[Close the session (from the interface): run the /end-session skill for campaign `{slug}`, session {nn:02d}. "
            f"This is a fresh conversation: the session was played in another one, so don't run /start-session; "
            f"work from the files. The DM side is in the live log `dm/session-log/session-{nn:02d}.md`.{where} "
            + ("A fight is still in progress: its state is in the combat tools (combat_info what=show_dm). " if fight
               else "No fight is in progress. ")
            + "\n"
            f"Step 1 is done (the interface asked). The player's answer to stars & wishes and anything to note: "
            f"\"{wishes.strip() or 'skip'}\". Start at Step 2. XP goes on the sheets with character_xp; the interface "
            f"increments \"Sessions played\" when you're done (don't).]"
            + (f"\n\n{bundle}" if bundle else ""))


# The session start (web.py): the interface does /start-session's mechanical steps itself and hands the
# DM the files it would otherwise read one turn at a time (26 turns in session 4), in ONE message.
START_RULES = ("safety-tools", "communication", "running-the-game", "dm-procedures", "continuity", "living-world")
START_FILE_LIMIT = 40_000   # characters per file in the bundle


def session_start_bundle(slug: str) -> str:
    """The first message of a fresh session: the session number, what the interface already did (live
    log created, campaign set active, world session reset, combat profiles checked), and the files
    /start-session's Step 2 and the brief need, so the DM reads none of them again."""
    camp = REPO / "campaigns" / slug
    md = (camp / "campaign.md").read_text(encoding="utf-8")
    played = re.search(r"\*\*Sessions played:\*\*\s*(\d+)", md)
    nn = (int(played.group(1)) if played else 0) + 1
    log = camp / "dm" / "session-log" / f"session-{nn:02d}.md"
    resume = log.exists()
    done = []
    if not resume:
        template = (REPO / ".claude" / "skills" / "start-session" / "session-log-template.md").read_text(encoding="utf-8")
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(template.replace("Session NN", f"Session {nn:02d}", 1)
                       .replace("- **Real date:**", f"- **Real date:** {time.strftime('%Y-%m-%d')}", 1), encoding="utf-8")
        done.append(f"created the live log dm/session-log/session-{nn:02d}.md from the template")
        if re.search(r"\*\*Status:\*\*\s*(?!active)\S", md):
            md = re.sub(r"(\*\*Status:\*\*\s*)[^\n]*", r"\g<1>active", md, count=1)
            (camp / "campaign.md").write_text(md, encoding="utf-8")
            done.append("set campaign.md status to active")
        world_out = _run_script_quiet("world.py", slug, ["session"])
        done.append(f"reset the world's session count ({world_out.strip()})")
    sheets = sorted(p for p in (camp / "players" / "characters").glob("*.md") if p.name.lower() != "readme.md")
    if sheets:
        check = _run_script_quiet("combat.py", slug, ["profile", "check"] + [str(p.relative_to(REPO)) for p in sheets])
        done.append("ran combat_profile_check on the sheets:\n" + check.strip())
    files = [REPO / "library" / "general" / "table-rules" / f"{n}.md" for n in START_RULES]
    files += [camp / "campaign.md", camp / "players" / "session-zero.md", camp / "players" / "party.md"]
    recaps = sorted((camp / "players" / "recaps").glob("session-*.md"))
    files += recaps[-1:] + sheets
    files += [camp / "dm" / "state.md", camp / "dm" / "session-prep" / f"session-{nn:02d}-prep.md"]
    if resume:
        files += [log, camp / "dm" / "screen-digest.md"]
    parts, missing = _file_blocks(files)
    if (camp / "players" / "inventory.json").exists():
        parts.append("===== the party's possessions (gear show) =====\n" + _run_script_quiet("gear.py", slug, ["show"]))
    for p in (camp / "dm" / "world.md", camp / "dm" / "threads.md"):
        if p.exists():
            heads = [l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("#")]
            parts.append(f"===== {p.relative_to(REPO)} (headings only: read sections as the brief needs) =====\n" + "\n".join(heads))
    head = (f"[Session start, from the interface: campaign `{slug}`, session {nn:02d}"
            + (" (a RESUME of an interrupted session: continue its live log, go to Step 4)" if resume else "") + ".\n"
            + ("Already done, don't repeat: " + "; ".join(done) + ".\n" if done else "")
            + ("Not there: " + ", ".join(missing) + ".\n" if missing else "")
            + "The files /start-session's Step 2 and the brief need are below, read for you: don't Read them again. "
              "Now run the /start-session skill for this campaign (Skill tool) and follow it, skipping what's done above; "
              "read further DM files only by section, as the brief needs. The player sees none of this message.]")
    return head + "\n\n" + "\n\n".join(parts)


def _file_blocks(paths: list[Path], limit: int = START_FILE_LIMIT) -> tuple[list[str], list[str]]:
    """The files as "===== path =====" blocks (cut at `limit` characters), and the ones that don't exist."""
    parts, missing = [], []
    for p in paths:
        name = str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)
        if not p.exists():
            missing.append(name)
            continue
        text = p.read_text(encoding="utf-8")
        cut = f"\n[… cut at {limit} characters: read the rest by section if you need it]" if len(text) > limit else ""
        parts.append(f"===== {name} =====\n{text[:limit]}{cut}")
    return parts, missing


def close_bundle(slug: str, nn: int, transcript: Path | None) -> str:
    """The files the closing conversation needs, read for it (instead of a dozen Reads and greps): the
    live log, the transcript, the state and world files, the party's sheets and notes, the DM's notes on
    the PCs, session zero (advancement), the last recap (its style), and the inventory."""
    camp = REPO / "campaigns" / slug
    sheets = sorted(p for p in (camp / "players" / "characters").glob("*.md") if p.name.lower() != "readme.md")
    notes = sorted(p for p in (camp / "dm" / "characters").glob("*.md") if p.name.lower() != "readme.md")
    recaps = sorted((camp / "players" / "recaps").glob("session-*.md"))
    files = [camp / "dm" / "session-log" / f"session-{nn:02d}.md"] + ([transcript] if transcript else [])
    files += [camp / "campaign.md", camp / "players" / "session-zero.md", camp / "dm" / "state.md", camp / "dm" / "world.md",
              camp / "players" / "party.md"] + recaps[-1:] + sheets + notes
    parts, _missing = _file_blocks([p for p in files if p is not None])
    if (camp / "players" / "inventory.json").exists():
        parts.append("===== the party's possessions (gear show) =====\n" + _run_script_quiet("gear.py", slug, ["show"]))
    return ("The files the close needs, read for you: don't Read them again (read others by section if you need them).\n\n"
            + "\n\n".join(parts))


def mark_session_closed(slug: str, nn: int) -> bool:
    """After the close: "Sessions played" becomes NN (once; the skill no longer does it by hand)."""
    md = REPO / "campaigns" / slug / "campaign.md"
    text = md.read_text(encoding="utf-8")
    m = re.search(r"(\*\*Sessions played:\*\*\s*)(\d+)", text)
    if not m or int(m.group(2)) >= nn:
        return False
    md.write_text(text[:m.start(2)] + str(nn) + text[m.end(2):], encoding="utf-8")
    return True


def _run_script_quiet(script: str, slug: str, args: list[str]) -> str:
    """Run one of the game scripts for the interface (outside the DM's play mode); its output, or the error."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_DM_MODE"}
    r = subprocess.run([sys.executable, str(REPO / "scripts" / script), "-c", slug] + args,
                       cwd=REPO, env=env, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def session_in_progress(slug: str | None) -> int | None:
    """The number of the campaign's session being played: its live log exists, and the session
    hasn't been closed yet (closing increments "Sessions played"). None otherwise."""
    md = REPO / "campaigns" / str(slug) / "campaign.md"
    if not slug or not md.is_file():
        return None
    text = md.read_text(encoding="utf-8")
    played = re.search(r"\*\*Sessions played:\*\*\s*(\d+)", text)
    nn = (int(played.group(1)) if played else 0) + 1
    return nn if (REPO / "campaigns" / str(slug) / "dm" / "session-log" / f"session-{nn:02d}.md").exists() else None


def write_transcript(slug: str, nn: int, history: list[dict[str, Any]]) -> Path | None:
    """The session's chat as the player saw it (.play/transcripts/<slug>-session-NN.md), from the
    last /start-session on: the closing conversation's memory of what was said. None if empty."""
    start = max((i for i, h in enumerate(history)
                 if h.get("role") == "player" and str(h.get("text", "")).startswith("/start-session")), default=0)
    lines: list[str] = []
    for h in history[start:]:
        role, text = h.get("role"), str(h.get("text") or "").strip()
        if role == "player" and text:
            lines.append(f"**Player:** {text}")
        elif role == "dm" and text:
            lines.append(f"**DM:** {text}")
        elif role == "log":
            events = [str(e.get("text", e)) if isinstance(e, dict) else str(e) for e in h.get("events") or []]
            lines.append(f"*({h.get('title') or 'combat log'})*" + "".join(f"\n- {e}" for e in events))
        elif role == "system" and text:
            lines.append(f"*({text})*")
    if not lines:
        return None
    path = STATE / "transcripts" / f"{slug}-session-{nn:02d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {campaign_title(slug)}, session {nn:02d}: transcript\n\n" + "\n\n".join(lines) + "\n",
                    encoding="utf-8")
    return path


def player_part(text: str) -> str | None:
    """What the player wrote in a message the DM received: None for the interface's own messages,
    the player's text without the recap the interface puts in front of it."""
    t = text.lstrip()
    if t.startswith(RECAP_PREFIX):
        end = t.find("]\n\n")
        return t[end + 3:].lstrip() if end >= 0 else None
    return None if t.startswith(INTERFACE_PREFIXES) else text


def is_interface_message(text: str) -> bool:
    """A message the interface sent the DM (a combat step with its DM-only briefing, a campaign switch),
    not something the player wrote: never shown in the chat, live or when history is reloaded."""
    return text.lstrip().startswith(INTERFACE_PREFIXES)


def exchange_kind(text: str) -> str:
    """What an exchange was, from the message the engine sent."""
    t = text.lstrip()
    if t.startswith("[Combat step"):
        return "combat-hidden" if "hasn't noticed" in t[:400] else "combat-step"
    if t.startswith("[Player's turn"):
        return "player-turn"
    if t.startswith("[The player is switching"):
        return "switch"
    if t.startswith("[The fight is over"):
        return "combat-end"
    if t.startswith("[The session is ending"):
        return "close-flush"
    if t.startswith("[Close the session"):
        return "command:end-session"
    if t.startswith("[Session start"):
        return "command:start-session"
    if t.startswith("/"):
        return "command:" + t.split()[0][1:]
    if t.lower().rstrip(".!") in ("next", "end turn"):
        return "go-signal"
    return "player"


def _tool_summary(name: str, inp: dict[str, Any]) -> str:
    """A short description of a tool call: the command for Bash, the file for Read/Edit, etc."""
    if name == "Bash":
        return str(inp.get("command", ""))[:300]
    if name in ("Read", "Write", "Edit", "Glob", "Grep"):
        return str(inp.get("file_path") or inp.get("pattern") or inp.get("path") or "")[:200]
    if name in ("Agent", "Task"):
        return str(inp.get("subagent_type") or "") + ": " + str(inp.get("description") or "")[:120]
    if name == "Skill":
        return str(inp.get("skill") or inp.get("command") or "")
    if name.startswith("mcp__"):
        return json.dumps(inp, separators=(",", ":"))[:300]
    return ""


def _error_line(content: Any) -> str:
    """The first meaningful line of a failed tool result."""
    body = content if isinstance(content, str) else json.dumps(content)
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    for pick in (lambda l: "combat error:" in l, lambda l: "Error" in l or "error:" in l,
                 lambda l: "error" in l.lower() and not l.startswith("Exit code")):
        hit = [i for i, l in enumerate(lines) if pick(l)]
        if hit:
            return _with_reason(lines, hit[-1])   # the last one: a traceback ends with the actual exception
    first = next((i for i, l in enumerate(lines) if "invalid arguments" in l), 0)
    return _with_reason(lines, first) if lines else ""


def _with_reason(lines: list[str], i: int) -> str:
    """Line i, plus the next one when it ends in a colon ("invalid arguments:" + what was wrong)."""
    text = lines[i]
    if text.endswith(":") and i + 1 < len(lines):
        text += " " + lines[i + 1]
    return text[:240]


class Engine:
    """One headless DM session. `send()` blocks until the reply to that message is complete."""

    QUIET_NOTICE = 60   # seconds without any event before the frontend hears "still waiting"
    last_event = 0.0
    COMPACT_AT = 120_000   # context tokens per call above which the conversation gets compacted between turns
    COMPACT_AFTER_FIGHT_AT = 100_000   # lower right after a fight: its tool calls and logs are dead weight then
    COMPACT_IN_FIGHT_AT = 180_000      # during a fight only when it's this large: wait for the fight's end
    context_tokens = 0
    combat_rules_read = False   # combat.md is read when a fight starts, not with the session's table rules

    def compact_if_large(self, after_fight: bool = False) -> bool:
        """Between turns: if the conversation has grown past COMPACT_AT tokens of context (or
        COMPACT_AFTER_FIGHT_AT when a fight just ended, a natural scene break), compact it (`/compact`,
        keeping what the table needs). Every later call then reads far less. Returns whether it
        compacted. Its text is never shown."""
        limit = self.COMPACT_AFTER_FIGHT_AT if after_fight else self.COMPACT_AT
        if self.role != "dm" or self.context_tokens < limit or not self.alive() or self.busy:
            return False
        self.hold()
        try:
            ok = self.send(COMPACT_PROMPT, label="tidying the DM's notes (a minute or two; you can keep typing, your message goes out right after)")
        finally:
            self.release(publish=False)
        if ok:
            self.context_tokens = 0
            self.combat_rules_read = False   # compaction drops what the DM read
        return ok

    def __init__(self, on_event: EventHandler, model: str | None = None, effort: str = 'medium', debug: bool = False,
                 record_session: bool = False, role: str = "dm", system_prompt: str | None = None,
                 campaign: str | None = None) -> None:
        """Args:
            on_event: called with every event (from a reader thread).
            model: model alias or id for `claude --model`, or None for the default.
            effort: thinking effort for `claude --effort`.
            debug: also emit debug events for tools and subagents.
            record_session: log the session (.play/sessions.log), so the picker can continue it.
                Only the real interface (web.py) sets it; tests and scripts must not, or
                the picker would offer their throwaway conversations.
            role: "dm" (the full DM: Claude Code's prompt, tools, skills and the project) or "runner"
                (the combat runner: a lean process with only `system_prompt` and the dm tools).
            system_prompt: the runner's whole system prompt.
            campaign: the game tools' default campaign (CLAUDE_DM_CAMPAIGN), so a fresh process's
                first tool call doesn't fail for want of one.
        """
        self.campaign = campaign
        self.on_event = on_event
        self.record_session = record_session
        self.role = role
        self.system_prompt = system_prompt
        self.telemetry_session: str | None = None   # a runner logs under the main DM's session
        # The DM has engaged combat in this session (used a combat tool, or the interface ran a step).
        # Until then the interfaces don't show a fight, even if one is saved from an earlier session.
        self.combat_engaged = False
        self.model = model
        self.effort = effort
        self.debug = debug
        self.debug_tag = "" if role == "dm" else "runner"   # whose lines these are (set by the runners)
        self._tool_names: dict[str, str] = {}              # tool_use id → name (debug: how much of a result to show)
        self.proc: subprocess.Popen[str] | None = None
        self.session_id: str | None = None
        self.stderr_lines: list[str] = []
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.waiting = False   # a player turn is in progress
        self._held: list[dict[str, Any]] | None = None   # DM text held back (a hidden actor's step)
        self._tel: dict[str, Any] | None = None           # telemetry of the exchange in progress
        self._cost_seen = 0.0                             # the process's running cost at the last reply
        self.telemetry = True
        self.armed = False     # the echo of the player's message has been seen
        self._reset()

    def _reset(self) -> None:
        """Forget the per-reply streaming state."""
        self.streamed: set[str | None] = set()
        self.current_msg = None
        self.in_text = False

    def dbg(self, line: str) -> None:
        """A debug line (only in debug mode), tagged with the process it comes from."""
        if self.debug:
            self.emit(type="debug", line=(f"{{{self.debug_tag}}} " if self.debug_tag else "") + line)

    def emit(self, **ev: Any) -> None:
        """Send an event to the frontend; errors in the handler never reach the reader thread.
        While text is held (see hold()), DM text events are kept back instead."""
        with self.lock:
            if self._held is not None and ev["type"] in ("text_start", "text", "text_end"):
                self._held.append(ev)
                return
        self._send_event(ev)

    def hold(self) -> None:
        """Keep the DM's text back until release(), e.g. while a hidden actor's turn is resolved."""
        with self.lock:
            self._held = []

    def held_text(self) -> str:
        """The text held back so far (without releasing it)."""
        with self.lock:
            return "".join(ev.get("delta", "") for ev in self._held or [] if ev["type"] == "text")

    def held_acted(self) -> bool:
        """Whether the reply being held made any tool call."""
        with self.lock:
            return any(ev["type"] == "_tool" for ev in self._held or [])

    def scrub_held(self, marker: str) -> None:
        """Remove a marker from the held text (it must never reach the player)."""
        with self.lock:
            for ev in self._held or []:
                if ev["type"] == "text" and marker in ev.get("delta", ""):
                    ev["delta"] = ev["delta"].replace(marker, "")

    def release(self, publish: bool, after_tools: bool = False) -> str:
        """Stop holding text; show what was held back if `publish`, else drop it. With after_tools,
        only the text written after the reply's last tool call is shown: whatever the DM wrote before
        it is its own reasoning (e.g. weighing the tactical options), not narration."""
        with self.lock:
            held, self._held = self._held or [], None
        if after_tools:
            marks = [i for i, ev in enumerate(held) if ev["type"] == "_tool"]
            if marks:
                tail = held[marks[-1] + 1:]
                if not any(ev["type"] == "text" and ev.get("delta", "").strip() for ev in tail):
                    # nothing after the last tool call (e.g. it narrated, then logged): the last text
                    # block before that call is the narration
                    start = marks[-2] + 1 if len(marks) > 1 else 0
                    tail = held[start:marks[-1]]
                held = tail
        if publish:
            for ev in held:
                if ev["type"] != "_tool":
                    self._send_event(ev)
        elif self.debug:
            dropped = "".join(ev.get("delta", "") for ev in held if ev["type"] == "text").strip()
            if dropped:
                self.dbg(f"[not shown] {dropped[:2000]}")
        return "".join(ev.get("delta", "") for ev in held if ev["type"] == "text") if publish else ""

    def _send_event(self, ev: dict[str, Any]) -> None:
        """Pass one event to the frontend's handler."""
        try:
            self.on_event(ev)
        except Exception:
            pass

    @property
    def busy(self) -> bool:
        """Whether a player turn is in progress."""
        return self.waiting

    # --- process ---
    def start(self, resume: str | None = None) -> None:
        """Start `claude -p` with stream-json in/out, optionally resuming a session, plus the reader threads."""
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--include-partial-messages", "--replay-user-messages",
               "--permission-mode", "dontAsk"]
        if self.role == "runner":   # ~9k tokens of context instead of the full DM's ~60k + the conversation
            cmd += ["--allowedTools", "mcp__dm", "--tools", "", "--disable-slash-commands", "--setting-sources", "",
                    "--system-prompt", self.system_prompt or RUNNER_PROMPT, "--no-session-persistence"]
            resume = None
        else:
            lock = (f"\n- THIS CONVERSATION PLAYS ONLY THE CAMPAIGN '{self.campaign}' (campaigns/{self.campaign}/). Other "
                    f"campaigns' folders are blocked for you and your subagents; never look into them. Give file "
                    f"searches a path (campaigns/{self.campaign}/… or library/…).") if self.campaign else ""
            cmd += ["--tools", DM_TOOLS, "--allowedTools", *ALLOWED_TOOLS,
                    "--append-system-prompt", WRAPPER_PROMPT + lock]
        if self.model:
            cmd += ["--model", self.model]
        if self.effort:
            cmd += ["--effort", self.effort]
        if resume:
            cmd += ["--resume", resume]
            self.session_id = resume
        cmd += ["--mcp-config", str(REPO / ".mcp.json"), "--strict-mcp-config"]
        # load the game tools up front (no tool-search round trip before the first use of each)
        env = dict(os.environ, CLAUDE_DM_MODE="play", ENABLE_TOOL_SEARCH="false")
        if self.campaign:
            env["CLAUDE_DM_CAMPAIGN"] = self.campaign
        self.proc = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        threading.Thread(target=self._drain_stderr, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _drain_stderr(self, proc: subprocess.Popen[str]) -> None:
        """Collect the process's stderr (and emit it in debug mode)."""
        assert proc.stderr is not None
        for line in proc.stderr:
            self.stderr_lines.append(line.rstrip())
            self.dbg(f"[stderr] {line.rstrip()}")

    def alive(self) -> bool:
        """Whether the claude process is running."""
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        """Close stdin and wait for the process to exit (kill it after 10 s)."""
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                assert proc.stdin is not None
                proc.stdin.close()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()

    def restart(self) -> None:
        """Kill the process and start it again, resuming the same session."""
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
        self.emit(type="status", label=None)
        self._reset()
        self.done.set()
        self._cost_seen = 0.0   # a new process starts its running total from zero
        self.start(resume=self.session_id)

    def new_session(self) -> None:
        """Stop the process and start a fresh conversation (no resume), e.g. for another campaign."""
        self.combat_engaged = False
        self.stop()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
        self.emit(type="status", label=None)
        self._reset()
        self.done.set()
        self.session_id = None
        self._cost_seen = 0.0
        self.combat_rules_read = False
        self.start()

    def set_effort(self, level: str) -> None:
        """Change the thinking effort; restarts the process and resumes the session."""
        if level not in EFFORTS:
            raise ValueError(level)
        self.effort = level
        self.restart()

    # --- turns ---
    def send(self, text: str, label: str = "thinking") -> bool:
        """Send one player message and block until its reply is complete. False if the process died.
        `label`: the status line the player sees while it runs."""
        proc = self.proc
        if proc is None or proc.poll() is not None or proc.stdin is None:
            return False
        if self.debug and (self.role == "runner" or is_interface_message(text) or text.lstrip().startswith(RECAP_PREFIX)):
            self.dbg(f"[→ sent] {text[:6000]}")   # what the interface told it (step briefings, recaps): hidden otherwise
        with self.lock:
            self.done.clear()
            self.waiting, self.armed = True, False
            self._reset()
            self._tel = {"start": time.time(), "kind": exchange_kind(text), "chars_in": len(text),
                         "tools": {}, "sub_tools": 0, "chars_out": 0}
            self.emit(type="status", label=label)
        proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
        proc.stdin.flush()
        self.last_event, told = time.time(), 0
        while not self.done.wait(0.2):
            if not self.alive():
                break
            quiet = int(time.time() - self.last_event)
            if quiet >= self.QUIET_NOTICE * (told + 1):   # say so once a minute: Claude may be retrying (outage, usage limit)
                told += 1
                self.emit(type="status", label=f"still waiting for Claude: nothing for {quiet} s (it may be retrying)")
        with self.lock:
            self.waiting = False
            if self._tel is not None:   # the process died mid-reply
                self._write_telemetry({"died": True})
        self.emit(type="status", label=None)
        return self.alive()

    def _write_telemetry(self, result: dict[str, Any]) -> None:
        """Append the finished exchange to .play/telemetry.jsonl (never raises)."""
        tel, self._tel = self._tel, None
        if not tel or not self.telemetry:
            return
        tools = list(tel["tools"].values())
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tel["start"])),
               "session": self.telemetry_session or self.session_id, "campaign": self.campaign or active_campaign(),
               "kind": ("runner:" if self.role == "runner" else "") + tel["kind"],
               "seconds": round(time.time() - tel["start"], 1), "effort": self.effort,
               "chars_in": tel["chars_in"], "chars_out": tel["chars_out"],
               "tools": tools, "tool_calls": len(tools), "tool_errors": sum(1 for x in tools if x.get("error")),
               "subagent_tool_calls": tel["sub_tools"]}
        for k in ("num_turns", "duration_ms", "died", "is_error", "subtype"):
            if k in result:
                rec[k] = result[k]
        if result.get("is_error"):   # the error's own text (an API or limit message), to diagnose stalls later
            rec["error_text"] = str(result.get("result") or result.get("errors") or "")[:300]
        if "total_cost_usd" in result:   # Claude Code reports a running total for the process
            total = result["total_cost_usd"] or 0
            rec["cost_usd"] = round(max(0.0, total - self._cost_seen) if total >= self._cost_seen else total, 4)
            rec["process_cost_usd"] = total
            self._cost_seen = total
        usage = result.get("usage") or {}
        if usage:
            rec["tokens"] = {k: usage.get(k, 0) for k in ("input_tokens", "output_tokens",
                                                       "cache_read_input_tokens", "cache_creation_input_tokens")}
        try:
            STATE.mkdir(exist_ok=True)
            with TELEMETRY.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError:
            pass

    # --- stream handling ---
    def _read(self, proc: subprocess.Popen[str]) -> None:
        """Reader thread: parse the stdout event stream and handle each event."""
        assert proc.stdout is not None
        for line in proc.stdout:
            self.last_event = time.time()
            try:
                m = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                self._handle(m)
        self.done.set()

    def _text_start(self) -> None:
        """Open a new block of DM text (once per block)."""
        if not self.in_text:
            self.in_text = True
            self.emit(type="status", label=None)
            self.emit(type="text_start")

    def _text_end(self) -> None:
        """Close the current block of DM text, if one is open."""
        if self.in_text:
            self.in_text = False
            self.emit(type="text_end")

    def _handle(self, m: dict[str, Any]) -> None:
        """Turn one stream-json message into frontend events. Only the main agent's text is passed on;
        tool calls become status labels, and subagent activity is dropped unless debug is on.
        """
        t = m.get("type")
        top = m.get("parent_tool_use_id") is None
        if t == "system" and m.get("subtype") == "init":
            dm = next((x for x in m.get("mcp_servers") or [] if x.get("name") == "dm"), None)
            if not dm or dm.get("status") != "connected":
                self.emit(type="error", message="The game tools (dice, combat, world) didn't start: "
                                                f"{(dm or {}).get('status', 'not loaded')}. Check scripts/mcp_server.py.")
            sid = m.get("session_id")
            if sid and sid != self.session_id:
                self.session_id = sid
                if self.record_session:
                    save_session(sid)
                self.emit(type="session", id=sid)
        elif t == "user" and m.get("isReplay"):
            self.armed = True
        elif t == "stream_event":
            e = m.get("event", {})
            et = e.get("type")
            if et == "message_start" and top:
                self.current_msg = e.get("message", {}).get("id")
            elif et == "content_block_start":
                block = e.get("content_block", {})
                if block.get("type") == "tool_use":
                    self._text_end()
                    if top and self._held is not None:
                        self._held.append({"type": "_tool"})   # text before this is the DM thinking out loud
                    self.emit(type="status", label=flavor(block.get("name"), not top))
                    self.dbg(f"[tool{'' if top else ' (sub)'}] {block.get('name')}")
            elif et == "content_block_delta" and top:
                d = e.get("delta", {})
                if d.get("type") == "text_delta":
                    self._text_start()
                    self.streamed.add(self.current_msg)
                    self.emit(type="text", delta=d.get("text", ""))
            elif et == "content_block_stop" and top:
                self._text_end()
        elif t == "assistant":
            content = m.get("message", {}).get("content", [])
            mid = m.get("message", {}).get("id")
            u = m.get("message", {}).get("usage") or {}
            if top and u:   # how much context the last call read: the cue for compacting
                self.context_tokens = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens",
                                                                       "cache_creation_input_tokens"))
            for c in content:
                if c.get("type") == "tool_use" and is_combat_tool(c.get("name", ""), c.get("input") or {}):
                    self.combat_engaged = True
                if c.get("type") == "tool_use" and reads_combat_rules(c.get("name", ""), c.get("input") or {}):
                    self.combat_rules_read = True
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            tel = self._tel
            if tel is not None:
                for c in content:
                    if c.get("type") != "tool_use":
                        continue
                    if top:
                        tel["tools"][c.get("id")] = {"name": c.get("name"),
                                                     "call": _tool_summary(c.get("name", ""), c.get("input") or {})}
                    else:
                        tel["sub_tools"] += 1
                if top:
                    tel["chars_out"] += sum(len(x) for x in texts)
            if top and texts and mid not in self.streamed:
                self._text_start()
                self.emit(type="text", delta="\n".join(texts))
                self._text_end()
            elif self.debug and not top and texts:
                self.dbg(f"[subagent] {' '.join(texts)[:400]}")
            for c in content:
                if c.get("type") == "tool_use":
                    self._tool_names[str(c.get("id"))] = str(c.get("name", ""))
                    if self.debug:
                        game = str(c.get("name", "")).startswith("mcp__dm__")
                        self.dbg(f"[input] {json.dumps(c.get('input'))[:2000 if game else 300]}")
        elif t == "user":
            for c in (m.get("message", {}).get("content") or []):
                if not (isinstance(c, dict) and c.get("type") == "tool_result"):
                    continue
                body = c.get("content")
                rec = (self._tel or {}).get("tools", {}).get(c.get("tool_use_id"))
                text = body if isinstance(body, str) else json.dumps(body)
                if rec is not None and (c.get("is_error") or "combat error:" in text or "Traceback" in text):
                    rec["error"] = _error_line(body)
                if self.debug:
                    if isinstance(body, list):   # content blocks: show their text, not the JSON around it
                        text = "\n".join(str(b.get("text", "")) for b in body if isinstance(b, dict)) or text
                    game = self._tool_names.get(str(c.get("tool_use_id")), "").startswith("mcp__dm__")
                    self.dbg(f"[result] {text[:4000 if game else 300]}")
        elif t == "result":
            self._text_end()
            self.emit(type="status", label=None)
            sid = m.get("session_id") or self.session_id
            if sid:
                self.session_id = sid
                if self.record_session:
                    save_session(sid)
            if m.get("is_error"):
                why = str(m.get("result") or "; ".join(map(str, m.get("errors") or [])) or m.get("subtype") or "")[:300]
                self.emit(type="error", message=f"The DM hit an error: {why or 'unknown'}. Try again"
                                                 " (\"continue\" resumes an interrupted combat step).")
            if self.waiting and self.armed and self._tel is not None:
                self._write_telemetry(m)
            if self.waiting and self.armed:
                self.done.set()
                self.emit(type="turn_end", solicited=True)
            elif not self.waiting:
                self._reset()
                self.emit(type="turn_end", solicited=False)


# ---------- campaigns and combat (player-safe views) ----------

def _combat_module() -> ModuleType:
    """Import scripts/combat.py as a module (it isn't a package)."""
    spec = importlib.util.spec_from_file_location("combat", REPO / "scripts" / "combat.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gear_module() -> ModuleType:
    """Import scripts/gear.py as a module (for the UI's gear views)."""
    spec = importlib.util.spec_from_file_location("gear", REPO / "scripts" / "gear.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stash_markdown(camp: str) -> str:
    """The party stash (every container that isn't a character) as Markdown, for the UI's Party stash tab."""
    mod = _gear_module()
    try:
        return str(mod.stash_markdown(camp))
    except mod.GearError as e:
        return f"*The stash can't be shown: {e}*"


GEAR_MARKERS = re.compile(r"<!-- gear:begin.*?<!-- gear:end -->[ \t]*\n?", re.S)   # the old generated blocks


def sheet_with_gear(camp: str, sheet: Path) -> str:
    """A character sheet for the UI's Character tab, its Gear section generated from the inventory
    (under the sheet's '## Gear' heading; before the backstory, or at the end, if it has none)."""
    text = GEAR_MARKERS.sub("", sheet.read_text(encoding="utf-8"))
    mod = _gear_module()
    try:
        gear = mod.character_gear_markdown(camp, str(sheet.relative_to(REPO / "campaigns" / camp)))
    except mod.GearError as e:
        gear = f"*The gear can't be shown: {e}*"
    if gear is None:
        return text
    m = re.search(r"^## Gear[^\n]*\n", text, re.M)
    if m:
        return text[:m.end()] + gear + "\n\n" + text[m.end():]
    m = re.search(r"^## Backstory", text, re.M)
    block = f"## Gear\n{gear}\n\n"
    return text[:m.start()] + block + text[m.start():] if m else text.rstrip("\n") + "\n\n" + block


SESSION_CAMPAIGNS = STATE / "session-campaigns.json"


def is_campaign(name: str | None) -> bool:
    """A real campaign folder: has campaign.md, and isn't _template or a test folder (_test_*, _zz_*)."""
    return bool(name) and not str(name).startswith("_") and (REPO / "campaigns" / str(name) / "campaign.md").is_file()


def remember_campaign(session_id: str | None, campaign: str | None) -> None:
    """Record which campaign a session plays (.play/session-campaigns.json), so the picker can continue it."""
    if not session_id or not is_campaign(campaign):
        return
    try:
        data = json.loads(SESSION_CAMPAIGNS.read_text()) if SESSION_CAMPAIGNS.exists() else {}
    except ValueError:
        data = {}
    if data.get(session_id) != campaign:
        data[session_id] = campaign
        STATE.mkdir(exist_ok=True)
        SESSION_CAMPAIGNS.write_text(json.dumps(data, indent=1))


def active_campaign(explicit: str | None = None) -> str | None:
    """The given campaign, or the one touched most recently (fight, session log, campaign file)."""
    if explicit:
        return explicit
    best: str | None = None
    best_t = 0.0
    for camp in (REPO / "campaigns").iterdir():
        if not is_campaign(camp.name):
            continue
        paths = [camp / "campaign.md", camp / "dm" / "combat" / "current.json"]
        paths += list((camp / "dm" / "session-log").glob("session-*.md"))
        t = max((p.stat().st_mtime for p in paths if p.exists()), default=0)
        if t > best_t:
            best, best_t = camp.name, t
    return best


def list_campaigns() -> list[dict[str, Any]]:
    """All playable campaigns (folders with a campaign.md, not _template), most recently played first:
    {slug, title, status, sessions_played, last_played (YYYY-MM-DD HH:MM or None), session (the
    conversation to continue, or None)}."""
    root = REPO / "campaigns"
    latest = campaign_sessions()
    out = []
    for d in sorted(root.iterdir()):
        if not (d.is_dir() and is_campaign(d.name)):
            continue
        text = (d / "campaign.md").read_text(encoding="utf-8")
        status = re.search(r"\*\*Status:\*\*\s*([^\n]+)", text)
        played = re.search(r"\*\*Sessions played:\*\*\s*(\d+)", text)
        sid, when = latest.get(d.name, (None, None))
        out.append({"slug": d.name, "title": campaign_title(d.name),
                    "status": status.group(1).strip() if status else "", "sessions_played": int(played.group(1)) if played else 0,
                    "last_played": when, "session": sid if sid and transcript_path(sid).exists() else None})
    out.sort(key=lambda c: c["last_played"] or "", reverse=True)
    return out


def campaign_sessions() -> dict[str, tuple[str, str]]:
    """For each campaign, its most recent conversation: {slug: (session id, when)}, from
    .play/sessions.log (the order) and .play/session-campaigns.json (which campaign each one plays)."""
    try:
        owner = json.loads(SESSION_CAMPAIGNS.read_text()) if SESSION_CAMPAIGNS.exists() else {}
    except ValueError:
        owner = {}
    log = STATE / "sessions.log"
    out: dict[str, tuple[str, str]] = {}
    for line in (log.read_text().splitlines() if log.exists() else []):
        parts = line.split()
        if len(parts) >= 3 and owner.get(parts[2]):
            out[owner[parts[2]]] = (parts[2], f"{parts[0]} {parts[1]}")
    return out


def slugify(name: str) -> str:
    """A campaign folder name from a title: 'The Rose & Thorn' → 'the-rose-thorn'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")[:40]


def campaign_title(camp: str | None) -> str:
    """The campaign's title from the '# …' line of campaign.md, or a fallback."""
    f = REPO / "campaigns" / camp / "campaign.md" if camp else None
    if f and f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return camp or "Claude DM"




def _light_view(cm: ModuleType, st: dict[str, Any]) -> dict[str, Any] | None:
    """Lighting for the browser map, from the (first) PC's perspective, or None when the fight has
    plain normal light. Light sources are shown where they are; a hidden carrier isn't named."""
    V = cm.V
    if not V.has_lighting(st):
        return None
    pc = next((c for c in st["tokens"] if c["side"] == "pc" and not c.get("removed")), None)
    view = V.player_view(st, pc)
    view["pc"] = pc["name"] if pc else None
    view["senses"] = V.describe_senses(pc) if pc else ""
    srcs = []
    for s in V.light_state(st).get("sources", []):
        cs = V.source_cells(st, s)
        if not cs or s.get("steps"):
            continue
        carrier = next((c for c in st["tokens"] if c["token"] == s.get("on")), None)
        srcs.append({"x": cs[0][0], "y": cs[0][1], "kind": s["kind"],
                     "carried": bool(carrier), "by": carrier["name"] if carrier and not carrier.get("hidden") else None})
    view["sources"] = srcs
    return view


def combat_snapshot(camp: str | None) -> dict[str, Any] | None:
    """Player-safe state of the current fight, or None. The web UI draws the map itself from `map`."""
    if not camp:
        return None
    state = REPO / "campaigns" / camp / "dm" / "combat" / "current.json"
    if not state.exists():
        return None
    try:
        st = json.loads(state.read_text())
        cm = _combat_module()
    except Exception:
        return None
    rows = []
    for c in cm.order(st):
        if c.get("removed") or c.get("hidden"):
            continue
        conditions = cm.R.labels(c, st)
        if c.get("nonlethal"):
            conditions.append(f"{c['nonlethal']} nonlethal" if c["side"] in cm.FRIENDLY else "hurt (nonlethal)")
        rows.append({
            "name": c["name"], "token": c["token"], "side": c["side"], "init": c["init"],
            "status": cm.status(c), "conditions": conditions,
            "fallen": c["hp"] <= 0 and c["side"] not in cm.FRIENDLY,
            "current": c["token"] == st.get("turn"),
        })
    used = {ch for row in st["grid"] for ch in row}
    terrain = [name for ch, name in cm.TERRAIN_NAMES.items() if ch in used]
    # Player-safe map data for the browser to draw: terrain plus visible tokens only.
    by_token = {r["token"]: r for r in rows}
    tokens = []
    for c in st["tokens"]:
        r = by_token.get(c["token"])
        if r:
            pc = next((o for o in st["tokens"] if o["side"] == "pc" and not o.get("removed")), None)
            unseen = bool(pc and c is not pc and cm.V.has_lighting(st) and cm.V.concealment(st, pc, c)[0] >= 50)
            tokens.append(dict(r, x=c["x"], y=c["y"], size=c.get("size", 1), unseen=unseen))
    grid_map = {"w": st["w"], "h": st["h"], "grid": st["grid"], "tokens": tokens,
                "terrain_names": cm.TERRAIN_NAMES, "light": _light_view(cm, st),
                "marks": cm.turn_marks(st)}   # the latest turn: movement, areas, targets (never a hidden actor's)
    turn = next((r["name"] for r in rows if r["current"]), None)
    cur = next((r for r in rows if r["current"]), None)
    # Who plays on the next go signal: the first live actor after the turn pointer (the pointer
    # marks who is acting or acted last). Hidden actors are skipped, because the DM resolves them
    # silently within the step, and naming them would give them away.
    nxt = _first_visible_after(st, st.get("turn"))
    upcoming = {"name": nxt["name"], "token": nxt["token"], "side": nxt["side"]} if nxt else None
    pc_left = None   # the PC's unused actions, so End turn can ask first
    live = next((c for c in st["tokens"] if c["token"] == st.get("turn")), None)
    if live and live["side"] == "pc" and cm.can_act(live):
        try:
            unused = [k for k in ("standard", "move") if not cm.can_take(st, live, k)]
            pc_left = {"text": cm.actions_left(st, live), "main": unused}
        except Exception:
            pc_left = None
    return {
        "active": True, "round": st.get("round", 1), "turn": turn, "initiative": rows,
        # whose turn it is, for the End turn / Next button ("pc" = the player acts now)
        "turn_side": cur["side"] if cur else None, "turn_token": cur["token"] if cur else None,
        "upcoming": upcoming, "pc_actions_left": pc_left, "surprise": bool(st.get("surprise")),
        "over": bool(cm.fight_over(st)),   # no enemy standing, nobody dying: the button says End combat
        "awaiting": st.get("awaiting"),
        "events": [{"round": e.get("round"), "text": e.get("text", "")} for e in st.get("events", [])],
        "terrain": terrain,
        "map": grid_map,
    }


def last_combat_events(camp: str) -> list[dict[str, Any]]:
    """Events of the most recently archived fight (for the 'fight is over' summary)."""
    arch = REPO / "campaigns" / camp / "dm" / "combat" / "archive"
    files = sorted(arch.glob("*.json"), key=lambda p: p.stat().st_mtime) if arch.exists() else []
    if not files:
        return []
    try:
        return [{"round": e.get("round"), "text": e.get("text", "")}
                for e in json.loads(files[-1].read_text()).get("events", [])]
    except (OSError, ValueError):
        return []


# ---------- history of a resumed session ----------

def transcript_path(session_id: str) -> Path:
    """Where Claude Code keeps the transcript of a session in this repo."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(REPO))
    return Path.home() / ".claude" / "projects" / slug / f"{session_id}.jsonl"


def load_history(session_id: str | None) -> list[dict[str, str]]:
    """The player's messages and the DM's text from a session transcript, oldest first."""
    path = transcript_path(session_id) if session_id else None
    if not path or not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("isSidechain") or r.get("isCompactSummary"):   # a compaction's summary isn't the player's
            continue
        msg = r.get("message") or {}
        if r.get("type") == "user" and isinstance(msg.get("content"), str):
            text = msg["content"]
            if text.startswith("<task-notification") or text.startswith("<local-command"):
                continue
            text = player_part(text) or ""   # the interface's messages and recaps aren't the player's
            if "<command-name>" in text:
                name = re.search(r"<command-name>(.*?)</command-name>", text, re.S)
                args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
                text = f"{name.group(1).strip() if name else ''} {args.group(1).strip() if args else ''}".strip()
                text = player_part(text) or ""   # /compact is the interface's
            if text.strip():
                out.append({"role": "player", "text": text})
        elif r.get("type") == "assistant":
            texts = [c.get("text", "") for c in msg.get("content", []) if c.get("type") == "text"]
            if texts:
                if out and out[-1]["role"] == "dm":
                    out[-1]["text"] += "\n\n" + "\n".join(texts)
                else:
                    out.append({"role": "dm", "text": "\n".join(texts)})
    return out


# ---------- engine-driven combat steps ----------
# The interface, not the DM, moves the turn pointer: on the player's go signal it runs
# `combat.py next` itself and asks the DM to resolve exactly the one actor it landed on.
# (`next` is refused inside the DM's own process: CLAUDE_DM_MODE=play.)

GO_SIGNALS = ("next", "end turn")
# "carry on" phrasings: a go signal too, but only while it isn't the PC's turn (there, the player
# may mean something else, and ending their turn by accident would be worse than asking)
RESUME_SIGNALS = ("continue", "resume", "go on", "carry on", "please continue", "please resume", "keep going")


def is_go_signal(text: str, st: dict[str, Any] | None = None) -> bool:
    """Whether the player's message is just a go signal ("next", "end turn", or with the fight's
    state given, "continue"/"resume" while an NPC holds the turn: e.g. after an interrupted step)."""
    t = text.strip().lower().rstrip(".!")
    if t in GO_SIGNALS:
        return True
    if t in RESUME_SIGNALS and st and st.get("turn") is not None:
        cur = next((c for c in st.get("tokens", []) if c["token"] == st["turn"]), None)
        return bool(cur and cur["side"] != "pc")
    return False


def ends_turn(text: str) -> bool:
    """Whether a longer message ends with "end turn" (a whole turn declared at once)."""
    return re.search(r"\bend turn[.!]?\s*$", text.strip(), re.IGNORECASE) is not None


def combat_state(camp: str | None) -> dict[str, Any] | None:
    """The raw current.json of the campaign's fight (DM data, never sent to the player), or None."""
    if not camp:
        return None
    try:
        return json.loads((REPO / "campaigns" / camp / "dm" / "combat" / "current.json").read_text())
    except (OSError, ValueError):
        return None


def _first_visible_after(st: dict[str, Any], token: str | None) -> dict[str, Any] | None:
    """The first creature still in the fight, not hidden, that acts after `token` (None: from the top)."""
    cm = _combat_module()
    full = cm.order(st)
    toks = [c["token"] for c in full]
    start = toks.index(token) if token in toks else -1
    for k in range(1, len(full) + 1):
        c = full[(start + k) % len(full)]
        wraps = start >= 0 and start + k >= len(full)
        if cm.in_fight(c) and not c.get("hidden") and (wraps or not cm.surprised(st, c)):
            return c
    return None


def step_due(camp: str | None, text: str) -> bool:
    """After an ordinary exchange: should the interface run a combat step on its own? Yes when the
    PC's turn is over (the DM ran `combat.py endturn`, or the message ended in "end turn"), or when
    the fight was just set up: the first turns start right after the setup reply, whoever is first."""
    st = combat_state(camp)
    if not st or st.get("awaiting"):
        return False
    turn = st.get("turn")
    by_tok = {c["token"]: c for c in st.get("tokens", [])}
    if turn is None:   # the fight was just set up (the PCs are in): the turns start right away
        return any(t["side"] == "pc" for t in st.get("tokens", []))
    pc_up = by_tok.get(turn, {}).get("side") == "pc"
    return pc_up and (st.get("end_turn") == turn or ends_turn(text))


def log_briefing(camp: str, st: dict[str, Any], c: dict[str, Any]) -> None:
    """Keep each step's DM briefing (tactical options, turn plans, sight) in the campaign's DM-only
    combat folder, so a decision can be checked afterwards (dm/combat/briefings.jsonl; a new fight
    starts the file over)."""
    path = REPO / "campaigns" / camp / "dm" / "combat" / "briefings.jsonl"
    try:
        lines = path.read_text().splitlines() if path.exists() else []
        if lines and json.loads(lines[0]).get("started") != st.get("started"):
            lines = []
        lines.append(json.dumps({"started": st.get("started"), "round": st.get("round"), "token": c["token"],
                                 "name": c["name"], "briefing": c.get("_ctx", ""), "sight": c.get("_sight", "")}))
        path.write_text("\n".join(lines) + "\n")
    except (OSError, ValueError):   # never block a step on the log
        pass


def fight_over(camp: str | None) -> str | None:
    """Why the campaign's fight is over (no enemy left standing, nobody dying), or None."""
    st = combat_state(camp)
    return _combat_module().fight_over(st) if st else None


def end_fight(camp: str) -> str:
    """Run `combat.py end` for the interface: XP, PC HP to the sheets, the log into the session log,
    the state archived. Returns its report (DM only)."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_DM_MODE"}
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "combat.py"), "-c", camp, "end"],
                       cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "combat.py end failed")
    return r.stdout.strip()


END_COMBAT = "end combat"


def fight_over_prompt(why: str, report: str, said: str | None = None) -> str:
    """The main DM's briefing when the player ended a finished fight (the End combat button, or
    their next message): the interface already ran combat_end. `said`: what the player wrote, if
    it was more than "end combat"."""
    then = (f"\nThe player's message right after the fight (answer it as part of the aftermath):\n{said}"
            if said and said.strip().lower().rstrip(".!") != END_COMBAT else "")
    return (f"[The fight is over ({why}), so the interface ended the encounter (combat_end already ran; don't run it "
            f"again):\n{report}\nNarrate the aftermath briefly from the player's point of view, log the loot and "
            f"consequences, and do the checkpoint (dm-procedures.md, \"Combat end\"). Then stop at the player's next "
            f"decision.]{then}")


def _run_next(camp: str) -> str:
    """Run `combat.py next` for the interface (outside the DM's play-mode restriction)."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_DM_MODE"}
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "combat.py"), "-c", camp, "next"],
                       cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "combat.py next failed")
    return r.stdout.strip()


def _sight(camp: str, st: dict[str, Any], tok: str) -> str:
    """The actor's `combat.py sight` report when the fight has lighting set up, else ""."""
    L = st.get("light") or {}
    if L.get("ambient", "normal") == "normal" and not L.get("grid") and not L.get("sources"):
        return ""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_DM_MODE"}
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "combat.py"), "-c", camp, "sight", tok],
                       cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode:
        return ""
    return ("\nWhat it sees (use it: fight from where it sees and isn't seen, go for light sources if darkness favors it. "
            "An enemy out of sight hasn't vanished: unless it's afraid or its nature says hide, go where it was last seen, "
            "close in until it can see it, or bring light; don't hold back or defend against nothing):\n" + r.stdout.strip())


# Who's who, for the narration: the runners only see numbers, and invented armour ("glances off her
# armour" on an unarmoured monk) breaks the fiction. Built from the sheets (race / class), the
# inventory (what's worn), the stat blocks' Gear line, and what's in hand right now.
CAST_NOTE = ("Who's who, for the narration (describe only this gear: no armor listed means none; never invent "
             "armor, shields or weapons; a hidden creature isn't described until it's revealed):")


def _ref_text(ref: str) -> str:
    p = REPO / ref
    try:
        return p.read_text(encoding="utf-8") if p.is_file() else ""
    except OSError:
        return ""


def cast_list(st: dict[str, Any]) -> str:
    """One line per combatant: what it is, what it wears, what it holds."""
    cm = _combat_module()
    camp = next((Path(t["ref"]).parts[1] for t in st.get("tokens", []) if str(t.get("ref") or "").startswith("campaigns/")), None)
    inv: dict[str, Any] = {}
    gear_mod = None
    if camp and (REPO / "campaigns" / camp / "players" / "inventory.json").exists():
        try:
            gear_mod = _gear_module()
            inv = gear_mod.load_inv(camp)
        except Exception:
            gear_mod, inv = None, {}
    lines = [CAST_NOTE]
    for t in st.get("tokens", []):
        if t.get("removed"):
            continue
        text = _ref_text(str(t.get("ref") or ""))
        what = ""
        m = re.search(r"\*\*Race / Class / Level:\*\*\s*([^\n]+)", text)
        if m:
            what = " ".join(m.group(1).split(" / ")[:2])
        elif text.startswith("# ") and text.count("```combat-profile") == 1:   # a file of several profiles: its title isn't this one
            what = re.sub(r"\s*\(CR [^)]*\)", "", text.splitlines()[0][2:]).strip()
        wears = ""
        sheet = str(t.get("ref") or "").split(f"campaigns/{camp}/", 1)[-1] if camp else ""
        owner = next((c for c in (inv.get("containers") or {}).values() if c.get("sheet") == sheet), None)
        if owner is not None and gear_mod is not None:
            worn = [gear_mod.entry_label(camp, dict(e, qty=1)) for e in owner["items"] if e.get("equipped")
                    and gear_mod.load_item(camp, e["item"])["category"] in ("armor", "shield")]
            wears = "wears " + (", ".join(worn) if worn else "no armor")
        elif text.count("```combat-profile") == 1:
            g = re.search(r"^\*\*Gear\*\*\s*([^\n]+)", text, re.M)
            if g:
                wears = f"gear its stat block lists (the scene decides what's actually there): {g.group(1).strip()[:220]}"
        held = cm.wielding(t) if cm.tracks_weapons(t) else []
        hands = "in hand: " + (", ".join(held) if held else "nothing (unarmed or spells)")
        carries = ""
        if owner is not None and gear_mod is not None:
            stowed = [gear_mod.entry_label(camp, dict(e, qty=1)) for e in owner["items"]
                      if gear_mod.load_item(camp, e["item"])["category"] == "weapon"
                      and gear_mod.load_item(camp, e["item"])["name"].lower() not in [h.lower() for h in held]]
            carries = ("carries (stowed): " + ", ".join(stowed)) if stowed else ""
        bits = [b for b in (what, wears, hands, carries) if b]
        lines.append(f"- {t['name']} ({t['token']}, {t['side']}{', HIDDEN' if t.get('hidden') else ''}): " + " · ".join(bits))
    return "\n".join(lines)


def _step_context(st: dict[str, Any], c: dict[str, Any]) -> str:
    """What the DM needs to play the actor without looking things up: its attacks, spells and
    speed, and where everyone is (DM data; the player never sees this message)."""
    cm = _combat_module()
    prof = c.get("profile") or {}
    opts = []
    for name, w in (prof.get("attacks") or {}).items():
        b = w.get("bonus")
        b = "/".join(f"{x:+d}" for x in b) if isinstance(b, list) else f"{b:+d}"
        opts.append(f"{name} ({w.get('type', 'melee')} {b}, {w.get('damage')}{', reach ' + str(w['reach']) if w.get('reach') else ''})")
    orders = ([f"THE PLAYER'S ORDERS for {c['name']}: {c['plan']} — follow them while they make sense (they come "
               f"before the turn plans below); once they're done or impossible, play it by its nature."] if c.get("plan") else [])
    lines = orders + [f"Its attacks (combat_attack `with`): {', '.join(opts) or 'none in its profile'}"
             + (f"; full attack: {', '.join(prof['full_attack'])}" if prof.get("full_attack") else "")
             + f". Speed {c.get('speed') or 30} ft, reach {c.get('reach', 5)} ft."]
    if cm.tracks_weapons(c):
        lines.append(f"In hand: {', '.join(cm.wielding(c)) or 'nothing'}. Attacking with another weapon needs combat_wield "
                     f"first (a move action; with BAB +1 it rides on a move; drop what's in the way for free). Only a melee "
                     f"weapon in hand (or natural attacks) threatens.")
    spells: list[str] = []
    spent: list[str] = []   # only what it can still cast: a used-up spell isn't an option
    for sc in prof.get("spellcasting") or []:
        for lvl, names in (sc.get("spells") or {}).items():
            for n in dict.fromkeys(names):
                (spells if cm.spell_left(c, sc, lvl, n) else spent).append(f"{n} ({lvl})")
    slas = [s_["name"] for s_ in prof.get("sla") or [] if cm.sla_left(c, s_)]
    spent += [f"{s_['name']} (SLA)" for s_ in prof.get("sla") or [] if not cm.sla_left(c, s_)]
    if spells or slas or spent:
        lines.append("Spells it can still cast: " + (", ".join(spells) or "none") + ("; SLAs (sla=true; Sp: they provoke like spells, and spell resistance applies): " + ", ".join(slas) if slas else "")
                     + (f". USED UP, not an option: {', '.join(spent)}" if spent else ""))
    if prof.get("abilities"):
        lines.append("Abilities (combat_ability; Su/Ex: no attack of opportunity, no spell resistance): "
                     + ", ".join(f"{n} ({str((a or {}).get('type', 'su')).capitalize()})" for n, a in prof["abilities"].items())
                     + (f" — performing {c['performing']} (keep it up with combat_ability, or it ends)" if c.get("performing") else ""))
    if prof.get("sneak_attack"):
        lines.append(f"Sneak attack +{prof['sneak_attack']} (automatic when flanking or the target is denied its Dex).")
    pos = []
    for o in cm.order(st):
        if o.get("removed") or o is c:
            continue
        d = cm.feet_between(c, o)
        hp = f"{o['hp']}/{o['max_hp']} HP"
        pos.append(f"{o['token']} {o['name']} ({o['side']}{', hidden' if o.get('hidden') else ''}) at "
                   f"{cm.fmt_pos(o['x'], o['y'])}, {d} ft away, {hp}" + (f", {', '.join(cm.R.labels(o, st))}" if cm.R.conditions(o) else ""))
    try:   # the geometry of its turn: reach, flanking, what it needs to hit, charge lanes, cover
        lines.append("Tactical options (computed; pick by its nature and knowledge):\n" + cm.tactical_options(st, c))
    except Exception as e:   # never block a step on the helper
        lines.append(f"(tactical options unavailable: {e})")
    lines.append(f"{c['token']} is at {cm.fmt_pos(c['x'], c['y'])} ({c['hp']}/{c['max_hp']} HP"
                 + (f", {', '.join(cm.R.labels(c, st))}" if cm.R.conditions(c) else "") + "). Others: " + "; ".join(pos))
    try:
        lines.append(cast_list(st))
    except Exception as e:   # never block a step on the helper
        lines.append(f"(who's who unavailable: {e})")
    return "\n".join(lines)


def _visible_prompt(c: dict[str, Any], started: str, pc_after: bool, next_name: str | None = None) -> str:
    """The instruction for one visible non-PC actor's step. Whose turn comes next is the interface's
    to announce (it knows when the actor is really done, e.g. after a follow-up move), so the narration
    never hands the turn to the player."""
    end = (f"Don't say whose turn comes next, don't write 'your turn' and don't ask the player what they do: the "
           f"interface announces the next turn itself" + ("" if pc_after else f" (it's {next_name or 'another creature'}'s, not the player's)")
           + ". Don't narrate anyone else's turn.")
    return (f"[Combat step, sent by the interface (not the player). The turn pointer is on {c['token']} "
            f"({c['name']}); `next` already ran:\n{started}\n{c.get('_ctx', '')}{c.get('_sight', '')}\n"
            f"Resolve ONLY {c['name']}'s turn: choose its actions from its tactics and the situation, and "
            f"resolve them in ONE combat_batch call. Don't run `next`: the interface advances turns. "
            f"Then narrate only {c['name']}'s turn and stop. {end} The briefing above is for your decision only: "
            f"don't write any of it (no 'hits on N+', no squares weighed, no enemy AC or HP), and write nothing "
            f"before your tool call; only the narration after it is shown.]")


def _followup_due(cm: Any, camp: str, tok: str, foes_before: dict[str, int]) -> tuple[dict[str, Any], dict[str, Any], str] | None:
    """After an NPC's step: (state, its token, why) when it should get a second look at its move action:
    its standard action is spent, its move isn't, and the situation changed (a foe dropped, or a melee
    creature now threatens no one). Else None: most steps need no second call."""
    st = combat_state(camp) or {}
    c = next((t for t in st.get("tokens", []) if t["token"] == tok), None)
    if not c or st.get("turn") != tok or c.get("hidden") or not cm.can_act(c):
        return None
    ta = c.get("turn_actions") or {}
    if not ta.get("standard") or ta.get("full") or c.get("moved") or c.get("stepped") or cm.can_take(st, c, "move"):
        return None
    toks = {t["token"]: t for t in st.get("tokens", [])}
    dropped = [toks[t]["name"] for t in foes_before if t in toks and toks[t]["hp"] <= 0]
    if dropped:
        return st, c, f"{', '.join(dropped)} went down"
    foes = [o for o in st.get("tokens", []) if (o["side"] in cm.FRIENDLY) != (c["side"] in cm.FRIENDLY)
            and o["hp"] > 0 and not o.get("removed")]
    melee = any(w.get("type", "melee") == "melee" for w in ((c.get("profile") or {}).get("attacks") or {}).values())
    if melee and foes and not any(cm.threatens(c, o) for o in foes):
        return st, c, "it threatens no enemy where it stands"
    return None


def _followup_prompt(c: dict[str, Any], why: str, ctx: str) -> str:
    """The second look at an NPC's move action, after its standard action changed the situation."""
    return (f"[Combat step continued, sent by the interface: {c['name']} ({c['token']}) has used its standard "
            f"action and still has its move action. The situation changed: {why}. Updated options:\n{ctx}\n"
            f"If it would move now (toward the next enemy, into cover, away), do it in ONE combat_batch call and "
            f"narrate the move in one short line. If it stays put, make no tool call and reply with only \"…\" "
            f"(nothing is shown). Don't write any of the briefing.]")


def _hidden_prompt(c: dict[str, Any], started: str) -> str:
    """The instruction for a hidden actor's step (its text is only shown if it gets revealed)."""
    return (f"[Combat step, sent by the interface. The turn pointer is on {c['token']} ({c['name']}), which "
            f"the player hasn't noticed; `next` already ran:\n{started}\n{c.get('_ctx', '')}{c.get('_sight', '')}\n"
            f"Resolve its turn with the combat tools (don't run `next`). If it stays unnoticed, reply with only \"…\": "
            f"nothing you write is shown. If its action reveals it (it attacks, or the character notices it), "
            f"reveal it (combat_flag action=reveal) in the same call and narrate its turn.]")


def run_combat_step(engine: Engine, camp: str, send: Callable[[str], bool], runner: "CombatRunner | None" = None) -> str:
    """Play one step of the fight on the player's go signal: advance the pointer, resolve hidden
    actors silently, resolve the one visible non-PC actor, and move the pointer onto the PC if the
    PC is next. The pacing is decided here, in code; the DM only plays the actor it's given.

    Args:
        engine: the engine (its text is held back while a hidden actor acts).
        camp: the campaign with the fight.
        send: sends one instruction to the DM and waits for the reply; False if the process died.
        runner: the combat runner that plays the NPC steps in its own small context. Creatures marked
            main_dm (a boss, a story NPC) still go to the main DM; without a runner, all of them do.

    Returns:
        Why the step stopped: "pc" (the player's turn), "pc-quiet" (the player's turn, and no actor
        was shown, so the frontend should say so itself), "wait" (the next visible actor waits for the
        next signal), "ask" (a question for the player is open), "over" (no fight), or "error".
    """
    cm = _combat_module()
    engine.combat_engaged = True
    acted = False
    for _ in range(200):   # a safety net; a step never needs this many
        st = combat_state(camp)
        if not st or cm.fight_over(st):
            return "over"
        if st.get("awaiting"):
            return "ask"
        found = cm.next_actor(st)
        if not found:
            return "over"
        c = found[0]
        if acted and c["side"] != "pc" and cm.can_act(c):   # one that can't act (dying, helpless) needs no Next press
            # The next visible actor gets its own step. Hidden actors in between are only resolved
            # now if the PC comes next (so the pointer can rest on the PC); otherwise they open the
            # next step, and one that reveals itself is then the only actor shown in it.
            if not c.get("hidden"):
                return "wait"
            nxt = _first_visible_after(st, c["token"])
            if not (nxt and nxt["side"] == "pc"):
                return "wait"
        try:
            started = _run_next(camp)
        except RuntimeError as e:
            engine.emit(type="error", message=f"Couldn't advance the turn: {e}")
            return "error"
        if c["side"] == "pc":
            return "pc" if acted else "pc-quiet"
        now = combat_state(camp) or st
        live = next((o for o in now.get("tokens", []) if o["token"] == c["token"]), c)
        if not cm.can_act(live):   # dying, helpless, stunned…: the script already rolled what there is to roll
            if runner is not None:
                runner.note(c["name"], "(can't act this turn)", by_runner=False)
            continue
        c = dict(c, _sight=_sight(camp, now, c["token"]), _ctx=_step_context(now, live))
        log_briefing(camp, now, c)
        use_runner = runner is not None and not live.get("main_dm")
        eng = runner.engine if use_runner and runner else engine
        say: Callable[[str], bool] = (lambda p: runner.send(runner.frame(p, camp, now))) if use_runner and runner else send
        if c.get("hidden"):
            eng.hold()
            try:
                ok = say(_hidden_prompt(c, started))
            finally:
                after = combat_state(camp) or {}
                still = next((t.get("hidden") for t in after.get("tokens", []) if t["token"] == c["token"]), True)
                text = eng.release(publish=not still, after_tools=True)
            acted = acted or not still
        else:
            nxt = _first_visible_after(st, c["token"])
            foes_before = {o["token"]: o["hp"] for o in now.get("tokens", [])
                           if (o["side"] in cm.FRIENDLY) != (live["side"] in cm.FRIENDLY) and o["hp"] > 0 and not o.get("removed")}
            eng.hold()   # the briefing invites thinking out loud: only the final narration is shown
            try:
                ok = say(_visible_prompt(c, started, pc_after=bool(nxt and nxt["side"] == "pc"),
                                         next_name=nxt["name"] if nxt else None))
            finally:
                text = eng.release(publish=True, after_tools=True)
            acted = True
            follow = _followup_due(cm, camp, c["token"], foes_before) if ok else None
            if follow:   # its standard action changed the situation and its move is still left: look again
                after_st, after_tok, why = follow
                pos = (after_tok["x"], after_tok["y"])
                eng.hold()
                try:
                    ok = say(_followup_prompt(after_tok, why, _step_context(after_st, after_tok)))
                finally:
                    later = combat_state(camp) or {}
                    me = next((t for t in later.get("tokens", []) if t["token"] == c["token"]), after_tok)
                    more = eng.release(publish=(me["x"], me["y"]) != pos, after_tools=True)
                text = (text + "\n" + more).strip()
        if runner is not None and text.strip():
            runner.note(c["name"], text.strip(), by_runner=use_runner)
        if not ok:
            return "error"
    return "error"


# ---------- the combat runner ----------
# NPC combat steps run in a separate, lean Claude Code process: its own short system prompt, only
# the dm tools, and per step only what that step needs. ~15-20k tokens per model turn instead of
# the main DM's whole conversation (~200k+ in a long session). The main DM gets a recap with the
# player's next message.

RUNNER_PROMPT = """You are the combat runner of a tabletop DM interface (Pathfinder 1e). You play the turns of the non-player creatures in a fight, one creature per message. The player sees ONLY the narration you write after your last tool call; everything else stays hidden.

Every message is a combat step for ONE creature, with a DM-only briefing: its attacks, positions, tactical options (squares, the d20 roll it needs, what provokes) and what it can see.
1. Decide what this creature does, by its nature, its knowledge and the encounter's tactics and morale (not by what you know as the DM). A cowardly creature may retreat; morale breaks per the notes. An enemy it can't see isn't gone: if it isn't afraid and has no reason to hide, it goes after it (toward where it was last seen, into view, or with light) instead of holding back. Allies of the player act on what the player's character says aloud (an order, "get him!") when it fits them.
2. Resolve it in ONE combat_batch call with the dm tools (move, attack, cast/sla through combat_cast with the effect in the same call: dmg/save, heal dice for cure spells, cond + cond_rounds for a condition on a failed save, unless the profile's effect data fills it in; special abilities like bardic performance or channel energy through combat_ability; maneuvers, conditions). The turn plans in the briefing weigh damage, support and risk, including its tactics weights and broken morale: use the spells, buffs, heals, defense and retreats they list, but play the creature's nature over the top number. A frightened or panicked creature's plans list only flight: it flees. Dropping a weapon to draw another leaves it on the ground (the plans charge for that): prefer sheathing or keeping the weapon in hand unless the drop clearly pays off this turn. Buff spells (bless) apply their bonus to every ally in range through combat_cast. The tools roll and apply every effect themselves: never fix HP afterwards with dice_roll and combat_hp. If a call fails, fix that call; if the effect really wasn't applied, say so in one line instead of patching it. The tools do all the rule math. Never run combat_next or combat_end; act only for this creature.
3. Then narrate only this creature's turn, in 1-3 lines, and stop.

Narration rules (strict):
- Write NOTHING before your tool call. Never repeat the briefing: no "hits on N+", no squares weighed, no enemy AC, HP or bonuses.
- Address the player's character as "you". Never write what the PC says, does, thinks or feels.
- Each attack on the PC: its total against the PC's AC and the damage as a number ("17 vs your AC 16, hit, 6 damage"). Never state an enemy's AC, HP or bonuses; say "hit", "miss", "bloodied".
- Match the combat log the tools return; never contradict a number.
- Describe people only with what the briefing's "Who's who" list gives them: their kind, the armor they wear ("no armor" means none: a blow can't glance off it) and what's in their hands. Never invent armor, shields or weapons.
- Highlight names the characters know: people in **bold**, places in ***bold italic***, spells and items in *italic*.
- A first use of a special ability, a reveal, or a turning point gets 2-4 vivid sentences; otherwise one line per action.
- A hidden creature that stays unnoticed: reply only "…".
- Never write "your turn", never say whose turn comes next and never ask the player what they do: the interface announces the next turn.
- Respect the table's lines and veils below."""


def runner_system_prompt(campaign: str, base: str = RUNNER_PROMPT) -> str:
    """A runner prompt (RUNNER_PROMPT, or PC_TURN_PROMPT) plus the campaign's table: tone, DM voice,
    conventions and safety lines from players/session-zero.md (player-facing, so nothing secret)."""
    path = REPO / "campaigns" / campaign / "players" / "session-zero.md"
    keep = []
    if path.exists():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.S | re.M):
            title = m.group(1).strip()
            if any(k in title.lower() for k in ("tone", "style", "safety", "convention", "dm voice")):
                keep.append(f"## {title}\n{m.group(2).strip()}")
    table = "\n\n".join(keep)[:6000]
    return base + (f"\n\nThis campaign's table (session zero):\n{table}" if table else "")


class CombatRunner:
    """Plays NPC combat steps in a lean, separate Claude Code process (see RUNNER_PROMPT). Its
    conversation is reset every few steps (each step message is self-contained), so its context
    stays small however long the fight runs."""

    RESET_EVERY = 6

    def __init__(self, on_event: EventHandler, campaign: str, model: str | None = None, effort: str = "low",
                 after_send: Callable[[], None] | None = None) -> None:
        """Args:
            on_event: the frontend's event handler (the runner's narration appears as DM text).
            campaign: the campaign of the fight.
            model, effort: for the runner's process (effort low: one creature's turn needs little thought).
            after_send: called after every step reply (e.g. to refresh the combat panel).
        """
        self.campaign = campaign
        self.engine = Engine(on_event, model=model, effort=effort, role="runner",
                             system_prompt=runner_system_prompt(campaign), campaign=campaign)
        self.engine.debug_tag = "NPC runner"
        self.after_send = after_send
        self.steps = 0
        self.recent: list[str] = []   # the last narrations, for continuity
        self.recap: list[str] = []    # what the main DM hasn't heard about yet
        self.player_said: list[str] = []   # the player's latest messages: allies hear what the PC says

    def send(self, prompt: str) -> bool:
        """Send one step to the runner (starting or refreshing its process as needed)."""
        if not self.engine.alive():
            self.engine.start()
        elif self.steps and self.steps % self.RESET_EVERY == 0:
            self.engine.new_session()
        self.steps += 1
        ok = self.engine.send(prompt)
        if not ok:
            self.engine.new_session()   # start clean; the step itself counts as failed
        if self.after_send:
            self.after_send()
        return ok

    def frame(self, prompt: str, camp: str, st: dict[str, Any]) -> str:
        """The step message for the runner: the campaign, the encounter's notes and the recent
        narration in front of the usual step briefing."""
        parts = [f"[Combat step context] Campaign: {camp} (pass campaign={camp} on your first tool call)."]
        enc = (st.get("encounter") or {}).get("file")
        if enc:
            try:
                block = _combat_module().load_encounter(REPO / enc)
                notes = "; ".join(f"{k.replace('_', ' ')}: {block[k]}" for k in ("tactics", "morale", "exit_ramp") if block.get(k))
                if notes:
                    parts.append(f"Encounter notes (DM only): {notes}")
            except Exception:
                pass
        if self.recent:
            parts.append("Recent narration (for continuity; don't repeat it):\n" + "\n".join(self.recent[-4:]))
        if self.player_said:
            parts.append("What the player said last (\"quotes\" are the PC speaking aloud: allies who hear it act on it "
                         "when it fits them; enemies only if they'd hear and understand):\n" + "\n".join(self.player_said[-2:]))
        return "\n".join(parts) + "\n\n" + prompt

    def heard(self, text: str) -> None:
        """Remember what the player just said (their own words, not interface messages)."""
        t = player_part(text) or ""
        if t.strip() and not t.startswith(("/", "[")):
            self.player_said = (self.player_said + [t.strip()[:400]])[-2:]

    def note(self, name: str, text: str, by_runner: bool) -> None:
        """Remember a step's narration: for continuity, and (if the runner played it) for the recap."""
        self.recent = (self.recent + [f"{name}: {text}"])[-6:]
        if by_runner:
            self.recap.append(f"{name}: {text}")

    def note_player(self, said: str, narration: str) -> None:
        """Remember a player's declaration and how the player-turn runner resolved it (for the recap)."""
        line = f"The player: {said.strip()[:300]}\n  → {narration}"
        self.recent = (self.recent + [line])[-6:]
        self.recap.append(line)

    def take_recap(self) -> str:
        """The recap for the main DM (and forget it): what the runner narrated since the last time."""
        out, self.recap = "\n".join(self.recap), []
        return out

    def stop(self) -> None:
        """Stop the runner's process."""
        self.engine.stop()


# ---------- the player's turns in a fight ----------
# During a fight, the player's messages on their turn (and answers to the script's questions) go to
# a second lean process instead of the main DM: it reads ~25k tokens per call instead of the whole
# session. Anything that isn't resolving the character's combat actions goes back to the main DM:
# the runner answers only ESCALATE, which is never shown.
ESCALATE = "[[DM]]"

PC_TURN_PROMPT = f"""You are the combat assistant of a tabletop DM interface (Pathfinder 1e). During a fight you resolve what the PLAYER declares for their character (the PC) on their turn, with the dm tools, and narrate the result. The player sees only the text you write; tool calls stay hidden. The player's character sheet is below.

Each message gives the turn's context (whose turn, the actions left, an open question from the script, the recent narration) and then what the player says.
1. Resolve exactly what the player declared, in as few calls as possible (several actions: one combat_batch). Use THEIR numbers: combat_attack with total (and damage if they gave it; a hit without damage waits: ask for it, then combat_damage), combat_maneuver and combat_save with total, combat_move (5-foot step, charge, withdraw, run via its options), combat_cast for their spells (the effect comes from the library; targets' saves are rolled by the tools; THEIR rolls go in: total = their touch attack for a ray or touch spell, amount = their rolled damage or healing, dc = the DC from their sheet; the tool asks for what's missing), combat_ability, combat_act for actions without their own tool (draw a weapon, stand up, a potion, total defense), combat_wield and combat_pickup, combat_first_aid on a dying ally next to them (their Heal check as total; DC 15, provokes), combat_undo when they correct a roll they already gave (then enter the corrected one), combat_endturn when they end the turn ("end turn", "done", "that's it", or together with their actions). The tools do all the rule math.
2. THE PLAYER ROLLS ALL OF THE PC'S DICE. Never call dice_roll for the PC and never make up or assume a PC's number (attack, damage, healing, save, check), also not after a tool error: ask for it.
3. Submit actions exactly as declared: the script judges legality and action economy. If a tool refuses, say plainly why and ask what they do instead. Never substitute another action, and don't retry a refused call unchanged. Never use override except for a feat or ability that changes the rules (Spring Attack, Quick Draw) when the sheet has it.
4. Then narrate the result in 1-3 lines (more for a crit, a kill or a spectacular moment), say which actions are left (from the tool's report), and STOP. Don't play anyone else's turn, don't run combat_next, never end the turn yourself, and never write the PC's words, thoughts or actions beyond what the player declared.
5. When a result sets a question (an attack of opportunity, a save, a concentration or stabilization check), ask the player for that roll. The context shows an open question; the player's message may answer it.
6. When a unique, named or boss enemy drops from the PC's attack, stop before describing it and ask "How do you want to do this?"; the player's next message describes the finish, and you narrate it.
7. Orders the player gives companions or allies ("Brenna, grapple him!", "Kovan, cover me") are free to speak: resolve the PC's own actions, and record each order with combat_plan for that ally (it shows in its briefing on its turns). That's not a hand-back.
8. HAND BACK TO THE DM: decide this FIRST, before any tool call. Reply with exactly {ESCALATE} and nothing else (no tool call, no other text) when the message is anything other than resolving the character's actions in this fight: talking with an NPC beyond a short battle cry (parley, threats, questions, surrender terms), questions about the world, lore, the story or a rule you aren't certain of, a stunt or skill use that needs a DC set (Bluff, Intimidate, Acrobatics past the basics), out-of-character remarks, or anything the sheet and tools don't cover.

Narration rules (strict):
- Address the PC as "you". Never state an enemy's AC, attack bonus, HP or saves; say "hit", "miss", "bloodied". No game terms in NPCs' mouths.
- Match the tool results and the combat log; never contradict a number.
- Describe people only with what the "Who's who" list gives them: their kind, the armor they wear ("no armor" means none) and what's in their hands. Never invent armor, shields or weapons.
- Highlight names the characters know: people in **bold**, places in ***bold italic***, spells and items in *italic*.
- Write nothing before your tool calls; only the narration after them.
- Respect the table's lines and veils below."""


def pc_sheets(campaign: str, st: dict[str, Any]) -> str:
    """The character sheets of the fight's PCs (their `ref`), for the player-turn runner."""
    out = []
    for t in st.get("tokens", []):
        ref = t.get("ref") if t.get("side") == "pc" else None
        if not ref:
            continue
        for p in (REPO / ref, REPO / "campaigns" / campaign / ref):
            if p.is_file() and "/dm/" not in str(p):   # player-facing sheets only
                out.append(f"### {t['name']} ({t['token']})\n{p.read_text(encoding='utf-8')[:9000]}")
                break
    return "\n\n".join(out)


class PlayerTurnRunner(CombatRunner):
    """Resolves the player's declared actions during a fight in its own lean process (PC_TURN_PROMPT,
    with the PCs' sheets). A new player turn starts a fresh conversation; within a turn it keeps one,
    so "and then I step back" knows what came before."""

    RESET_EVERY = 12

    def __init__(self, on_event: EventHandler, campaign: str, st: dict[str, Any], model: str | None = None,
                 effort: str = "medium", after_send: Callable[[], None] | None = None) -> None:
        super().__init__(on_event, campaign, model=model, effort=effort, after_send=after_send)
        sheets = pc_sheets(campaign, st)
        prompt = runner_system_prompt(campaign, PC_TURN_PROMPT) + (f"\n\nThe player's character sheet:\n{sheets}" if sheets else "")
        self.engine = Engine(on_event, model=model, effort=effort, role="runner", system_prompt=prompt, campaign=campaign)
        self.engine.debug_tag = "player-turn runner"
        self.turn_key: tuple[Any, Any] | None = None

    def player_frame(self, text: str, st: dict[str, Any], recent: list[str]) -> str:
        """The message for one player declaration: the turn's context, then the player's words."""
        parts = [f"[Player's turn context] Campaign: {self.campaign} (pass campaign={self.campaign} on your first tool call).",
                 turn_line(st)]
        if st.get("awaiting"):
            parts.append(f"Open question from the script: {st['awaiting']}")
        try:
            parts.append(cast_list(st))
        except Exception:
            pass
        if recent:
            parts.append("Recent narration (for continuity; don't repeat it):\n" + "\n".join(recent[-4:]))
        return "\n".join(p for p in parts if p) + "\n\nThe player says:\n" + text

    def play(self, text: str, st: dict[str, Any], recent: list[str]) -> tuple[bool, str | None]:
        """Resolve one player message. Returns (ok, the narration shown), with None for the narration
        when it handed the message back to the main DM (nothing is shown then). A hand-back after a
        tool call doesn't count: the actions are resolved, and passing the message on would have the
        main DM resolve them a second time (a stabilization check rolled twice)."""
        key = (st.get("round"), st.get("turn"))
        if self.turn_key is not None and key != self.turn_key and self.engine.alive():
            self.engine.new_session()   # a new turn: start clean (the context line has what's left)
            self.steps = 0
        self.turn_key = key
        self.engine.hold()
        handed_back, shown = False, ""
        try:
            ok = self.send(self.player_frame(text, st, recent))
        finally:
            handed_back = ESCALATE in self.engine.held_text() and not self.engine.held_acted()
            self.engine.scrub_held(ESCALATE)
            shown = self.engine.release(publish=not handed_back, after_tools=True)
        if handed_back:
            self.engine.dbg("[handed back to the DM]")
        if not ok or handed_back:
            return ok, None
        return True, shown.strip()


def turn_line(st: dict[str, Any] | None) -> str:
    """Whose turn it is, from the script: on the PC's turn what it has left (the DM's action bookkeeping
    comes from here, never from its memory of earlier turns); between NPC steps, that it isn't the
    player's turn and who acts next."""
    if not st or st.get("turn") is None:
        return ""
    c = next((t for t in st.get("tokens", []) if t["token"] == st["turn"]), None)
    if not c:
        return ""
    if c["side"] != "pc":   # between NPC steps: the player is talking out of turn
        nxt = _first_visible_after(st, c["token"])
        spent = any((c.get("turn_actions") or {}).values()) or c.get("moved") or c.get("stepped")
        shown = c["name"] if not c.get("hidden") else "a creature"
        where = (f"{shown} has just taken its turn" if spent else f"{shown}'s turn hasn't been played yet (interrupted?)")
        upcoming = f"; next up: {nxt['name']}" if nxt else ""
        mine = " (the player's turn)" if nxt and nxt["side"] == "pc" else ""
        return (f"Now: round {st.get('round')}, NOT the player's turn: {where}{upcoming}{mine}. The interface plays "
                f"the next turn when the player presses Next. Answer what the player says or asks (speaking is a "
                f"free action), but don't resolve actions for their character, don't say it's their turn, and only "
                f"allow a readied or immediate action if the rules do.")
    try:
        left = _combat_module().actions_left(st, c)
    except Exception:   # never block a message on the helper
        return ""
    untouched = not any((c.get("turn_actions") or {}).values()) and not c.get("moved") and not c.get("stepped")
    fresh = " (a NEW turn: what it did on earlier turns doesn't count)" if untouched else ""
    return f"Now: round {st.get('round')}, {c['name']}'s turn{fresh}. Actions left (from the script): {left}."


COMBAT_RULES = "library/general/table-rules/combat.md"


def reads_combat_rules(name: str, inp: dict[str, Any]) -> bool:
    """Whether a tool call reads the combat table rules (Read, or a shell command naming the file)."""
    target = str(inp.get("file_path") or "") if name == "Read" else str(inp.get("command") or "") if name == "Bash" else ""
    return COMBAT_RULES in target


def with_recap(text: str, recap: str, log_lines: list[str], st: dict[str, Any] | None = None,
               rules_unread: bool = False) -> str:
    """The player's message for the main DM, with what happened in combat since its last reply in
    front (the chat shows only the player's text, live and in reloaded history), and whose turn it is.
    rules_unread: a fight is on and the DM hasn't read combat.md in this conversation: remind it."""
    now = turn_line(st)
    if rules_unread:
        now = (f"A fight is on and you haven't read {COMBAT_RULES} in this conversation (or since it was "
               f"compacted): read it now, before you resolve anything.\n" + now)
    if not recap and not log_lines and not now:
        return text
    body = (f"While you were waiting, the combat runner played these turns and resolved the player's declared actions "
            f"(the player saw this narration):\n{recap}\n"
            if recap else "")
    if log_lines:
        body += "Combat log since your last reply:\n" + "\n".join(log_lines[-20:]) + "\n"
    body += now
    return f"{RECAP_PREFIX}: {body.strip()}]\n\n{text}"

