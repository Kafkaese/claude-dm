#!/usr/bin/env python3
"""web.py: Claude DM in the browser (local only).

  python3 web.py                  start a new session and open the browser
  python3 web.py --resume         continue the last session (its chat history is shown)
  python3 web.py --resume ID      continue a specific session
  python3 web.py --effort high    think harder (slower); default is medium
  python3 web.py --port 8765 --no-browser --campaign <slug> --model <alias> --debug

Serves web/index.html on http://127.0.0.1:<port>. Only the DM's words reach the page;
tool calls stay hidden. During a fight, a side panel shows the map, initiative and the
combat log. Type :effort low|medium|high or :debug in the chat to change settings.
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

from dm_engine import (EFFORTS, REPO, Engine, active_campaign, campaign_title, combat_snapshot,
                       last_combat_events, last_session, load_history, map_png_path)

WEB = REPO / "web"


class Hub:
    """Keeps the page's chat history and fans engine events out to connected browsers."""

    def __init__(self, campaign_arg: str | None) -> None:
        """Args:
            campaign_arg: the --campaign option, or None to use the most recently played campaign.
        """
        self.campaign_arg = campaign_arg
        self.lock = threading.RLock()
        self.subs: list[queue.Queue[dict[str, Any]]] = []
        self.history: list[dict[str, Any]] = []   # {"role": "player"|"dm"|"system"|"log", ...}
        self.turn_dm: int | None = None           # index of the DM message of the current turn
        self.status: str | None = None
        self.status_since: float | None = None
        self.combat: dict[str, Any] | None = None  # last snapshot sent
        self.engine: Engine | None = None         # set by main() before the server starts
        self.worker: threading.Thread | None = None

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
        """The campaign in play."""
        return active_campaign(self.campaign_arg)

    def hello(self) -> dict[str, Any]:
        """The first event a browser gets: title, chat history, busy state, status, settings and the fight."""
        camp = self.campaign()
        with self.lock:
            return {"type": "hello", "title": campaign_title(camp), "campaign": camp,
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

    def refresh_combat(self) -> None:
        """Send the current fight to the browsers, or a 'fight is over' card when it just ended."""
        camp = self.campaign()
        snap = combat_snapshot(camp)
        with self.lock:
            was_active = bool(self.combat and self.combat.get("active"))
            if snap:
                self.combat = snap
                self.publish(dict(snap, type="combat"))
            elif was_active and camp:
                final = last_combat_events(camp)
                self.combat = {"active": False}
                self.history.append({"role": "log", "title": "The fight is over", "events": final})
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
        with self.lock:
            if self.eng.busy or (self.worker and self.worker.is_alive()):
                return 409, "The DM is still busy."
            self.history.append({"role": "player", "text": text})
            self.turn_dm = None
            self.publish({"type": "player", "text": text})
            self.publish({"type": "busy", "busy": True})
            self.worker = threading.Thread(target=self._run_turn, args=(text,), daemon=True)
            self.worker.start()
        return 202, "ok"

    def _run_turn(self, text: str) -> None:
        """Worker thread: send the message to the engine and wait for the reply."""
        ok = self.eng.send(text)
        if not ok:
            self.system("The DM process stopped. Restarting and resuming the session…")
            self.eng.restart()
        with self.lock:
            self.turn_dm = None
        self.refresh_combat()
        self.publish({"type": "busy", "busy": False})

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
            """Serve the page, /events, /map.png and /doc?name=…"""
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
            if url.path == "/events":
                return self._events()
            if url.path == "/map.png":
                camp = hub.campaign()
                png = map_png_path(camp) if camp else None
                if png and png.exists():
                    return self._send(200, png.read_bytes(), "image/png")
                return self._send(404, "{}")
            if url.path == "/doc":
                name = parse_qs(url.query).get("name", [""])[0]
                doc = player_doc(hub.campaign(), name)
                return self._send(200 if doc else 404, json.dumps(doc or {}))
            return self._send(404, "{}")

        def do_POST(self) -> None:
            """Accept a player message at /send."""
            if urlparse(self.path).path != "/send":
                return self._send(404, "{}")
            length = int(self.headers.get("Content-Length") or 0)
            try:
                text = json.loads(self.rfile.read(length) or b"{}").get("text", "")
            except ValueError:
                return self._send(400, json.dumps({"error": "bad json"}))
            code, msg = hub.send(text)
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
    ap.add_argument("--campaign", help="campaign slug (default: the most recently played)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    resume = last_session() if args.resume == "last" else args.resume
    hub = Hub(args.campaign)
    if resume:
        hub.history = load_history(resume)
    engine = Engine(hub.on_event, model=args.model, effort=args.effort, debug=args.debug)
    hub.engine = engine
    engine.start(resume=resume)
    hub.combat = combat_snapshot(hub.campaign()) or {"active": False}

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
        server.shutdown()
        if engine.session_id:
            print(f"Session saved. Continue with: python3 web.py --resume")


if __name__ == "__main__":
    main()
