"""dm_engine: go signals, the combat step driver, telemetry, and the player-safe snapshot."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import dm_engine as E
from tests.support import GOBLIN, PC_PROFILE, CampaignCase


class Signals(CampaignCase):
    def test_go_signals(self) -> None:
        self.assertTrue(E.is_go_signal("Next"))
        self.assertTrue(E.is_go_signal("end turn."))
        self.assertFalse(E.is_go_signal("next please"))
        self.assertTrue(E.ends_turn("I attack g1, 17 to hit. End turn."))

    def test_exchange_kinds(self) -> None:
        self.assertEqual(E.exchange_kind("[Combat step, sent by the interface. …"), "combat-step")
        self.assertEqual(E.exchange_kind("/start-session x"), "command:start-session")
        self.assertEqual(E.exchange_kind("end turn"), "go-signal")
        self.assertEqual(E.exchange_kind("I open the door"), "player")

    def test_error_line_prefers_the_real_error(self) -> None:
        self.assertEqual(E._error_line("Exit code 1\n$ next\ncombat error: nope"), "combat error: nope")
        self.assertEqual(E._error_line("Traceback (most recent call last):\n  x\nKeyError: 'ac'"), "KeyError: 'ac'")


class Stepping(CampaignCase):
    """The interface's step driver, with a fake DM that just records what it was asked."""

    def setUp(self) -> None:
        super().setUp()
        self.new(blank="12x6", light="dark")   # dark, so the hidden lurker stays hidden
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "D2", GOBLIN, init=15)
        self.add("h1", "Lurker", "H5", GOBLIN, "enemy", 12, "--hidden")
        self.add("g2", "Gob2", "J2", GOBLIN, init=10)
        self.asked: list[str] = []
        self.shown: list[dict] = []
        self.engine = E.Engine(lambda ev: self.shown.append(ev))

    def send(self, prompt: str) -> bool:
        tok = prompt.split("pointer is on ")[1].split()[0]
        self.asked.append(tok)
        for t in ("text_start", "text", "text_end"):
            self.engine.emit(type=t, delta=f"narration {tok}")
        return True

    def step(self) -> str:
        self.asked.clear()
        self.shown.clear()
        return E.run_combat_step(self.engine, self.slug, self.send)

    def test_fight_start_with_pc_first(self) -> None:
        self.assertTrue(E.step_due(self.slug, "I rolled 18"))
        self.assertEqual(self.step(), "pc-quiet")
        self.assertEqual(self.state()["turn"], "C")

    def test_one_visible_actor_per_step_and_hidden_text_dropped(self) -> None:
        self.step()                                   # onto Corin
        self.assertEqual(self.step(), "wait")         # end turn → g1 only
        self.assertEqual(self.asked, ["g1"])
        self.assertEqual(self.step(), "pc")           # h1 (hidden, silent), g2, then back to Corin
        self.assertEqual(self.asked, ["h1", "g2"])
        texts = {e["delta"] for e in self.shown if e["type"] == "text"}
        self.assertEqual(texts, {"narration g2"})     # h1 stayed hidden: its text was dropped
        self.assertEqual(self.state()["round"], 2)

    def test_step_message_has_context(self) -> None:
        prompts: list[str] = []
        self.step()
        E.run_combat_step(self.engine, self.slug, lambda p: prompts.append(p) or True)
        self.assertIn("Its attacks (combat_attack `with`): spear", prompts[0])
        self.assertIn("Tactical options", prompts[0])

    def test_endturn_flag(self) -> None:
        self.step()
        self.assertFalse(E.step_due(self.slug, "I attack"))
        self.run_cmd("endturn", "C")
        self.assertTrue(E.step_due(self.slug, "done"))


class Snapshot(CampaignCase):
    def test_player_safe(self) -> None:
        self.new(light="dark")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "D2", dict(GOBLIN, senses={"darkvision": 60}), init=15)
        self.add("h1", "Lurker", "H5", GOBLIN, "enemy", 12, "--hidden")
        snap = E.combat_snapshot(self.slug)
        assert snap is not None
        self.assertTrue(any(t["unseen"] for t in snap["map"]["tokens"] if t["token"] == "g1"))   # in the dark
        self.run_cmd("light", "add", "torch", "--on", "h1")
        snap = E.combat_snapshot(self.slug)
        assert snap is not None
        blob = json.dumps(snap)
        self.assertNotIn("Lurker", blob)                    # hidden tokens are never sent
        self.assertNotIn('"ac"', blob)                      # no AC
        self.assertIn('"light"', blob)
        srcs = snap["map"]["light"]["sources"]
        self.assertEqual(srcs[0]["by"], None)               # its light shows, its carrier doesn't


class Telemetry(CampaignCase):
    def test_record_written(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            old = E.TELEMETRY
            E.TELEMETRY = Path(d) / "t.jsonl"
            try:
                eng = E.Engine(lambda ev: None)
                eng._tel = {"start": 0, "kind": "player", "chars_in": 3, "tools": {}, "sub_tools": 0, "chars_out": 0}
                eng.waiting = eng.armed = True
                eng._handle({"type": "assistant", "parent_tool_use_id": None, "message": {"id": "m", "content": [
                    {"type": "tool_use", "id": "t1", "name": "mcp__dm__combat_attack", "input": {"attacker": "g1"}}]}})
                eng._handle({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "combat error: nope"}]}})
                eng._handle({"type": "result", "num_turns": 2})
                rec = json.loads(E.TELEMETRY.read_text().splitlines()[0])
                self.assertEqual(rec["tool_errors"], 1)
                self.assertEqual(rec["tools"][0]["error"], "combat error: nope")
            finally:
                E.TELEMETRY = old


class CampaignTracking(CampaignCase):
    """A session stays with its campaign, even when test campaigns are touched later."""

    def setUp(self) -> None:
        super().setUp()
        self._old = E.SESSION_CAMPAIGNS
        self._tmp = tempfile.TemporaryDirectory()
        E.SESSION_CAMPAIGNS = Path(self._tmp.name) / "sc.json"

    def tearDown(self) -> None:
        E.SESSION_CAMPAIGNS = self._old
        self._tmp.cleanup()
        super().tearDown()

    def test_test_folders_are_not_campaigns(self) -> None:
        self.assertFalse(E.is_campaign(self.slug))          # _test_…: never picked up
        self.assertFalse(E.is_campaign("_template"))
        self.assertNotEqual(E.active_campaign(None), self.slug)

    def test_recorded_and_history_fallback(self) -> None:
        real = next(p.name for p in (E.REPO / "campaigns").iterdir() if E.is_campaign(p.name))
        E.remember_campaign("sid-1", real)
        E.remember_campaign("sid-2", self.slug)              # a test folder is never recorded
        self.assertEqual(E.campaign_for_session("sid-1"), real)
        self.assertIsNone(E.campaign_for_session("sid-2"))
        hist = [{"role": "player", "text": f"/start-session {real}"}, {"role": "dm", "text": "Welcome back."}]
        self.assertEqual(E.campaign_for_session("unknown", hist), real)

    def test_web_hub_pins_the_campaign(self) -> None:
        import web
        real = next(p.name for p in (E.REPO / "campaigns").iterdir() if E.is_campaign(p.name))
        hub = web.Hub(None)
        hub.engine = type("FakeEngine", (), {"session_id": "sid-3"})()
        hub.follow_command(f"/start-session {real}")
        hub._pin_campaign()
        self.run_cmd("new", "--blank", "5x5")                 # a test campaign gets touched afterwards…
        self.assertEqual(hub.campaign(), real)                # …and the page stays with the real one
        self.assertEqual(E.campaign_for_session("sid-3"), real)
