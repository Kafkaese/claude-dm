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
import importlib.util
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
STATE = REPO / ".play"

ALLOWED_TOOLS = [
    "Read", "Glob", "Grep", "Edit", "Write", "Agent", "Task", "Skill", "TodoWrite",
    "WebFetch", "WebSearch",
    "Bash(python3 scripts/roll.py:*)", "Bash(python3 scripts/combat.py:*)", "Bash(python3 scripts/world.py:*)",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)",
    "Bash(sed -n:*)", "Bash(wc:*)", "Bash(find:*)", "Bash(mkdir:*)",
    "Bash(cp -R campaigns/_template:*)",
    "Bash(git status:*)", "Bash(git add:*)", "Bash(git commit:*)",
]

WRAPPER_PROMPT = """You are running inside a player-facing interface for Claude DM (play.py in a terminal, or the web UI).
- The player sees ONLY your own text. Tool calls, tool results, subagent activity and subagent text are hidden from them.
- Play mode "play.py": do hidden mechanics yourself. Roll with scripts/roll.py, run scripts/combat.py, and read and write dm/ files directly. Don't delegate them to the gm-screen agent. Keep using dm-scribe, dm-researcher and continuity-checker for heavy jobs (prep, research, the continuity check), and always wait for their results.
- Everything you write as text is shown to the player. So never think out loud ("Let me check…", "Now I need…"), never mention files, tools or DM-only content, and write only what the DM says at the table.
- The interface shows the combat map, the initiative order and the combat log after each turn in which the combat state changed. Don't paste the map yourself.
- NARRATION CONTRACT (these override your instincts as a writer):
  - Address the player's character as "you", always in the second person. Never "Corin does…" or "he says…".
  - Never write the PC's words, thoughts, feelings or actions beyond what the player declared. An implied intention isn't a declaration.
    - "I try to read the writing" → give what the character reads and understands ("The glyphs are old Thassilonian: 'Here stands…'"). Don't have them read it aloud, react or comment.
    - "I try to force the door" → resolve the attempt ("The door grinds open, wide enough to pass") and STOP. Don't have them step through.
    - "I attack" → resolve the attack, then say which actions remain. Don't add a move or a line of dialogue.
  - Checks you roll secretly (Perception, Knowledge, Sense Motive, …) are invisible. Never mention them: not that you rolled, not how many, not whether they succeeded (no "All three succeed", no "Perception 21"). Narrate only what the character notices or knows. A failed check simply produces nothing, or the misleading impression.
  - Companions and NPCs speak and act for themselves. The PC doesn't, unless the player says so.
- COMBAT:
  - The combat script knows the rules. Resolve attacks with `combat.py attack g1 C --with <attack>` (NPC, from its combat profile) or `attack C g1 --total N --damage N` (PC). Flanking, conditions, prone, cover, range, into-melee, flat-footed/touch AC and concealment are applied automatically, so never add modifiers yourself and never roll attacks separately. Timed effects: `cond … --rounds N` (they expire on their own). Areas: `area …`, saves: `save …`, dying PCs: `stabilize C --total N`. Movement rolls NPC attacks of opportunity itself. If a combatant's stat block has no combat-profile block, add one first (see combat.md).
  - The interface shows the combat log with all the numbers, after each turn. Narrate EVERY creature's turn in its own line or lines, matching the log. Never merge turns, never skip a creature, never contradict a number.
  - ONE ACTOR PER REPLY. The player sends "next" (or "end turn" on their own turn) as a go signal. The turn pointer marks who is acting or acted last, so every step STARTS with `next` and then resolves the actor it lands on, all in ONE `combat.py do "next" "…"` call. If the PC acts after that actor, end the call with one more `next` so the pointer rests on the PC. Narrate that one actor, then STOP (say "Your turn" if the PC is up).
  - Hidden, unnoticed actors never get a step of their own: if `next` lands on one, resolve it silently and `next` again in the same call.
  - When the player must decide something mid-round (an AoO, a reaction, a stabilization check), ask, and run `combat.py ask "…"` in your call so auto-combat pauses.
  - A PC who is dying rolls their own stabilization check (ask for it). Never "play it forward" without the player, and never promise to report back later: resolve everything in this reply, step by step.
  - PC tokens use the first letter of the character's name (Corin → C).
- Do lookups before you start writing to the player, so you never send the same text twice.
- Before any in-game narration, the /start-session skill must have run in this conversation (it loads the table rules). If the player wants to play and it hasn't, run it first.
- AskUserQuestion isn't available here. Ask questions in plain text, with the options as a short list.
- Keep turns fast. Every tool call costs the player waiting time:
  - put all rolls for a turn in ONE roll.py call, and all combat steps in ONE `combat.py do "…" "…"` call
  - don't re-read files you've already read this session
  - log tersely, at scene breaks only: one short Edit to the live log, not one per action
  - read files by section (grep -n '^#' to find the heading, then Read with offset and limit)"""

EFFORTS = ("low", "medium", "high", "xhigh", "max")


def flavor(tool_name, sub):
    if sub:
        return "working behind the screen"
    return {
        "Bash": "rolling dice and moving pieces", "Read": "checking notes", "Grep": "checking notes",
        "Glob": "checking notes", "Edit": "taking notes", "Write": "taking notes",
        "Agent": "working behind the screen", "Task": "working behind the screen",
        "WebFetch": "consulting references", "WebSearch": "consulting references",
        "Skill": "getting ready", "TodoWrite": "planning",
    }.get(tool_name, "thinking")


def save_session(sid):
    if not sid:
        return
    STATE.mkdir(exist_ok=True)
    (STATE / "last-session").write_text(sid)
    with (STATE / "sessions.log").open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')} {sid}\n")


def last_session():
    f = STATE / "last-session"
    return f.read_text().strip() if f.exists() else None


class Engine:
    """One headless DM session. `send()` blocks until the reply to that message is complete."""

    def __init__(self, on_event, model=None, effort="medium", debug=False):
        self.on_event = on_event
        self.model = model
        self.effort = effort
        self.debug = debug
        self.proc = None
        self.session_id = None
        self.stderr_lines = []
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.waiting = False   # a player turn is in progress
        self.armed = False     # the echo of the player's message has been seen
        self._reset()

    def _reset(self):
        self.streamed = set()
        self.current_msg = None
        self.in_text = False

    def emit(self, **ev):
        try:
            self.on_event(ev)
        except Exception:
            pass

    @property
    def busy(self):
        return self.waiting

    # --- process ---
    def start(self, resume=None):
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
        env = dict(os.environ, CLAUDE_DM_MODE="play")
        self.proc = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        threading.Thread(target=self._drain_stderr, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _drain_stderr(self, proc):
        for line in proc.stderr:
            self.stderr_lines.append(line.rstrip())
            if self.debug:
                self.emit(type="debug", line=f"[stderr] {line.rstrip()}")

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.alive():
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()

    def restart(self):
        if self.alive():
            self.proc.kill()
        self.emit(type="status", label=None)
        self._reset()
        self.done.set()
        self.start(resume=self.session_id)

    def set_effort(self, level):
        if level not in EFFORTS:
            raise ValueError(level)
        self.effort = level
        self.restart()

    # --- turns ---
    def send(self, text):
        """Send one player message and block until its reply is complete. False if the process died."""
        if not self.alive():
            return False
        with self.lock:
            self.done.clear()
            self.waiting, self.armed = True, False
            self._reset()
            self.emit(type="status", label="thinking")
        self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
        self.proc.stdin.flush()
        while not self.done.wait(0.2):
            if not self.alive():
                break
        with self.lock:
            self.waiting = False
        self.emit(type="status", label=None)
        return self.alive()

    # --- stream handling ---
    def _read(self, proc):
        for line in proc.stdout:
            try:
                m = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                self._handle(m)
        self.done.set()

    def _text_start(self):
        if not self.in_text:
            self.in_text = True
            self.emit(type="status", label=None)
            self.emit(type="text_start")

    def _text_end(self):
        if self.in_text:
            self.in_text = False
            self.emit(type="text_end")

    def _handle(self, m):
        t = m.get("type")
        top = m.get("parent_tool_use_id") is None
        if t == "system" and m.get("subtype") == "init":
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
        elif t == "user" and self.debug:
            for c in (m.get("message", {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    body = c.get("content")
                    body = body if isinstance(body, str) else json.dumps(body)
                    self.emit(type="debug", line=f"[result] {body[:300]}")
        elif t == "result":
            self._text_end()
            self.emit(type="status", label=None)
            sid = m.get("session_id") or self.session_id
            if sid:
                self.session_id = sid
                save_session(sid)
            if m.get("is_error"):
                self.emit(type="error", message=f"The DM hit an error ({m.get('subtype')}). Try again.")
            if self.waiting and self.armed:
                self.done.set()
                self.emit(type="turn_end", solicited=True)
            elif not self.waiting:
                self._reset()
                self.emit(type="turn_end", solicited=False)


# ---------- campaigns and combat (player-safe views) ----------

def _combat_module():
    spec = importlib.util.spec_from_file_location("combat", REPO / "scripts" / "combat.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def active_campaign(explicit=None):
    """The given campaign, or the one touched most recently (fight, session log, campaign file)."""
    if explicit:
        return explicit
    best, best_t = None, 0
    for camp in (REPO / "campaigns").iterdir():
        if not camp.is_dir() or camp.name.startswith("_"):
            continue
        paths = [camp / "campaign.md", camp / "dm" / "combat" / "current.json"]
        paths += list((camp / "dm" / "session-log").glob("session-*.md"))
        t = max((p.stat().st_mtime for p in paths if p.exists()), default=0)
        if t > best_t:
            best, best_t = camp.name, t
    return best


def campaign_title(camp):
    f = REPO / "campaigns" / camp / "campaign.md" if camp else None
    if f and f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return camp or "Claude DM"


def map_png_path(camp):
    """The clean map image (map only, no initiative panel) that the web UI shows."""
    return REPO / "campaigns" / camp / "players" / "combat-map-clean.png"


def combat_snapshot(camp, render_png=False):
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
            tokens.append(dict(r, x=c["x"], y=c["y"], size=c.get("size", 1)))
    grid_map = {"w": st["w"], "h": st["h"], "grid": st["grid"], "tokens": tokens,
                "terrain_names": cm.TERRAIN_NAMES}
    turn = next((r["name"] for r in rows if r["current"]), None)
    cur = next((r for r in rows if r["current"]), None)
    # Who plays on the next go signal: the first live actor after the turn pointer (the pointer
    # marks who is acting or acted last). Hidden actors are skipped, because the DM resolves them
    # silently within the step, and naming them would give them away.
    live = [c for c in cm.order(st) if not c.get("removed") and (c["hp"] > 0 or c["side"] in cm.FRIENDLY)]
    toks = [c["token"] for c in live]
    start = toks.index(st["turn"]) + 1 if st.get("turn") in toks else 0
    upcoming = None
    for i in range(len(live)):
        c = live[(start + i) % len(live)]
        if not c.get("hidden"):
            upcoming = {"name": c["name"], "token": c["token"], "side": c["side"]}
            break
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


def last_combat_events(camp):
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

def transcript_path(session_id):
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(REPO))
    return Path.home() / ".claude" / "projects" / slug / f"{session_id}.jsonl"


def load_history(session_id):
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
