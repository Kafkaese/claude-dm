#!/usr/bin/env python3
"""play.py: a player-facing terminal for Claude DM.

Runs Claude Code headless in this repo and shows the player ONLY the DM's words.
Tool calls, dice, file reads and subagent work stay behind the screen. A small
status line shows that something is happening. During a fight, the map (player
view) is printed after each turn, and in iTerm2 the PNG map is shown inline.

Usage:
  python3 play.py                 start a new session
  python3 play.py --resume        continue the last session
  python3 play.py --resume ID     continue a specific session
  python3 play.py --debug         also show tools and subagents (for testing)
  python3 play.py --effort high   think harder (slower); default is medium

Then type as a player, e.g. `/start-session sandpoint-delve`.
In-game commands (not sent to the DM):
  :help  :map  :debug  :effort low|medium|high  :quit
End a line with \\ to continue your message on the next line.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
STATE = REPO / ".play"

ALLOWED_TOOLS = [
    "Read", "Glob", "Grep", "Edit", "Write", "Agent", "Task", "Skill", "TodoWrite",
    "WebFetch", "WebSearch",
    "Bash(python3 scripts/roll.py:*)", "Bash(python3 scripts/combat.py:*)",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)",
    "Bash(sed -n:*)", "Bash(wc:*)", "Bash(find:*)", "Bash(mkdir:*)",
    "Bash(cp -R campaigns/_template:*)",
    "Bash(git status:*)", "Bash(git add:*)", "Bash(git commit:*)",
]

WRAPPER_PROMPT = """You are running inside play.py, a player-facing interface for Claude DM.
- The player sees ONLY your own text. Tool calls, tool results, subagent activity and subagent text are hidden from them.
- Play mode "play.py": do hidden mechanics yourself. Roll with scripts/roll.py, run scripts/combat.py, and read and write dm/ files directly. Don't delegate them to the gm-screen agent. Keep using dm-scribe, dm-researcher and continuity-checker for heavy jobs (prep, research, the continuity check), and always wait for their results.
- Everything you write as text is shown to the player. So never think out loud ("Let me check…", "Now I need…"), never mention files, tools or DM-only content, and write only what the DM says at the table.
- The interface prints the combat map (player view, and the PNG in iTerm2) after each turn in which the combat state changed. Don't paste the map yourself.
- NARRATION CONTRACT (these override your instincts as a writer):
  - Address the player's character as "you", always in the second person. Never "Corin does…" or "he says…".
  - Never write the PC's words, thoughts, feelings or actions beyond what the player declared. An implied intention isn't a declaration.
    - "I try to read the writing" → give what the character reads and understands ("The glyphs are old Thassilonian: 'Here stands…'"). Don't have them read it aloud, react or comment.
    - "I try to force the door" → resolve the attempt ("The door grinds open, wide enough to pass") and STOP. Don't have them step through.
    - "I attack" → resolve the attack, then say which actions remain. Don't add a move or a line of dialogue.
  - Checks you roll secretly (Perception, Knowledge, Sense Motive, …) are invisible. Never mention them: not that you rolled, not how many, not whether they succeeded (no "All three succeed", no "Perception 21"). Narrate only what the character notices or knows. A failed check simply produces nothing, or the misleading impression.
  - Companions and NPCs speak and act for themselves. The PC doesn't, unless the player says so.
- COMBAT:
  - Resolve every attack with `scripts/combat.py attack` (NPC: --roll/--dmg; PC: the player's --total/--damage). Never roll attacks separately.
  - The interface prints the combat log with all the numbers, after each turn. Narrate EVERY creature's turn in its own line or lines, matching the log. Never merge turns, never skip a creature, never contradict a number.
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

# ---------- terminal formatting ----------

BOLD, ITAL, DIM, CYAN, RESET = "\033[1m", "\033[3m", "\033[2m", "\033[36m", "\033[0m"
CLEAR_LINE = "\r\033[K"


def inline_md(s):
    s = re.sub(r"`([^`]+)`", CYAN + r"\1" + RESET, s)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", BOLD + ITAL + r"\1" + RESET, s)
    s = re.sub(r"\*\*(.+?)\*\*", BOLD + r"\1" + RESET, s)
    s = re.sub(r"(?<![\*\w])\*(?!\s)(.+?)(?<!\s)\*(?![\*\w])", ITAL + r"\1" + RESET, s)
    s = re.sub(r"(?<![_\w])_(?!\s)(.+?)(?<!\s)_(?![_\w])", ITAL + r"\1" + RESET, s)
    return s


class Renderer:
    """Line-buffered markdown-to-ANSI renderer for streamed text."""

    def __init__(self):
        self.buf = ""
        self.in_code = False

    def feed(self, text):
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self._line(line)

    def flush(self):
        if self.buf:
            self._line(self.buf)
            self.buf = ""

    def _line(self, line):
        if line.strip().startswith("```"):
            self.in_code = not self.in_code
            return
        if self.in_code:
            out = line
        elif re.match(r"^#{1,6} ", line):
            out = BOLD + inline_md(re.sub(r"^#{1,6} ", "", line)) + RESET
        elif line.startswith(">"):
            out = DIM + "│ " + RESET + ITAL + inline_md(line.lstrip("> ")) + RESET
        elif re.match(r"^\s*[-*] ", line):
            out = re.sub(r"^(\s*)[-*] ", r"\1• ", inline_md(line), count=1)
        elif re.match(r"^\|?\s*-{3,}", line) and "|" in line:
            return  # table separator row
        else:
            out = inline_md(line)
        sys.stdout.write(out + "\n")
        sys.stdout.flush()


class Spinner:
    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self):
        self.label = None
        self.start = 0.0
        self.lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def show(self, label):
        with self.lock:
            if self.label is None:
                self.start = time.time()
            self.label = label

    def hide(self):
        with self.lock:
            if self.label is not None:
                sys.stdout.write(CLEAR_LINE)
                sys.stdout.flush()
            self.label = None

    def _run(self):
        i = 0
        while True:
            time.sleep(0.12)
            with self.lock:
                if self.label is None:
                    continue
                secs = int(time.time() - self.start)
                sys.stdout.write(f"{CLEAR_LINE}{DIM}{self.FRAMES[i % len(self.FRAMES)]} {self.label}… {secs}s{RESET}")
                sys.stdout.flush()
            i += 1


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


# ---------- map ----------

def in_iterm():
    return os.environ.get("TERM_PROGRAM") == "iTerm.app" or os.environ.get("LC_TERMINAL") == "iTerm2"


class MapWatcher:
    def __init__(self, campaign, images):
        self.campaign = campaign
        self.images = images and in_iterm()
        self.seen = {}
        self.events_shown = None   # combat-log lines already printed for the current fight
        self.last_state = None

    def _events(self, state):
        """Print combat-log lines added since the last call (also after `end` archived the state)."""
        path = state
        if not path.exists():
            if self.last_state is None:
                return
            archives = sorted(path.parent.glob("archive/*.json"), key=lambda p: p.stat().st_mtime)
            if not archives:
                return
            path = archives[-1]
        try:
            evs = json.loads(path.read_text()).get("events", [])
        except (OSError, ValueError):
            return
        start = self.events_shown or 0
        if start > len(evs):
            start = 0
        if len(evs) > start:
            print(f"\n{DIM}── combat log ──{RESET}")
            for e in evs[start:]:
                print(f"{DIM}R{e.get('round', '?')}{RESET} {e.get('text', '')}")
        self.events_shown = len(evs)
        if not state.exists():   # the fight ended; start fresh next time
            self.events_shown, self.last_state = None, None
        else:
            self.last_state = state

    def _campaign(self):
        if self.campaign:
            return self.campaign
        states = sorted(REPO.glob("campaigns/*/dm/combat/current.json"), key=lambda p: p.stat().st_mtime)
        return states[-1].parents[2].name if states else None

    def _changed(self, path):
        if not path.exists():
            self.seen.pop(str(path), None)
            return False
        m = path.stat().st_mtime
        if self.seen.get(str(path)) == m:
            return False
        self.seen[str(path)] = m
        return True

    def prime(self):
        """Remember the current map files without printing (so only later changes show)."""
        camp = self._campaign()
        if camp:
            for rel in ("dm/combat/current.json", "players/combat-map.png"):
                self._changed(REPO / "campaigns" / camp / rel)
            state = REPO / "campaigns" / camp / "dm" / "combat" / "current.json"
            if state.exists():
                try:
                    self.events_shown = len(json.loads(state.read_text()).get("events", []))
                    self.last_state = state
                except (OSError, ValueError):
                    pass

    def show(self, force=False):
        camp = self._campaign()
        if not camp:
            if force:
                print(f"{DIM}(no active fight){RESET}")
            return
        state = REPO / "campaigns" / camp / "dm" / "combat" / "current.json"
        png = REPO / "campaigns" / camp / "players" / "combat-map.png"
        self._events(state)
        state_changed = self._changed(state)
        png_changed = self._changed(png) and state.exists()
        if not state.exists():
            if force:
                print(f"{DIM}(no active fight){RESET}")
            return
        if state_changed or force:
            r = subprocess.run([sys.executable, "scripts/combat.py", "-c", camp, "show"],
                               cwd=REPO, capture_output=True, text=True)
            if r.returncode == 0:
                print(f"\n{DIM}{'─' * 40}{RESET}\n{r.stdout.rstrip()}\n{DIM}{'─' * 40}{RESET}")
        if self.images and png.exists() and (png_changed or force):
            data = base64.b64encode(png.read_bytes()).decode()
            sys.stdout.write(f"\033]1337;File=inline=1;width=80%;preserveAspectRatio=1:{data}\a\n")
            sys.stdout.flush()


# ---------- the DM process ----------

class DM:
    """Runs `claude -p` and renders its event stream continuously in a reader thread.

    Replies can also arrive when the player didn't just write something, e.g. when a
    background task finishes. Those are shown as they come, and a turn only ends at the
    result that follows the echo (isReplay) of the player's own message.
    """

    def __init__(self, args, spinner, maps):
        self.args = args
        self.spinner = spinner
        self.maps = maps
        self.proc = None
        self.session_id = None
        self.debug = args.debug
        self.effort = args.effort
        self.stderr_lines = []
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.waiting = False       # a player turn is in progress
        self.armed = False         # the echo of the player's message has been seen
        self.idle_output = False   # text arrived while the player was at the prompt
        self._reset_render()

    def _reset_render(self):
        self.r = Renderer()
        self.streamed = set()
        self.current_msg = None
        self.printed_any = False

    # --- process ---
    def start(self, resume=None):
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--include-partial-messages", "--replay-user-messages",
               "--permission-mode", "dontAsk",
               "--allowedTools", *ALLOWED_TOOLS, "--disallowedTools", "AskUserQuestion",
               "--append-system-prompt", WRAPPER_PROMPT]
        if self.args.model:
            cmd += ["--model", self.args.model]
        if self.effort:
            cmd += ["--effort", self.effort]
        if resume:
            cmd += ["--resume", resume]
        env = dict(os.environ, CLAUDE_DM_MODE="play")
        self.proc = subprocess.Popen(cmd, cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        threading.Thread(target=self._drain_stderr, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _drain_stderr(self, proc):
        for line in proc.stderr:
            self.stderr_lines.append(line.rstrip())
            if self.debug:
                print(f"{DIM}[stderr] {line.rstrip()}{RESET}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()

    def restart(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.spinner.hide()
        self._reset_render()
        self.start(resume=self.session_id)

    # --- turns ---
    def turn(self, text):
        """Send one player message and block until its reply is complete. False if the process died."""
        if self.proc.poll() is not None:
            return False
        with self.lock:
            self.done.clear()
            self.waiting, self.armed = True, False
            self._reset_render()
            self.spinner.show("thinking")
        msg = {"type": "user", "message": {"role": "user", "content": text}}
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        while not self.done.wait(0.2):
            if self.proc.poll() is not None:
                break
        with self.lock:
            self.waiting = False
        self.spinner.hide()
        return self.proc.poll() is None

    # --- rendering ---
    def _read(self, proc):
        for line in proc.stdout:
            try:
                m = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                self._handle(m)
        self.done.set()

    def _text_starts(self):
        self.spinner.hide()
        if not self.waiting and not self.idle_output:
            sys.stdout.write("\n")   # replies that arrive at the prompt start on a fresh line
            self.idle_output = True

    def _handle(self, m):
        t = m.get("type")
        top = m.get("parent_tool_use_id") is None
        if t == "system" and m.get("subtype") == "init":
            self.session_id = m.get("session_id") or self.session_id
            save_session(self.session_id)
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
                    self.r.flush()
                    self.spinner.show(flavor(block.get("name"), not top))
                    if self.debug:
                        self.spinner.hide()
                        print(f"{DIM}[tool{'' if top else ' (sub)'}] {block.get('name')}{RESET}")
                elif block.get("type") == "text" and top:
                    self._text_starts()
                    if self.printed_any:
                        sys.stdout.write("\n")
            elif et == "content_block_delta" and top:
                d = e.get("delta", {})
                if d.get("type") == "text_delta":
                    self._text_starts()
                    self.streamed.add(self.current_msg)
                    self.r.feed(d.get("text", ""))
                    self.printed_any = True
            elif et == "content_block_stop" and top:
                self.r.flush()
        elif t == "assistant":
            content = m.get("message", {}).get("content", [])
            mid = m.get("message", {}).get("id")
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            if top and texts and mid not in self.streamed:
                self._text_starts()
                self.r.feed("\n".join(texts) + "\n")
                self.r.flush()
                self.printed_any = True
            elif self.debug and not top and texts:
                self.spinner.hide()
                print(f"{DIM}[subagent] {' '.join(texts)[:400]}{RESET}")
            if self.debug:
                for c in content:
                    if c.get("type") == "tool_use":
                        self.spinner.hide()
                        print(f"{DIM}[input] {json.dumps(c.get('input'))[:300]}{RESET}")
        elif t == "user" and self.debug:
            for c in (m.get("message", {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    body = c.get("content")
                    body = body if isinstance(body, str) else json.dumps(body)
                    self.spinner.hide()
                    print(f"{DIM}[result] {body[:300]}{RESET}")
        elif t == "result":
            self.r.flush()
            self.spinner.hide()
            self.session_id = m.get("session_id") or self.session_id
            save_session(self.session_id)
            if m.get("is_error"):
                print(f"{DIM}(the DM hit an error: {m.get('subtype')}; try again, or use :debug){RESET}")
            if self.waiting and self.armed:
                self.done.set()
            elif not self.waiting:
                # A reply nobody was waiting for (e.g. a background task finished): show it, then the prompt again.
                self.maps.show()
                if self.idle_output:
                    sys.stdout.write(f"\n{BOLD}>{RESET} ")
                    sys.stdout.flush()
                self.idle_output = False
                self._reset_render()


def save_session(sid):
    if not sid:
        return
    STATE.mkdir(exist_ok=True)
    (STATE / "last-session").write_text(sid)
    with (STATE / "sessions.log").open("a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')} {sid}\n")


def read_input():
    lines = []
    prompt = f"\n{BOLD}>{RESET} "
    while True:
        line = input(prompt)
        if line.endswith("\\"):
            lines.append(line[:-1])
            prompt = f"{BOLD}…{RESET} "
            continue
        lines.append(line)
        return "\n".join(lines).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resume", nargs="?", const="last", help="continue the last session, or a given session ID")
    ap.add_argument("--model", help="model alias or ID (default: your Claude Code default)")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                    help="thinking effort (default: medium; higher is slower but more careful)")
    ap.add_argument("--campaign", help="campaign slug for the map (default: the one with an active fight)")
    ap.add_argument("--no-images", action="store_true", help="don't show the PNG map inline")
    ap.add_argument("--debug", action="store_true", help="show tools and subagents")
    args = ap.parse_args()

    try:
        import readline  # noqa: F401  (line editing and history for input())
    except ImportError:
        pass

    resume = args.resume
    if resume == "last":
        f = STATE / "last-session"
        resume = f.read_text().strip() if f.exists() else None
        if not resume:
            print("No previous session found; starting a new one.")

    spinner = Spinner()
    maps = MapWatcher(args.campaign, not args.no_images)
    maps.prime()
    dm = DM(args, spinner, maps)
    dm.session_id = resume
    dm.start(resume=resume)

    print(f"{BOLD}Claude DM{RESET}  {DIM}(type :help for commands; effort {args.effort}){RESET}")
    if resume:
        print(f"{DIM}Resuming session {resume}. Type :map to see an ongoing fight.{RESET}")
    else:
        print(f"{DIM}New session. Try: /start-session <campaign>  or  /new-campaign{RESET}")

    while True:
        try:
            text = read_input()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        dm.idle_output = False
        if not text:
            continue
        if text in (":q", ":quit", ":exit"):
            break
        if text == ":help":
            print(__doc__.split("In-game commands")[1])
            continue
        if text == ":debug":
            dm.debug = not dm.debug
            print(f"{DIM}debug {'on' if dm.debug else 'off'}{RESET}")
            continue
        if text == ":map":
            maps.show(force=True)
            continue
        if text.startswith(":effort"):
            level = text.split()[-1]
            if level not in ("low", "medium", "high", "xhigh", "max"):
                print(f"{DIM}usage: :effort low|medium|high|xhigh|max (now {dm.effort}){RESET}")
                continue
            dm.effort = level
            dm.restart()
            print(f"{DIM}effort {level}; session resumed{RESET}")
            continue
        print()
        try:
            ok = dm.turn(text)
        except KeyboardInterrupt:
            spinner.hide()
            print(f"\n{DIM}(interrupted; restarting the DM session){RESET}")
            dm.restart()
            continue
        if not ok:
            spinner.hide()
            print(f"{DIM}(the DM process stopped; restarting and resuming the session){RESET}")
            if dm.stderr_lines:
                print(f"{DIM}{dm.stderr_lines[-1]}{RESET}")
            dm.restart()
            continue
        maps.show()

    dm.stop()
    if dm.session_id:
        print(f"{DIM}Session saved. Continue with: python3 play.py --resume{RESET}")


if __name__ == "__main__":
    main()
