#!/usr/bin/env python3
"""web.py: Claude DM in the browser (local only).

  python3 web.py                  open the browser on the campaign picker (continue, new session, new campaign)
  python3 web.py --campaign SLUG  skip the picker: continue that campaign's last conversation
  python3 web.py --resume [ID]    skip the picker: continue the last (or a given) conversation
  python3 web.py --effort high    think harder (slower); default is medium
  python3 web.py --port 8765 --no-browser --model <alias> --debug

Serves web/index.html on http://127.0.0.1:<port>. Only the DM's words reach the page;
tool calls stay hidden. During a fight, a side panel shows the map, initiative and the
combat log. Type :effort low|medium|high or :debug in the chat to change settings; switch
campaigns from the settings menu (it can end the running session first).

The DM process is locked to one campaign (CLAUDE_DM_CAMPAIGN): the campaign_lock hook and the
game tools refuse every other campaign's folder, so nothing crosses over between campaigns.
"""
from __future__ import annotations

import argparse
import json
import queue
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from dm_engine import (EFFORTS, REPO, CombatRunner, Engine, with_recap, campaign_for_session, campaign_title, is_campaign, remember_campaign, combat_snapshot, combat_state,
                       end_fight, fight_over, fight_over_prompt,
                       is_go_signal, list_campaigns, run_combat_step, slugify, step_due,
                       last_combat_events, last_session, load_history,
                       FLUSH_PROMPT, WISHES_QUESTION, close_prompt, session_in_progress, write_transcript)

WEB = REPO / "web"


class Hub:
    """Keeps the page's chat history and fans engine events out to connected browsers."""

    def __init__(self, campaign_arg: str | None) -> None:
        """Args:
            campaign_arg: the campaign in play, or None: the page opens the campaign picker.
        """
        self.campaign_arg = campaign_arg
        self.runner: CombatRunner | None = None   # plays the NPC steps in its own small context
        self.runner_model: str | None = None
        self.runner_effort = "low"
        self.log_mark = 0   # combat-log lines the main DM has already been told about
        self.lock = threading.RLock()
        self.subs: list[queue.Queue[dict[str, Any]]] = []
        self.history: list[dict[str, Any]] = []   # {"role": "player"|"dm"|"system"|"log", ...}
        self.turn_dm: int | None = None           # index of the DM message of the current turn
        self.status: str | None = None
        self.status_since: float | None = None
        self.combat: dict[str, Any] | None = None  # last snapshot sent
        self.engine: Engine | None = None         # set by main() before the server starts
        self.worker: threading.Thread | None = None
        self.shown_campaign: str | None = None     # the campaign the page's title shows
        self.closing = False                       # /end-session asked the stars & wishes; the next message answers
        self.fight_ended = False                   # a fight ended during this turn (compaction threshold)

    @property
    def eng(self) -> Engine:
        """The engine; only valid once main() has created it."""
        assert self.engine is not None, "engine not started"
        return self.engine

    # --- plumbing ---
    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        """Register a browser connection; returns the queue its events arrive on."""
        q: queue.Queue[dict[str, Any]] = queue.Queue()
        with self.lock:
            self.subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any]]) -> None:
        """Forget a closed browser connection."""
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)

    def publish(self, ev: dict[str, Any]) -> None:
        """Send an event to every connected browser."""
        with self.lock:
            for q in list(self.subs):
                q.put(ev)

    def campaign(self) -> str | None:
        """The campaign in play (None until one is chosen in the picker)."""
        return self.campaign_arg

    def hello(self) -> dict[str, Any]:
        """The first event a browser gets: title, chat history, busy state, status, settings and the fight."""
        camp = self.campaign()
        with self.lock:
            self.shown_campaign = camp
            return {"type": "hello", "title": campaign_title(camp), "campaign": camp, "picker": camp is None,
                    "session": self.engine.session_id if self.engine else None,
                    "history": list(self.history), "busy": bool(self.engine and self.engine.busy),
                    "status": self.status, "status_since": self.status_since,
                    "effort": self.engine.effort if self.engine else None,
                    "debug": bool(self.engine and self.engine.debug),
                    "combat": self.combat or {"active": False}}

    # --- engine events ---
    def on_event(self, ev: dict[str, Any]) -> None:
        """Handle an engine event: update the chat history and forward it to the browsers."""
        t = ev["type"]
        with self.lock:
            if t == "status":
                self.status = ev["label"]
                self.status_since = time.time() if ev["label"] else None
                ev = dict(ev, since=self.status_since)
            elif t == "text_start":
                if self.turn_dm is None:
                    self.history.append({"role": "dm", "text": ""})
                    self.turn_dm = len(self.history) - 1
                    ev = dict(ev, new=True)
                else:
                    self.history[self.turn_dm]["text"] += "\n\n"
                    ev = dict(ev, new=False)
            elif t == "text" and self.turn_dm is not None:
                self.history[self.turn_dm]["text"] += ev["delta"]
            elif t == "error":
                self.history.append({"role": "system", "text": ev["message"]})
            elif t == "debug":
                self.history.append({"role": "debug", "text": ev["line"]})
            self.publish(ev)
            if t == "turn_end":
                self.turn_dm = None
                if not ev["solicited"]:   # player turns refresh in _run_turn
                    self.refresh_combat()
                    self.refresh_campaign()

    def refresh_campaign(self) -> None:
        """Tell the browsers when the campaign in play changed (e.g. after /start-session or /new-campaign)."""
        camp = self.campaign()
        with self.lock:
            if camp == self.shown_campaign:
                return
            self.shown_campaign = camp
            self.publish({"type": "campaign", "campaign": camp, "title": campaign_title(camp)})

    def fight(self) -> dict[str, Any] | None:
        """The fight to show: only once the DM has engaged combat in this session (a saved fight from
        an earlier session stays hidden until the DM resumes it)."""
        if not (self.engine and self.engine.combat_engaged):
            return None
        return combat_snapshot(self.campaign())

    def refresh_combat(self) -> None:
        """Send the current fight to the browsers, or a 'fight is over' card when it just ended."""
        camp = self.campaign()
        snap = self.fight()
        with self.lock:
            was_active = bool(self.combat and self.combat.get("active"))
            if snap:
                self.combat = snap
                self.publish(dict(snap, type="combat"))
            elif was_active and camp:
                final = last_combat_events(camp)
                self.combat = {"active": False}
                self.history.append({"role": "log", "title": "The fight is over", "events": final})
                self.fight_ended = True   # a scene break: compact sooner after this turn
                self.publish({"type": "combat", "active": False, "final_events": final})

    # --- player input ---
    def send(self, text: str) -> tuple[int, str]:
        """Accept a player message (or a ':command') and run the turn in a worker thread.

        Returns:
            (HTTP status, message): 202 when accepted, 409 while the DM is busy, 400 for empty input.
        """
        text = text.strip()
        if not text:
            return 400, "empty"
        if text.startswith(":"):
            return self.command(text)
        if not self.campaign():
            return 409, "Choose a campaign first."
        parts = text.split()
        if parts[0] == "/new-campaign" or (parts[0] == "/start-session" and len(parts) > 1 and parts[1] != self.campaign()):
            return 409, "Use the campaign menu (the gear) to start or switch campaigns."
        if parts[0] == "/end-session" or self.closing:
            return self._close_input(text)
        with self.lock:
            if self.busy():
                return 409, "The DM is still busy."
            self.history.append({"role": "player", "text": text})
            self.turn_dm = None
            self.publish({"type": "player", "text": text})
            self.publish({"type": "busy", "busy": True})
            st = combat_state(self.campaign()) if self.eng.combat_engaged else None
            step = bool(st and not st.get("awaiting") and is_go_signal(text, st))
            self.worker = threading.Thread(target=self._run_step if step else self._run_turn, args=(text,), daemon=True)
            self.worker.start()
        return 202, "ok"

    # --- closing a session (see FLUSH_PROMPT in dm_engine) ---
    def _close_input(self, text: str) -> tuple[int, str]:
        """/end-session: ask the stars & wishes here (no DM call); the answer closes the session in
        a fresh conversation, "cancel" goes back to the game."""
        with self.lock:
            if self.busy():
                return 409, "The DM is still busy."
            self.history.append({"role": "player", "text": text})
            self.publish({"type": "player", "text": text})
            if not self.closing:
                if session_in_progress(self.campaign()) is None:
                    self.closing = False
                    self.system("No session is in progress to end. Start one from the campaign menu (the gear).")
                    return 202, "ok"
                self.closing = True
                self.interface_says(WISHES_QUESTION)
                return 202, "ok"
            self.closing = False
            if text.lower().strip(" .!\"'") in ("cancel", "keep playing", "never mind", "nevermind"):
                self.system("Okay, back to the game.")
                return 202, "ok"
            self.publish({"type": "busy", "busy": True})
            self.worker = threading.Thread(target=self._run_close, args=(text,), daemon=True)
            self.worker.start()
        return 202, "ok"

    def _run_close(self, wishes: str) -> None:
        """Worker thread: close the session in a fresh conversation."""
        self.close_session(wishes)
        self.refresh_campaign()
        self.publish({"type": "busy", "busy": False})

    def close_session(self, wishes: str) -> bool:
        """The playing DM brings its live log up to date (one short, hidden exchange); then a fresh
        conversation, locked to the same campaign, runs /end-session from the files and the
        session's transcript. Its reply (award, recap, teaser) is shown. Returns whether it ran."""
        camp = self.campaign()
        nn = session_in_progress(camp)
        if not camp or nn is None:
            return False
        self.system("Wrapping up the session…")
        if self.eng.alive() and self.eng.session_id:
            self.eng.hold()
            try:
                self._exchange(FLUSH_PROMPT)
            finally:
                self.eng.release(publish=False)
        transcript = write_transcript(camp, nn, self.history)
        if self.runner:
            self.runner.stop()
            self.runner = None
        self.eng.new_session()   # same campaign lock, a fresh and small context
        with self.lock:
            self.turn_dm = None
        ok = self._exchange(close_prompt(camp, nn, wishes, transcript))
        self._pin_campaign()   # "continue" now picks up the closing conversation
        return ok

    def busy(self) -> bool:
        """Whether a turn (or a campaign switch) is running."""
        return self.eng.busy or bool(self.worker and self.worker.is_alive())

    def _pin_campaign(self) -> None:
        """After a reply: record which campaign this conversation plays (for continuing it later)."""
        remember_campaign(self.engine.session_id if self.engine else None, self.campaign_arg)

    def _run_turn(self, text: str) -> None:
        """Worker thread: send the message to the engine and wait for the reply. If that reply
        leaves a combat step due (the player ended their turn in the same message, or a fight was
        just set up with the PC first), the step runs right after."""
        camp = self.campaign()
        if camp and self.eng.combat_engaged and combat_state(camp):
            self._get_runner(camp).heard(text)   # allies hear what the PC says (no process starts here)
        ok = self._exchange(self._with_recap(text))
        self.refresh_combat()
        if ok and self.eng.combat_engaged and step_due(self.campaign(), text):
            self._step()
        self.end_fight_if_over()
        self._compact()
        self._pin_campaign()
        self.refresh_campaign()
        self.publish({"type": "busy", "busy": False})

    def _run_step(self, text: str) -> None:
        """Worker thread for a go signal ("next", "end turn"): one engine-driven combat step."""
        self._step()
        self.end_fight_if_over()
        self._compact()
        self.publish({"type": "busy", "busy": False})

    def _compact(self) -> None:
        """Between turns: compact the conversation when it's large, sooner right after a fight."""
        after_fight, self.fight_ended = self.fight_ended, False
        self.eng.compact_if_large(after_fight)

    def _with_recap(self, text: str) -> str:
        """The player's message for the main DM, with what the combat runner played since its last
        reply in front (only the main DM sees the recap; the chat shows the player's text)."""
        st = combat_state(self.campaign()) or {}
        events = st.get("events", [])
        if self.log_mark > len(events):   # a new fight
            self.log_mark = 0
        lines = [f"R{e.get('round', '?')} {e.get('text', '')}" for e in events[self.log_mark:]]
        self.log_mark = len(events)
        recap = self.runner.take_recap() if self.runner else ""
        return with_recap(text, recap, lines if recap else [], st)

    def _get_runner(self, camp: str) -> CombatRunner:
        """The combat runner for this campaign (a new one when the campaign changes)."""
        if self.runner is None or self.runner.campaign != camp:
            if self.runner:
                self.runner.stop()

            def after() -> None:
                with self.lock:
                    self.turn_dm = None
                self.refresh_combat()

            self.runner = CombatRunner(self.on_event, camp, model=self.runner_model, effort=self.runner_effort, after_send=after)
        self.runner.engine.telemetry_session = self.eng.session_id
        return self.runner

    def _step(self) -> None:
        """Run one combat step, refreshing the combat panel after each DM reply. NPC steps go to the
        combat runner; creatures the main DM plays (main_dm) go to the main DM."""
        camp = self.campaign()
        if not camp:
            return

        def send(instruction: str) -> bool:
            ok = self._exchange(instruction)
            self.refresh_combat()
            return ok

        result = run_combat_step(self.eng, camp, send, runner=self._get_runner(camp))
        self.refresh_combat()
        if result in ("pc", "pc-quiet"):   # announced here, once the NPCs are really done (follow-up moves included)
            st = combat_state(camp) or {}
            pc = next((t for t in st.get("tokens", []) if t["token"] == st.get("turn")), None)
            self.system(f"Your turn{', ' + pc['name'] if pc else ''}.")

    def _exchange(self, text: str) -> bool:
        """Send one message and wait for the reply; restart (resuming) if the process died.
        Returns whether the reply completed."""
        ok = self.eng.send(text)
        if not ok:
            self.system("The DM process stopped. Restarting and resuming the session…")
            self.eng.restart()
        with self.lock:
            self.turn_dm = None
        return ok

    def open_campaign(self, slug: str, mode: str, end_current: bool = False, name: str = "", pitch: str = "") -> tuple[int, str]:
        """Start playing a campaign (from the picker or the menu). mode: "continue" (resume its last
        conversation), "fresh" (a new conversation, /start-session), or "new" (create it: /new-campaign,
        with `name` and an optional `pitch`). The DM process is restarted locked to that campaign.
        Returns (HTTP status, message)."""
        if mode == "new":
            slug = slugify(name)
            if not slug:
                return 400, "Give the campaign a name."
            if (REPO / "campaigns" / slug).exists():
                return 409, f"A campaign folder '{slug}' already exists: pick another name."
        elif mode not in ("continue", "fresh") or not is_campaign(slug):
            return 404, "No such campaign."
        with self.lock:
            if self.busy():
                return 409, "The DM is still busy."
            self.publish({"type": "busy", "busy": True})
            self.worker = threading.Thread(target=self._run_open, args=(slug, mode, end_current, name, pitch), daemon=True)
            self.worker.start()
        return 202, "ok"

    def switch(self, slug: str, end_current: bool) -> tuple[int, str]:
        """The settings menu's switch: a fresh session of another campaign."""
        return self.open_campaign(slug, "fresh", end_current)

    def _run_open(self, slug: str, mode: str, end_current: bool, name: str, pitch: str) -> None:
        """Worker thread for open_campaign()."""
        old = self.campaign()
        if end_current and old and session_in_progress(old) is not None:
            self.system(f"Ending the session of {campaign_title(old)} first…")
            self.close_session("skip (the player is switching to another campaign)")
        self.closing = False
        if self.runner:
            self.runner.stop()
            self.runner = None
        resume = None
        if mode == "continue":
            resume = next((c["session"] for c in list_campaigns() if c["slug"] == slug), None)
            if not resume:
                mode = "fresh"   # nothing to continue: start its next session
        self.eng.stop()
        self.eng.campaign = slug   # the lock: hooks and game tools refuse every other campaign
        self.eng.combat_engaged = False
        with self.lock:
            self.campaign_arg = slug
            self.history = load_history(resume) if resume else []
            self.turn_dm, self.log_mark = None, 0
            self.combat = {"active": False}   # nothing shown until the DM engages (or resumes) a fight
        if resume:
            self.eng.start(resume=resume)
        else:
            self.eng.new_session()
        with self.lock:
            self.publish(self.hello())
        if resume:
            self._pin_campaign()
            self.system(f"Continuing {campaign_title(slug)}. Say what you do, or \"recap\" for a reminder.")
            self.resume_fight()
            self.publish({"type": "busy", "busy": False})
            return
        text = (f"/new-campaign slug={slug} {pitch or name}".strip() if mode == "new" else f"/start-session {slug}")
        with self.lock:
            self.history.append({"role": "player", "text": text})
            self.publish({"type": "player", "text": text})
        self._run_turn(text)

    def end_fight_if_over(self) -> None:
        """After a turn or step: if no enemy is left standing and nobody is dying, end the encounter
        (the interface runs combat_end) and let the main DM narrate the aftermath."""
        camp = self.campaign()
        why = fight_over(camp) if camp and self.eng.combat_engaged else None
        if not why or not camp:
            return
        try:
            report = end_fight(camp)
        except RuntimeError as e:
            self.system(f"The fight looks over, but ending it failed: {e}")
            return
        if self.runner:
            self.runner.stop()
            self.runner = None
        self.refresh_combat()   # the panel closes with the "fight is over" card
        self._exchange(fight_over_prompt(why, report))
        self.refresh_combat()

    def resume_fight(self) -> None:
        """A continued conversation with a fight in progress: show the fight at once (this conversation
        engaged it) and say whose turn it is, so the Next button or the player's turn picks it up."""
        st = combat_state(self.campaign())
        if not st or st.get("turn") is None:
            return
        self.eng.combat_engaged = True
        self.refresh_combat()
        cur = next((t for t in st.get("tokens", []) if t["token"] == st["turn"]), None)
        if cur and cur["side"] == "pc":
            self.system(f"The fight goes on: round {st.get('round')}, it's your turn.")
        elif cur:
            self.system(f"The fight goes on (round {st.get('round')}). Press Next (or say \"continue\") to play on.")

    def interface_says(self, text: str) -> None:
        """A message in the DM's place, written by the interface (markdown, like the DM's own)."""
        with self.lock:
            self.history.append({"role": "dm", "text": text})
            self.turn_dm = None
            for ev in ({"type": "text_start", "new": True}, {"type": "text", "delta": text}, {"type": "turn_end"}):
                self.publish(ev)

    def system(self, text: str) -> None:
        """Add a system note (not from the DM) to the chat."""
        with self.lock:
            self.history.append({"role": "system", "text": text})
            self.publish({"type": "system", "text": text})

    def command(self, text: str) -> tuple[int, str]:
        """Handle ':effort LEVEL' and ':debug'. Returns (HTTP status, message)."""
        parts = text.split()
        if parts[0] == ":effort" and len(parts) == 2 and parts[1] in EFFORTS:
            if self.eng.busy:
                return 409, "The DM is still busy."
            self.eng.set_effort(parts[1])
            self.system(f"Effort set to {parts[1]}. Session resumed.")
            self.publish({"type": "settings", "effort": parts[1], "debug": self.eng.debug})
            return 200, "ok"
        if parts[0] == ":debug":
            self.eng.debug = not self.eng.debug
            self.system(f"Debug {'on' if self.eng.debug else 'off'}.")
            self.publish({"type": "settings", "effort": self.eng.effort, "debug": self.eng.debug})
            return 200, "ok"
        self.system("Commands: :effort low|medium|high|xhigh|max, :debug")
        return 200, "ok"


def player_doc(camp: str | None, name: str) -> dict[str, str] | None:
    """Player-facing documents only (never dm/)."""
    base = REPO / "campaigns" / camp / "players" if camp else None
    if not base or not base.exists():
        return None
    if name == "character":
        files = sorted(p for p in (base / "characters").glob("*.md") if p.name != "README.md")
        title = "Character"
    elif name == "party":
        files, title = [base / "party.md"], "Party notes"
    elif name == "handouts":
        files = sorted(p for p in (base / "handouts").glob("*.md") if p.name != "README.md")
        title = "Handouts"
    else:
        return None
    parts = [p.read_text(encoding="utf-8") for p in files if p.exists()]
    return {"title": title, "markdown": "\n\n---\n\n".join(parts) or "*Nothing here yet.*"}


def make_handler(hub: Hub) -> type[BaseHTTPRequestHandler]:
    """Build the request handler class bound to this hub."""
    class Handler(BaseHTTPRequestHandler):
        """Serves the page, the event stream (SSE), player documents, and accepts messages."""

        def log_message(self, *args: Any) -> None:
            """Keep the console quiet (no access log)."""

        def _send(self, code: int, body: str | bytes, ctype: str = 'application/json; charset=utf-8') -> None:
            """Send a complete response with no-store caching."""
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            """Serve the page, /favicon.svg, /events, /campaigns and /doc?name=…"""
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
            if url.path == "/favicon.svg":
                return self._send(200, (WEB / "favicon.svg").read_bytes(), "image/svg+xml")
            if url.path == "/events":
                return self._events()
            if url.path == "/campaigns":
                return self._send(200, json.dumps({"current": hub.campaign(), "campaigns": list_campaigns()}))
            if url.path == "/doc":
                name = parse_qs(url.query).get("name", [""])[0]
                doc = player_doc(hub.campaign(), name)
                return self._send(200 if doc else 404, json.dumps(doc or {}))
            return self._send(404, "{}")

        def do_POST(self) -> None:
            """Accept a player message at /send, a campaign switch at /switch, or the picker's choice at /open."""
            path = urlparse(self.path).path
            if path not in ("/send", "/switch", "/open"):
                return self._send(404, "{}")
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._send(400, json.dumps({"error": "bad json"}))
            if path == "/switch":
                code, msg = hub.switch(str(body.get("campaign", "")), bool(body.get("end_current", True)))
            elif path == "/open":
                code, msg = hub.open_campaign(str(body.get("campaign", "")), str(body.get("mode", "continue")),
                                              bool(body.get("end_current", False)), str(body.get("name", "")),
                                              str(body.get("pitch", "")))
            else:
                code, msg = hub.send(body.get("text", ""))
            return self._send(code, json.dumps({"message": msg}))

        def _events(self) -> None:
            """Stream events to one browser (Server-Sent Events) until it disconnects."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = hub.subscribe()
            try:
                self._write(hub.hello())
                while True:
                    try:
                        ev = q.get(timeout=15)
                        self._write(ev)
                    except queue.Empty:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.unsubscribe(q)

        def _write(self, ev: dict[str, Any]) -> None:
            """Write one SSE message."""
            self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode("utf-8"))
            self.wfile.flush()

    return Handler


def main() -> None:
    """Command-line entry point: start the engine and serve the page on 127.0.0.1."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resume", nargs="?", const="last", help="continue the last session, or a given session ID")
    ap.add_argument("--model", help="model alias or ID (default: your Claude Code default)")
    ap.add_argument("--effort", default="medium", choices=EFFORTS)
    ap.add_argument("--runner-model", help="model for the combat runner (NPC turns); default: the DM's model")
    ap.add_argument("--runner-effort", default="low", choices=EFFORTS, help="thinking effort for NPC turns (default low)")
    ap.add_argument("--campaign", help="skip the picker: continue this campaign")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    resume = last_session() if args.resume == "last" else args.resume
    hub = Hub(None)
    engine = Engine(hub.on_event, model=args.model, effort=args.effort, debug=args.debug, record_session=True)
    hub.engine = engine
    hub.runner_model, hub.runner_effort = args.runner_model or args.model, args.runner_effort
    hub.combat = {"active": False}   # shown once the DM engages combat in this session (Hub.fight)
    # No campaign yet: the page opens the picker, and the DM process starts once one is chosen,
    # locked to it. --resume / --campaign choose up front.
    if resume:
        history = load_history(resume)
        camp = campaign_for_session(resume, history)
        if not camp:
            raise SystemExit(f"Don't know which campaign session {resume} plays; start without --resume and pick it.")
        hub.campaign_arg, hub.history = camp, history
        engine.campaign = camp
        engine.start(resume=resume)
        hub.resume_fight()
    elif args.campaign:
        if not is_campaign(args.campaign):
            raise SystemExit(f"No campaign '{args.campaign}'.")
        hub.open_campaign(args.campaign, "continue")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(hub))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Claude DM is running at {url}  (Ctrl-C to stop)")
    if resume:
        print(f"Resuming session {resume}.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        if hub.runner:
            hub.runner.stop()
        server.shutdown()
        if engine.session_id:
            print(f"Session saved. Continue with: python3 web.py --resume")


if __name__ == "__main__":
    main()
