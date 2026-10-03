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

    def test_fight_starts_right_after_setup_even_with_an_enemy_first(self) -> None:
        self.run_cmd("init", "g1", "25")                 # the goblin goes before Corin
        self.assertTrue(E.step_due(self.slug, "17"))
        self.assertEqual(self.step(), "pc")              # g1 plays at once, then it's Corin's turn
        self.assertEqual(self.asked, ["g1"])

    def test_engine_doesnt_record_sessions_by_default(self) -> None:
        self.assertFalse(E.Engine(lambda ev: None).record_session)

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

    def test_step_message_names_who_is_next(self) -> None:
        prompts: list[str] = []
        self.step()                                       # onto Corin
        E.run_combat_step(self.engine, self.slug, lambda p: prompts.append(p) or True)
        self.assertIn("it's Gob2's, not the player's", prompts[0])   # g1, then (h1), g2
        self.assertIn("don't write 'your turn'", prompts[0])

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

    def test_web_hub_needs_a_chosen_campaign(self) -> None:
        import web
        real = next(p.name for p in (E.REPO / "campaigns").iterdir() if E.is_campaign(p.name))
        hub = web.Hub(None)
        hub.engine = E.Engine(lambda ev: None)
        self.assertTrue(hub.hello()["picker"])
        self.assertEqual(hub.send("I look around")[0], 409)            # nothing before a campaign is chosen
        self.assertEqual(hub.open_campaign(real, "new", name=real)[0], 409)   # that folder exists
        self.assertEqual(hub.open_campaign("no-such-campaign", "continue")[0], 404)
        hub.campaign_arg = real
        self.assertFalse(hub.hello()["picker"])
        self.assertEqual(hub.send("/new-campaign")[0], 409)            # switching goes through the picker
        self.assertEqual(hub.send("/start-session some-other")[0], 409)


class CombatVisibility(CampaignCase):
    """A saved fight stays hidden until the DM engages combat in this session."""

    def test_which_tools_engage_combat(self) -> None:
        self.assertTrue(E.is_combat_tool("mcp__dm__combat_info", {}))
        self.assertTrue(E.is_combat_tool("mcp__dm__combat_setup", {}))
        self.assertFalse(E.is_combat_tool("mcp__dm__combat_profile_check", {}))
        self.assertFalse(E.is_combat_tool("mcp__dm__dice_roll", {}))
        self.assertTrue(E.is_combat_tool("Bash", {"command": "python3 scripts/combat.py -c x show"}))
        self.assertFalse(E.is_combat_tool("Bash", {"command": "python3 scripts/combat.py -c x profile check f.md"}))

    def test_engine_notices_combat_tools(self) -> None:
        eng = E.Engine(lambda ev: None)
        self.assertFalse(eng.combat_engaged)
        eng._handle({"type": "assistant", "parent_tool_use_id": None, "message": {"id": "m", "content": [
            {"type": "tool_use", "id": "t", "name": "mcp__dm__dice_roll", "input": {}}]}})
        self.assertFalse(eng.combat_engaged)
        eng._handle({"type": "assistant", "parent_tool_use_id": None, "message": {"id": "m2", "content": [
            {"type": "tool_use", "id": "t2", "name": "mcp__dm__combat_info", "input": {"what": "show"}}]}})
        self.assertTrue(eng.combat_engaged)

    def test_web_hides_a_saved_fight_until_engaged(self) -> None:
        import web
        self.new()
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        self.assertIsNone(hub.fight())                       # saved, but this session hasn't engaged it
        hub.engine.combat_engaged = True
        self.assertIsNotNone(hub.fight())


class NoBriefingLeaks(CampaignCase):
    """The DM-only combat briefing never reaches the player: not as history, not as thinking out loud."""

    def test_history_skips_interface_messages(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.jsonl"
            rows = [{"type": "user", "message": {"content": "I attack the goblin"}},
                    {"type": "user", "message": {"content": "[Combat step, sent by the interface. Tactical options: hits on 12+"}},
                    {"type": "assistant", "message": {"content": [{"type": "text", "text": "The goblin lunges."}]}}]
            path.write_text("\n".join(json.dumps(r) for r in rows))
            old = E.transcript_path
            E.transcript_path = lambda sid: path   # type: ignore[assignment]
            try:
                hist = E.load_history("x")
            finally:
                E.transcript_path = old   # type: ignore[assignment]
        self.assertEqual([m["text"] for m in hist], ["I attack the goblin", "The goblin lunges."])

    def held_text(self, events: list[dict], publish: bool = True) -> str:
        shown: list[dict] = []
        eng = E.Engine(lambda ev: shown.append(ev))
        eng.hold()
        for ev in events:
            if ev["type"] == "_tool":
                eng._held.append(ev)          # what the stream handler records at a tool call
            else:
                eng.emit(**ev)
        eng.release(publish=publish, after_tools=True)
        return "".join(e.get("delta", "") for e in shown if e["type"] == "text")

    def test_only_the_narration_after_the_tool_call(self) -> None:
        txt = lambda t: [{"type": "text_start"}, {"type": "text", "delta": t}, {"type": "text_end"}]
        out = self.held_text(txt("Best shot: move to M9, hits on 12+.") + [{"type": "_tool"}] + txt("The goblin shoots."))
        self.assertEqual(out, "The goblin shoots.")
        # narrated, then one more tool call (e.g. a log line): the narration is still shown
        out = self.held_text(txt("Thinking: hits on 12+.") + [{"type": "_tool"}] + txt("The goblin shoots.") + [{"type": "_tool"}])
        self.assertEqual(out, "The goblin shoots.")
        # a hidden actor that stays hidden: nothing at all
        self.assertEqual(self.held_text(txt("…"), publish=False), "")


class Runner(CampaignCase):
    """NPC steps go to the combat runner (with its own framing); main-DM creatures don't."""

    def setUp(self) -> None:
        super().setUp()
        self.new(blank="12x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "D2", GOBLIN, init=20)
        self.add("b1", "Boss", "H4", GOBLIN, "enemy", 15, "--main-dm")
        self.to_runner: list[str] = []
        self.to_main: list[str] = []
        self.runner = E.CombatRunner(lambda ev: None, self.slug)
        self.runner.send = lambda p: self.to_runner.append(p) or True        # type: ignore[method-assign]

    def main_send(self, p: str) -> bool:
        self.to_main.append(p)
        return True

    def test_routing_and_framing(self) -> None:
        eng = E.Engine(lambda ev: None)
        E.run_combat_step(eng, self.slug, self.main_send, runner=self.runner)     # g1: the runner
        self.assertEqual(len(self.to_runner), 1)
        self.assertIn(f"Campaign: {self.slug}", self.to_runner[0])
        self.assertIn("pointer is on g1", self.to_runner[0])
        E.run_combat_step(eng, self.slug, self.main_send, runner=self.runner)     # b1: the main DM
        self.assertEqual(len(self.to_main), 1)
        self.assertIn("pointer is on b1", self.to_main[0])

    def test_recap_and_history(self) -> None:
        self.runner.note("Gob", "The goblin lunges: 17 vs your AC 16, hit, 5 damage.", by_runner=True)
        self.runner.note("Boss", "The boss roars.", by_runner=False)          # main DM played it: no recap
        msg = E.with_recap("I attack the goblin", self.runner.take_recap(), ["R1 Gob → Corin: 17 — hit, 5 damage"])
        self.assertIn("The goblin lunges", msg)
        self.assertNotIn("The boss roars", msg)
        self.assertEqual(E.player_part(msg), "I attack the goblin")          # the chat shows only this
        self.assertIsNone(E.player_part("[Combat step, sent by the interface …]"))
        self.assertEqual(self.runner.take_recap(), "")                       # taken once
        self.assertEqual(E.with_recap("hi", "", []), "hi")

    def test_system_prompt_has_the_table(self) -> None:
        self.write("players/session-zero.md", "# Session Zero\n## Tone & Style\nGrim and gritty.\n## Safety Tools\n- **Lines (never):** spiders\n## Rules\nnot this\n")
        sp = E.runner_system_prompt(self.slug)
        self.assertIn("Grim and gritty", sp)
        self.assertIn("spiders", sp)
        self.assertNotIn("not this", sp)


class Skipping(CampaignCase):
    """Turns without decisions never reach the DM; the PC's turn line comes from the script."""

    def setUp(self) -> None:
        super().setUp()
        self.new(blank="12x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("a1", "Ally", "C2", dict(GOBLIN, con=12), side="ally", init=15)
        self.add("g1", "Gob", "J2", GOBLIN, init=10)
        self.asked: list[str] = []
        self.engine = E.Engine(lambda ev: None)

    def send(self, prompt: str) -> bool:
        self.asked.append(prompt.split("pointer is on ")[1].split()[0])
        return True

    def test_dying_and_dead_allies_get_no_step(self) -> None:
        self.run_cmd("hp", "a1", "-14")                       # dying (-2), above -Con
        E.run_combat_step(self.engine, self.slug, self.send)   # onto Corin
        E.run_combat_step(self.engine, self.slug, self.send)   # a1 (skipped, rolls to stabilize), g1
        self.assertEqual(self.asked, ["g1"])
        self.assertTrue(any("a1" in e["text"] or "Ally" in e["text"] for e in self.state()["events"]))
        self.run_cmd("hp", "a1", "-20")                       # dead
        import combat
        self.assertFalse(combat.in_fight(self.tok("a1")))

    def test_turn_line_and_snapshot(self) -> None:
        E.run_combat_step(self.engine, self.slug, self.send)   # Corin's turn
        line = E.turn_line(self.state())
        self.assertIn("Corin's turn (a NEW turn", line)
        self.assertIn("standard", line)
        self.assertIn("Now: round 1", E.with_recap("I attack", "", [], self.state()))
        snap = E.combat_snapshot(self.slug)
        self.assertEqual(snap["pc_actions_left"]["main"], ["standard", "move"])
        self.run_cmd("act", "C", "standard", "total defense")
        snap = E.combat_snapshot(self.slug)
        self.assertEqual(snap["pc_actions_left"]["main"], ["move"])


class FollowUp(CampaignCase):
    """After an NPC's standard action changes the situation, it gets one more look at its move."""

    def test_second_look_after_a_kill(self) -> None:
        self.new(blank="12x6")
        self.add("C", "Corin", "J5", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "B2", GOBLIN, init=20)
        self.add("a1", "Ally", "C2", GOBLIN, side="ally", init=10)
        prompts: list[str] = []

        def send(prompt: str) -> bool:
            prompts.append(prompt)
            if prompt.startswith("[Combat step, sent") and "pointer is on g1" in prompt:
                self.run_cmd("attack", "g1", "a1", "--roll", "1d20+99", "--dmg", "99")
            return True

        E.run_combat_step(E.Engine(lambda ev: None), self.slug, send)
        follow = [p for p in prompts if p.startswith("[Combat step continued")]
        self.assertEqual(len(follow), 1)
        self.assertIn("Ally went down", follow[0])
        self.assertIn("STANDARD ACTION IS SPENT", follow[0])

    def test_no_second_look_when_nothing_changed(self) -> None:
        self.new(blank="12x6")
        self.add("C", "Corin", "C2", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "B2", GOBLIN, init=20)
        prompts: list[str] = []

        def send(prompt: str) -> bool:
            prompts.append(prompt)
            if "pointer is on g1" in prompt:
                self.run_cmd("attack", "g1", "C", "--roll", "1d20+0", "--dmg", "1")
            return True

        E.run_combat_step(E.Engine(lambda ev: None), self.slug, send)
        self.assertFalse([p for p in prompts if p.startswith("[Combat step continued")])


class ResumeFight(CampaignCase):
    def test_continuing_shows_the_fight_and_whose_turn(self) -> None:
        import web
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "E2", GOBLIN, init=20)
        self.run_cmd("next")                                   # the goblin holds the turn
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        self.assertIsNone(hub.fight())                         # a new conversation doesn't show an old fight…
        hub.resume_fight()                                     # …a continued one does
        self.assertTrue(hub.fight()["active"])
        self.assertIn("Press Next", hub.history[-1]["text"])


class FightOver(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", dict(PC_PROFILE, con=12), side="pc", init=5)
        self.add("g1", "Gob", "E2", GOBLIN, init=20)
        self.add("h1", "Lurker", "G5", GOBLIN, "enemy", 15, "--hidden")

    def test_over_only_when_no_enemy_stands_and_nobody_dies(self) -> None:
        import combat
        self.run_cmd("hp", "g1", "-20")
        self.assertIsNone(combat.fight_over(self.state()))            # the hidden lurker is still there
        self.run_cmd("remove", "h1")                                   # fled
        self.assertEqual(combat.fight_over(self.state()), "no enemy is left standing")
        self.run_cmd("hp", "C", "-32")                                 # Corin is dying (-2)
        self.assertIsNone(combat.fight_over(self.state()))
        self.run_cmd("cond", "C", "add", "stable")
        self.assertIsNotNone(combat.fight_over(self.state()))

    def test_web_hub_ends_the_fight(self) -> None:
        import web
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        hub.engine.combat_engaged = True
        sent: list[str] = []
        hub._exchange = lambda text: sent.append(text) or True       # type: ignore[method-assign]
        hub.end_fight_if_over()
        self.assertEqual(sent, [])                                     # still enemies up
        self.run_cmd("hp", "g1", "-20")
        self.run_cmd("remove", "h1")
        hub.end_fight_if_over()
        self.assertFalse(E.combat_state(self.slug))                    # ended and archived
        self.assertTrue(sent and sent[0].startswith("[The fight is over"))
        self.assertIn("XP", sent[0])


class AnnounceTurn(CampaignCase):
    def test_follow_up_comes_before_the_players_turn(self) -> None:
        """The last NPC before the PC kills its target and gets a follow-up: no step message asks for
        'your turn', and the hub announces the PC's turn only after the follow-up."""
        import web
        self.new(blank="12x6")
        self.add("C", "Corin", "J5", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "B2", GOBLIN, init=20)
        self.add("a1", "Ally", "C2", GOBLIN, side="ally", init=10)
        self.run_cmd("hp", "a1", "-100")                        # out of the way: only g1 acts before Corin
        self.add("a2", "Ally2", "C3", GOBLIN, side="ally", init=1)
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        hub.engine.combat_engaged = True
        order: list[str] = []

        def exchange(prompt: str) -> bool:
            order.append(prompt[:40])
            self.assertNotIn("say so", prompt)
            if "pointer is on g1" in prompt:
                self.run_cmd("attack", "g1", "a2", "--roll", "1d20+99", "--dmg", "99")
            return True
        hub._exchange = exchange                                 # type: ignore[method-assign]
        hub._get_runner = lambda camp: None                      # type: ignore[method-assign]  # never a real process
        hub.system = lambda text: order.append("SYSTEM " + text)   # type: ignore[method-assign]
        hub._step()
        self.assertTrue(order[-1].startswith("SYSTEM Your turn, Corin"), order)
        self.assertTrue(any(o.startswith("[Combat step continued") for o in order[:-1]))
