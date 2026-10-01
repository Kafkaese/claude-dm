"""dm_engine: the shared core of Claude DM's player-facing interfaces (play.py, web.py).

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

ALLOWED_TOOLS = [
    "Read", "Glob", "Grep", "Edit", "Write", "Agent", "Task", "Skill", "TodoWrite",
    "WebFetch", "WebSearch",
    "mcp__dm",   # the game tools (scripts/mcp_server.py): dice_roll, world, combat_*; the scripts aren't run via Bash here
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)",
    "Bash(sed -n:*)", "Bash(wc:*)", "Bash(find:*)", "Bash(mkdir:*)",
    "Bash(cp -R campaigns/_template:*)",
    "Bash(git status:*)", "Bash(git add:*)", "Bash(git commit:*)",
]

WRAPPER_PROMPT = """You are running inside a player-facing interface for Claude DM (play.py in a terminal, or the web UI).
- The player sees ONLY your own text. Tool calls, tool results, subagent activity and subagent text are hidden from them.
- Play mode (web/terminal): do hidden mechanics yourself, with the `dm` tools (dice_roll, world, combat_*; give `campaign` on the first call), and read and write dm/ files directly. Where the docs show a script command line, use the matching tool: `combat.py attack …` = combat_attack, `combat.py do "…" "…"` = ONE combat_batch, `roll.py` = dice_roll, `world.py turn …` = world. Don't delegate them to the gm-screen agent. Keep using dm-scribe, dm-researcher and continuity-checker for heavy jobs (prep, research, the continuity check), and always wait for their results.
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
- COMBAT (details: combat.md; the combat tools' descriptions have the options):
  - The script does all the rule math (modifiers, AoOs, maneuvers, light and vision, durations, dying). Never compute modifiers, count squares or roll attacks yourself. NPCs: combat_attack with `with` (a profile attack); PCs: the player's rolls (combat_attack with `total` and `damage`).
  - Every NPC spell or SLA goes through combat_cast (sla=true for SLAs), with its effect in the same call. Effects beyond damage, after a failed save: combat_condition with rounds.
  - Setup: a prepared encounter (combat_encounters action=list) is ONE combat_setup call once the player's initiative is in. Otherwise: every combatant needs a valid combat profile (add one from the stat block first; a PC's sheet must pass the PC schema, so ask the player for missing values). Decide the lighting as part of the encounter. PC tokens use the first letter of the name (Corin → C). After setup, stop.
  - THE INTERFACE RUNS THE TURN ORDER. Never run `next` (it's refused). A bracketed "[Combat step …]" message names ONE actor and what it can see: resolve exactly that actor in ONE combat_batch call, narrate only that actor, and stop. Play it by its nature and what it sees. A hidden actor's step: reply "…" unless it gets revealed.
  - On the PC's turn, resolve what the player declares and say which actions remain. If the player ends the turn in other words or together with their actions, call combat_endturn.
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
    """Remember a session id in .play/last-session and append it to .play/sessions.log."""
    if not sid:
        return
    STATE.mkdir(exist_ok=True)
    (STATE / "last-session").write_text(sid)
    with (STATE / "sessions.log").open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')} {sid}\n")


def last_session() -> str | None:
    """The id of the most recently saved session, or None."""
    f = STATE / "last-session"
    return f.read_text().strip() if f.exists() else None


# ---------- telemetry ----------
# One JSON line per exchange in .play/telemetry.jsonl (local and gitignored; it contains the DM's
# commands, so it's DM-only). Summarize with: python3 scripts/telemetry.py

TELEMETRY = STATE / "telemetry.jsonl"


def exchange_kind(text: str) -> str:
    """What an exchange was, from the message the engine sent."""
    t = text.lstrip()
    if t.startswith("[Combat step"):
        return "combat-hidden" if "hasn't noticed" in t[:400] else "combat-step"
    if t.startswith("[The player is switching"):
        return "switch"
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
        hit = [l for l in lines if pick(l)]
        if hit:
            return hit[-1][:240]   # the last one: a traceback ends with the actual exception
    return lines[0][:240] if lines else ""


class Engine:
    """One headless DM session. `send()` blocks until the reply to that message is complete."""

    def __init__(self, on_event: EventHandler, model: str | None = None, effort: str = 'medium', debug: bool = False) -> None:
        """Args:
            on_event: called with every event (from a reader thread).
            model: model alias or id for `claude --model`, or None for the default.
            effort: thinking effort for `claude --effort`.
            debug: also emit debug events for tools and subagents.
        """
        self.on_event = on_event
        self.model = model
        self.effort = effort
        self.debug = debug
        self.proc: subprocess.Popen[str] | None = None
        self.session_id: str | None = None
        self.stderr_lines: list[str] = []
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.waiting = False   # a player turn is in progress
        self._held: list[dict[str, Any]] | None = None   # DM text held back (a hidden actor's step)
        self._tel: dict[str, Any] | None = None           # telemetry of the exchange in progress
        self.telemetry = True
        self.armed = False     # the echo of the player's message has been seen
        self._reset()

    def _reset(self) -> None:
        """Forget the per-reply streaming state."""
        self.streamed: set[str | None] = set()
        self.current_msg = None
        self.in_text = False

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

    def release(self, publish: bool) -> None:
        """Stop holding text; show what was held back if `publish`, else drop it."""
        with self.lock:
            held, self._held = self._held or [], None
        if publish:
            for ev in held:
                self._send_event(ev)

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
               "--permission-mode", "dontAsk",
               "--allowedTools", *ALLOWED_TOOLS, "--disallowedTools", "AskUserQuestion",
               "--append-system-prompt", WRAPPER_PROMPT]
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
        self.proc = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        threading.Thread(target=self._drain_stderr, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _drain_stderr(self, proc: subprocess.Popen[str]) -> None:
        """Collect the process's stderr (and emit it in debug mode)."""
        assert proc.stderr is not None
        for line in proc.stderr:
            self.stderr_lines.append(line.rstrip())
            if self.debug:
                self.emit(type="debug", line=f"[stderr] {line.rstrip()}")

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
        self.start(resume=self.session_id)

    def new_session(self) -> None:
        """Stop the process and start a fresh conversation (no resume), e.g. for another campaign."""
        self.stop()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
        self.emit(type="status", label=None)
        self._reset()
        self.done.set()
        self.session_id = None
        self.start()

    def set_effort(self, level: str) -> None:
        """Change the thinking effort; restarts the process and resumes the session."""
        if level not in EFFORTS:
            raise ValueError(level)
        self.effort = level
        self.restart()

    # --- turns ---
    def send(self, text: str) -> bool:
        """Send one player message and block until its reply is complete. False if the process died."""
        proc = self.proc
        if proc is None or proc.poll() is not None or proc.stdin is None:
            return False
        with self.lock:
            self.done.clear()
            self.waiting, self.armed = True, False
            self._reset()
            self._tel = {"start": time.time(), "kind": exchange_kind(text), "chars_in": len(text),
                         "tools": {}, "sub_tools": 0, "chars_out": 0}
            self.emit(type="status", label="thinking")
        proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
        proc.stdin.flush()
        while not self.done.wait(0.2):
            if not self.alive():
                break
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
               "session": self.session_id, "campaign": active_campaign(), "kind": tel["kind"],
               "seconds": round(time.time() - tel["start"], 1), "effort": self.effort,
               "chars_in": tel["chars_in"], "chars_out": tel["chars_out"],
               "tools": tools, "tool_calls": len(tools), "tool_errors": sum(1 for x in tools if x.get("error")),
               "subagent_tool_calls": tel["sub_tools"]}
        for k in ("num_turns", "duration_ms", "total_cost_usd", "died", "is_error"):
            if k in result:
                rec[k] = result[k]
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
                    self.emit(type="status", label=flavor(block.get("name"), not top))
                    if self.debug:
                        self.emit(type="debug", line=f"[tool{'' if top else ' (sub)'}] {block.get('name')}")
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
                self.emit(type="debug", line=f"[subagent] {' '.join(texts)[:400]}")
            if self.debug:
                for c in content:
                    if c.get("type") == "tool_use":
                        self.emit(type="debug", line=f"[input] {json.dumps(c.get('input'))[:300]}")
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
                    self.emit(type="debug", line=f"[result] {text[:300]}")
        elif t == "result":
            self._text_end()
            self.emit(type="status", label=None)
            sid = m.get("session_id") or self.session_id
            if sid:
                self.session_id = sid
                save_session(sid)
            if m.get("is_error"):
                self.emit(type="error", message=f"The DM hit an error ({m.get('subtype')}). Try again.")
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


def active_campaign(explicit: str | None = None) -> str | None:
    """The given campaign, or the one touched most recently (fight, session log, campaign file)."""
    if explicit:
        return explicit
    best: str | None = None
    best_t = 0.0
    for camp in (REPO / "campaigns").iterdir():
        if not camp.is_dir() or camp.name.startswith("_"):
            continue
        paths = [camp / "campaign.md", camp / "dm" / "combat" / "current.json"]
        paths += list((camp / "dm" / "session-log").glob("session-*.md"))
        t = max((p.stat().st_mtime for p in paths if p.exists()), default=0)
        if t > best_t:
            best, best_t = camp.name, t
    return best


def list_campaigns() -> list[dict[str, str]]:
    """All playable campaigns (folders with a campaign.md, not _template) as {slug, title}."""
    root = REPO / "campaigns"
    return [{"slug": d.name, "title": campaign_title(d.name)}
            for d in sorted(root.iterdir())
            if d.is_dir() and not d.name.startswith("_") and (d / "campaign.md").exists()]


def campaign_title(camp: str | None) -> str:
    """The campaign's title from the '# …' line of campaign.md, or a fallback."""
    f = REPO / "campaigns" / camp / "campaign.md" if camp else None
    if f and f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return camp or "Claude DM"


def map_png_path(camp: str) -> Path:
    """The clean map image (map only, no initiative panel) that the web UI shows."""
    return REPO / "campaigns" / camp / "players" / "combat-map-clean.png"


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


def combat_snapshot(camp: str | None, render_png: bool = False) -> dict[str, Any] | None:
    """Player-safe state of the current fight, or None. The web UI draws the map itself from
    `map`; render_png=True also writes a map-only PNG (for other frontends)."""
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
    png = map_png_path(camp)
    if render_png:
        try:
            cm.render_image(st, png, panel=False)
        except Exception:
            pass
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
                "terrain_names": cm.TERRAIN_NAMES, "light": _light_view(cm, st)}
    turn = next((r["name"] for r in rows if r["current"]), None)
    cur = next((r for r in rows if r["current"]), None)
    # Who plays on the next go signal: the first live actor after the turn pointer (the pointer
    # marks who is acting or acted last). Hidden actors are skipped, because the DM resolves them
    # silently within the step, and naming them would give them away.
    nxt = _first_visible_after(st, st.get("turn"))
    upcoming = {"name": nxt["name"], "token": nxt["token"], "side": nxt["side"]} if nxt else None
    return {
        "active": True, "round": st.get("round", 1), "turn": turn, "initiative": rows,
        # whose turn it is, for the End turn / Next button ("pc" = the player acts now)
        "turn_side": cur["side"] if cur else None, "turn_token": cur["token"] if cur else None,
        "upcoming": upcoming,
        "awaiting": st.get("awaiting"),
        "events": [{"round": e.get("round"), "text": e.get("text", "")} for e in st.get("events", [])],
        "terrain": terrain,
        "map": grid_map,
        "image": int(png.stat().st_mtime * 1000) if png.exists() else None,
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
        if r.get("isSidechain"):
            continue
        msg = r.get("message") or {}
        if r.get("type") == "user" and isinstance(msg.get("content"), str):
            text = msg["content"]
            if text.startswith("<task-notification") or text.startswith("<local-command"):
                continue
            if "<command-name>" in text:
                name = re.search(r"<command-name>(.*?)</command-name>", text, re.S)
                args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
                text = f"{name.group(1).strip() if name else ''} {args.group(1).strip() if args else ''}".strip()
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


def is_go_signal(text: str) -> bool:
    """Whether the player's message is just a go signal ("next" or "end turn")."""
    return text.strip().lower().rstrip(".!") in GO_SIGNALS


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
        if cm.in_fight(c) and not c.get("hidden"):
            return c
    return None


def step_due(camp: str | None, text: str) -> bool:
    """After an ordinary exchange: should the interface run a combat step on its own? Yes when the
    PC's turn is over (the DM ran `combat.py endturn`, or the message ended in "end turn"), or when
    the fight was just set up and the PC is the first visible actor."""
    st = combat_state(camp)
    if not st or st.get("awaiting"):
        return False
    turn = st.get("turn")
    by_tok = {c["token"]: c for c in st.get("tokens", [])}
    if turn is None:
        first = _first_visible_after(st, None)
        return bool(first and first["side"] == "pc")
    pc_up = by_tok.get(turn, {}).get("side") == "pc"
    return pc_up and (st.get("end_turn") == turn or ends_turn(text))


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
    return ("\nWhat it sees (use it: fight from where it sees and isn't seen, avoid what it can't see in, "
            "go for light sources if darkness favors it):\n" + r.stdout.strip())


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
    lines = [f"Its attacks (combat_attack `with`): {', '.join(opts) or 'none in its profile'}"
             + (f"; full attack: {', '.join(prof['full_attack'])}" if prof.get("full_attack") else "")
             + f". Speed {c.get('speed') or 30} ft, reach {c.get('reach', 5)} ft."]
    spells = []
    for sc in prof.get("spellcasting") or []:
        for lvl, names in (sc.get("spells") or {}).items():
            spells += [f"{n} ({lvl})" for n in names]
    slas = [s_["name"] for s_ in prof.get("sla") or []]
    if spells or slas:
        lines.append("Spells: " + (", ".join(spells) or "none") + ("; SLAs (sla=true): " + ", ".join(slas) if slas else "")
                     + " (combat_info what=spells for what's left)")
    pos = []
    for o in cm.order(st):
        if o.get("removed") or o is c:
            continue
        d = cm.feet_between(c, o)
        hp = f"{o['hp']}/{o['max_hp']} HP"
        pos.append(f"{o['token']} {o['name']} ({o['side']}{', hidden' if o.get('hidden') else ''}) at "
                   f"{cm.fmt_pos(o['x'], o['y'])}, {d} ft away, {hp}" + (f", {', '.join(cm.R.labels(o, st))}" if cm.R.conditions(o) else ""))
    lines.append(f"{c['token']} is at {cm.fmt_pos(c['x'], c['y'])} ({c['hp']}/{c['max_hp']} HP"
                 + (f", {', '.join(cm.R.labels(c, st))}" if cm.R.conditions(c) else "") + "). Others: " + "; ".join(pos))
    return "\n".join(lines)


def _visible_prompt(c: dict[str, Any], started: str, pc_after: bool) -> str:
    """The instruction for one visible non-PC actor's step."""
    end = ("The player's turn comes right after this one: end with one short line saying so."
           if pc_after else "Don't end with a question: the player sends the next go signal.")
    return (f"[Combat step, sent by the interface (not the player). The turn pointer is on {c['token']} "
            f"({c['name']}); `next` already ran:\n{started}\n{c.get('_ctx', '')}{c.get('_sight', '')}\n"
            f"Resolve ONLY {c['name']}'s turn: choose its actions from its tactics and the situation, and "
            f"resolve them in ONE combat_batch call. Don't run `next`: the interface advances turns. "
            f"Then narrate only {c['name']}'s turn and stop. {end}]")


def _hidden_prompt(c: dict[str, Any], started: str) -> str:
    """The instruction for a hidden actor's step (its text is only shown if it gets revealed)."""
    return (f"[Combat step, sent by the interface. The turn pointer is on {c['token']} ({c['name']}), which "
            f"the player hasn't noticed; `next` already ran:\n{started}\n{c.get('_ctx', '')}{c.get('_sight', '')}\n"
            f"Resolve its turn with the combat tools (don't run `next`). If it stays unnoticed, reply with only \"…\": "
            f"nothing you write is shown. If its action reveals it (it attacks, or the character notices it), "
            f"reveal it (combat_flag action=reveal) in the same call and narrate its turn.]")


def run_combat_step(engine: Engine, camp: str, send: Callable[[str], bool]) -> str:
    """Play one step of the fight on the player's go signal: advance the pointer, resolve hidden
    actors silently, resolve the one visible non-PC actor, and move the pointer onto the PC if the
    PC is next. The pacing is decided here, in code; the DM only plays the actor it's given.

    Args:
        engine: the engine (its text is held back while a hidden actor acts).
        camp: the campaign with the fight.
        send: sends one instruction to the DM and waits for the reply; False if the process died.

    Returns:
        Why the step stopped: "pc" (the player's turn), "pc-quiet" (the player's turn, and no actor
        was shown, so the frontend should say so itself), "wait" (the next visible actor waits for the
        next signal), "ask" (a question for the player is open), "over" (no fight), or "error".
    """
    cm = _combat_module()
    acted = False
    for _ in range(200):   # a safety net; a step never needs this many
        st = combat_state(camp)
        if not st:
            return "over"
        if st.get("awaiting"):
            return "ask"
        found = cm.next_actor(st)
        if not found:
            return "over"
        c = found[0]
        if acted and c["side"] != "pc":
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
        c = dict(c, _sight=_sight(camp, now, c["token"]), _ctx=_step_context(now, live))
        if c.get("hidden"):
            engine.hold()
            try:
                ok = send(_hidden_prompt(c, started))
            finally:
                after = combat_state(camp) or {}
                still = next((t.get("hidden") for t in after.get("tokens", []) if t["token"] == c["token"]), True)
                engine.release(publish=not still)
            acted = acted or not still
        else:
            nxt = _first_visible_after(st, c["token"])
            ok = send(_visible_prompt(c, started, pc_after=bool(nxt and nxt["side"] == "pc")))
            acted = True
        if not ok:
            return "error"
    return "error"

