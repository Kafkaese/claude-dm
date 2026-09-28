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

from dm_engine import EFFORTS, REPO, Engine, last_session

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


# ---------- terminal frontend ----------

class Terminal:
    """Turns engine events into terminal output."""

    def __init__(self, spinner, maps):
        self.spinner = spinner
        self.maps = maps
        self.r = Renderer()
        self.at_prompt = False      # the player is typing; replies arriving now need a fresh line
        self.idle_output = False
        self.blocks = 0

    def on_event(self, ev):
        t = ev["type"]
        if t == "status":
            if ev["label"]:
                self.spinner.show(ev["label"])
            else:
                self.spinner.hide()
        elif t == "text_start":
            self.spinner.hide()
            if self.at_prompt and not self.idle_output:
                sys.stdout.write("\n")
                self.idle_output = True
            if self.blocks:
                sys.stdout.write("\n")
            self.blocks += 1
        elif t == "text":
            self.r.feed(ev["delta"])
        elif t == "text_end":
            self.r.flush()
        elif t == "turn_end":
            self.r.flush()
            self.spinner.hide()
            if not ev["solicited"]:
                self.maps.show()
                if self.idle_output:
                    sys.stdout.write(f"\n{BOLD}>{RESET} ")
                    sys.stdout.flush()
                self.idle_output = False
                self.blocks = 0
        elif t == "error":
            self.spinner.hide()
            print(f"{DIM}({ev['message']}){RESET}")
        elif t == "debug":
            self.spinner.hide()
            print(f"{DIM}{ev['line']}{RESET}")

    def before_turn(self):
        self.at_prompt, self.idle_output, self.blocks = False, False, 0
        self.r = Renderer()

    def after_turn(self):
        self.at_prompt = True


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
    ap.add_argument("--effort", default="medium", choices=EFFORTS,
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
        resume = last_session()
        if not resume:
            print("No previous session found; starting a new one.")

    spinner = Spinner()
    maps = MapWatcher(args.campaign, not args.no_images)
    maps.prime()
    term = Terminal(spinner, maps)
    dm = Engine(term.on_event, model=args.model, effort=args.effort, debug=args.debug)
    dm.start(resume=resume)

    print(f"{BOLD}Claude DM{RESET}  {DIM}(type :help for commands; effort {args.effort}){RESET}")
    if resume:
        print(f"{DIM}Resuming session {resume}. Type :map to see an ongoing fight.{RESET}")
    else:
        print(f"{DIM}New session. Try: /start-session <campaign>  or  /new-campaign{RESET}")

    term.after_turn()
    while True:
        try:
            text = read_input()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        term.idle_output = False
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
            if level not in EFFORTS:
                print(f"{DIM}usage: :effort low|medium|high|xhigh|max (now {dm.effort}){RESET}")
                continue
            dm.set_effort(level)
            print(f"{DIM}effort {level}; session resumed{RESET}")
            continue
        print()
        term.before_turn()
        try:
            ok = dm.send(text)
        except KeyboardInterrupt:
            spinner.hide()
            print(f"\n{DIM}(interrupted; restarting the DM session){RESET}")
            dm.restart()
            term.after_turn()
            continue
        term.after_turn()
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
