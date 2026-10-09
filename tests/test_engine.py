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
    def test_error_line_keeps_the_reason(self) -> None:
        import dm_engine
        body = "[1] combat_move: invalid arguments:\n  combat_move: unknown field 'stp'\n(stopped; nothing after this ran)"
        self.assertIn("unknown field 'stp'", dm_engine._error_line(body))
        self.assertEqual(dm_engine._error_line("combat error: it isn't C's turn"), "combat error: it isn't C's turn")

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
        recorded = json.loads(E.SESSION_CAMPAIGNS.read_text())
        self.assertEqual(recorded.get("sid-1"), real)
        self.assertNotIn("sid-2", recorded)

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

    def test_the_player_ends_a_finished_fight(self) -> None:
        """The final turn stays on screen: the snapshot says over (End combat), the hub says so once,
        and the player's next message ends the fight, reaching the DM with the aftermath."""
        import web
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        hub.engine.combat_engaged = True
        sent: list[str] = []
        notes: list[str] = []
        hub._exchange = lambda text: sent.append(text) or True       # type: ignore[method-assign]
        hub.system = lambda text: notes.append(text)                   # type: ignore[method-assign]
        hub._get_runner = lambda camp: None                            # type: ignore[method-assign]
        self.run_cmd("hp", "g1", "-20")
        self.run_cmd("remove", "h1")
        self.assertTrue(E.combat_snapshot(self.slug)["over"])
        hub.announce_fight_over()
        hub.announce_fight_over()
        self.assertEqual(len(notes), 1)                                # said once
        self.assertTrue(E.combat_state(self.slug))                     # not ended by itself
        hub._run_turn("I search the goblin's pockets")
        self.assertFalse(E.combat_state(self.slug))
        self.assertEqual(len(sent), 1)
        self.assertIn("I search the goblin's pockets", sent[0])
        self.assertNotIn("player's message", E.fight_over_prompt("x", "r", "End combat"))


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


class TalkingOutOfTurn(CampaignCase):
    def test_turn_line_between_npc_steps(self) -> None:
        self.new(blank="10x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "F2", GOBLIN, init=20)
        self.add("g2", "Gob2", "H2", GOBLIN, init=10)
        self.run_cmd("next")                                    # g1's turn
        self.run_cmd("wield", "g1", "shortbow", "--drop", "spear", "--out-of-turn")
        self.run_cmd("attack", "g1", "C", "--with", "shortbow")
        line = E.turn_line(self.state())
        self.assertIn("NOT the player's turn: Gob has just taken its turn; next up: Gob2", line)
        self.assertIn("don't say it's their turn", line)
        self.run_cmd("next")                                    # g2 now, not yet acted; Corin after it
        line = E.turn_line(self.state())
        self.assertIn("hasn't been played yet", line)
        self.assertIn("next up: Corin (the player's turn)", line)
        self.assertIn("NOT the player's turn", E.with_recap("Can I see his face?", "", [], self.state()))


class RunnerHearsThePlayer(CampaignCase):
    def test_player_words_reach_the_runner_frame(self) -> None:
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=5)
        runner = E.CombatRunner(lambda ev: None, self.slug)
        runner.heard(E.with_recap('"Get him!" I point at the fleeing guard', "", [], self.state()))
        runner.heard("[Combat step, sent by the interface]")                  # not the player's words
        frame = runner.frame("STEP", self.slug, self.state())
        self.assertIn('"Get him!" I point at the fleeing guard', frame)
        self.assertNotIn("Combat step, sent", frame.split("STEP")[0])
        self.assertFalse(runner.engine.alive())                              # nothing started


class Compaction(CampaignCase):
    def test_compacts_only_when_large_and_hides_it(self) -> None:
        shown: list[dict] = []
        eng = E.Engine(lambda ev: shown.append(ev))
        sent: list[str] = []
        eng.alive = lambda: True                                    # type: ignore[method-assign]
        labels: list[str] = []
        eng.send = lambda text, label="thinking": sent.append(text) or labels.append(label) or True   # type: ignore[method-assign]
        eng.context_tokens = 90_000
        self.assertFalse(eng.compact_if_large())
        eng.context_tokens = 180_000
        self.assertTrue(eng.compact_if_large())
        self.assertTrue(sent[0].startswith("/compact "))
        self.assertIn("tidying the DM's notes", labels[0])            # the player sees what's going on, not "thinking"
        self.assertEqual(eng.context_tokens, 0)
        self.assertIsNone(E.player_part(sent[0]))                    # never shown as the player's message
        self.assertEqual(E.exchange_kind(sent[0]), "command:compact")

    def test_sooner_after_a_fight(self) -> None:
        import web
        eng = E.Engine(lambda ev: None)
        eng.alive = lambda: True                                    # type: ignore[method-assign]
        eng.send = lambda text, label="thinking": True              # type: ignore[method-assign]
        eng.context_tokens = 110_000
        self.assertFalse(eng.compact_if_large())                    # below the general threshold
        self.assertTrue(eng.compact_if_large(after_fight=True))     # a scene break: compact now
        hub = web.Hub(self.slug)
        hub.engine = eng
        calls: list[bool] = []
        eng.compact_if_large = lambda after_fight=False: calls.append(after_fight) or False   # type: ignore[method-assign]
        hub.combat = {"active": True}
        hub.fight = lambda: None                                    # type: ignore[method-assign]  # the fight just ended
        hub.refresh_combat()
        hub._compact()
        hub._compact()
        self.assertEqual(calls, [True, False])                      # only the turn the fight ended in


class ClosingSession(CampaignCase):
    """/end-session: the interface asks the stars & wishes, the playing DM flushes its live log, and
    a fresh conversation runs the skill from the files and the transcript."""

    def hub(self) -> tuple[Any, list[str]]:
        import web
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        hub.engine.session_id = "old"
        hub.engine.alive = lambda: True                          # type: ignore[method-assign]
        sent: list[str] = []
        hub.engine.new_session = lambda: sent.append("NEW SESSION")   # type: ignore[method-assign]  # never a real process
        hub._exchange = lambda text: sent.append(text) or True   # type: ignore[method-assign]
        hub.history = [{"role": "player", "text": "/start-session " + self.slug}, {"role": "dm", "text": "Rain on the docks."},
                       {"role": "player", "text": "I follow the smuggler."}]
        return hub, sent

    def test_close_in_a_fresh_conversation(self) -> None:
        self.write("dm/session-log/session-01.md", "# Session 01\n")
        hub, sent = self.hub()
        with tempfile.TemporaryDirectory() as d:
            old, E.STATE = E.STATE, Path(d)
            try:
                hub.send("/end-session")
                self.assertTrue(hub.closing)
                self.assertIn("Stars & wishes", hub.history[-1]["text"])
                self.assertEqual(sent, [])                                  # no DM call for the question
                hub.send("cancel")
                self.assertFalse(hub.closing)
                hub.send("/end-session")
                hub.send("More rooftop chases")
                hub.worker.join(5)
                self.assertTrue(sent[0].startswith("[The session is ending"))   # the flush, in the old conversation
                self.assertEqual(sent[1], "NEW SESSION")
                self.assertIn("/end-session skill for campaign", sent[2])
                self.assertIn('"More rooftop chases"', sent[2])
                self.assertIn("Start at Step 2", sent[2])
                self.assertIn("No fight is in progress", sent[2])          # so the close doesn't go looking for one
                self.assertIn("The files the close needs, read for you", sent[2])
                self.assertIn("I follow the smuggler.", sent[2])             # the transcript is in the bundle
                self.assertIn("A fight is still in progress", E.close_prompt(self.slug, 1, "", None, fight=True))
                transcript = Path(d) / "transcripts" / f"{self.slug}-session-01.md"
                self.assertIn(str(transcript), sent[2])
                text = transcript.read_text()
                self.assertIn("**Player:** I follow the smuggler.", text)
                self.assertIn("**DM:** Rain on the docks.", text)
            finally:
                E.STATE = old
        self.assertEqual(E.exchange_kind(sent[2]), "command:end-session")
        self.assertIsNone(E.player_part(sent[0]))
        self.assertIsNone(E.player_part(sent[2]))

    def test_nothing_to_close(self) -> None:
        hub, sent = self.hub()
        hub.send("/end-session")
        self.assertFalse(hub.closing)
        self.assertIn("No session is in progress", hub.history[-1]["text"])
        self.assertEqual(sent, [])


class CombatRulesOnDemand(CampaignCase):
    """combat.md is read when a fight starts; until the DM has read it, messages in a fight remind it."""

    def test_reminder_until_read(self) -> None:
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "F2", GOBLIN, init=10)
        st = self.state()
        self.assertIn(E.COMBAT_RULES, E.with_recap("I roll 17", "", [], st, rules_unread=True))
        self.assertNotIn(E.COMBAT_RULES, E.with_recap("I roll 17", "", [], st))
        self.assertEqual(E.player_part(E.with_recap("I roll 17", "", [], st, rules_unread=True)), "I roll 17")
        self.assertTrue(E.reads_combat_rules("Read", {"file_path": str(E.REPO / E.COMBAT_RULES)}))
        self.assertTrue(E.reads_combat_rules("Bash", {"command": f"sed -n '1,80p' {E.COMBAT_RULES}"}))
        self.assertFalse(E.reads_combat_rules("Read", {"file_path": "library/general/table-rules/combat-prep.md"}))

    def test_compaction_forgets_it(self) -> None:
        eng = E.Engine(lambda ev: None)
        eng.alive = lambda: True                                    # type: ignore[method-assign]
        eng.send = lambda text, label="thinking": True              # type: ignore[method-assign]
        eng.combat_rules_read, eng.context_tokens = True, 200_000
        self.assertTrue(eng.compact_if_large())
        self.assertFalse(eng.combat_rules_read)


class PlayerTurns(CampaignCase):
    """In a fight, the player's turns go to the lean player-turn runner; everything else, and what it
    hands back, goes to the main DM."""

    def setUp(self) -> None:
        super().setUp()
        self.write("players/characters/corin.md", "# Corin\nSpells: daze, light.\n")
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", PC_PROFILE, "pc", 20, "--ref", f"campaigns/{self.slug}/players/characters/corin.md")
        self.add("g1", "Gob", "F2", GOBLIN, init=10)
        self.run_cmd("next")                                    # Corin's turn

    def hub(self, reply: str | None) -> tuple[Any, list[str], list[str]]:
        import web
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        hub.engine.combat_engaged = True
        to_dm: list[str] = []
        to_runner: list[str] = []
        hub._exchange = lambda text: to_dm.append(text) or True   # type: ignore[method-assign]

        class Fake:
            campaign = self.slug
            def play(self, text: str, st: dict, recent: list) -> tuple[bool, str | None]:
                to_runner.append(text)
                return True, reply
            def stop(self) -> None:
                pass
        hub._get_pc_runner = lambda camp, st: Fake()             # type: ignore[method-assign]
        return hub, to_dm, to_runner

    def test_routing(self) -> None:
        hub, to_dm, to_runner = self.hub("Hit: the goblin reels. You still have a move action.")
        hub._run_turn("I attack g1, 17 to hit, 6 damage")
        self.assertEqual((len(to_runner), to_dm), (1, []))    # resolved without the main DM
        self.assertIn("I attack g1", hub.runner.take_recap())  # and the main DM hears it later
        hub._run_turn("[Use the optional flanking rule from now on]")
        self.assertEqual(len(to_runner), 1)                   # brackets: the main DM
        self.assertEqual(len(to_dm), 1)

    def test_handed_back(self) -> None:
        hub, to_dm, to_runner = self.hub(None)
        hub._run_turn('"Drop your blade and I\'ll let you live," I tell the goblin.')
        self.assertEqual(len(to_runner), 1)
        self.assertEqual(len(to_dm), 1)
        self.assertIn("I'll let you live", to_dm[0])

    def test_not_the_players_turn(self) -> None:
        self.run_cmd("next")                                    # the goblin's turn
        hub, to_dm, to_runner = self.hub("ok")
        hub._run_turn("What does the goblin look like?")
        self.assertEqual((to_runner, len(to_dm)), ([], 1))

    def test_runner_hides_the_hand_back_and_starts_each_turn_fresh(self) -> None:
        shown: list[dict] = []
        st = self.state()
        r = E.PlayerTurnRunner(lambda ev: shown.append(ev), self.slug, st)
        self.assertIn("Spells: daze", r.engine.system_prompt or "")
        replies = [E.ESCALATE, "Hit, 6 damage. You still have a move action.", "You step back."]
        fresh: list[int] = []
        r.engine.alive = lambda: True                                 # type: ignore[method-assign]
        r.engine.new_session = lambda: fresh.append(1)                # type: ignore[method-assign]

        def send(prompt: str) -> bool:
            self.assertIn("The player says:", prompt)
            r.engine.emit(type="text_start")
            r.engine.emit(type="text", delta=replies.pop(0))
            return True
        r.engine.send = send                                          # type: ignore[method-assign]
        self.assertEqual(r.play("I tell him to surrender", st, []), (True, None))
        self.assertEqual(shown, [])                                   # the hand-back is never shown
        ok, text = r.play("I attack g1, 17, 6 damage", st, [])
        self.assertEqual(text, "Hit, 6 damage. You still have a move action.")
        self.assertTrue(any(ev.get("delta") == text for ev in shown))
        self.assertEqual(fresh, [])
        st2 = dict(st, round=2)
        r.play("I step back", st2, [])
        self.assertEqual(fresh, [1])                                  # a new turn: a fresh conversation
        self.assertEqual(E.exchange_kind(r.player_frame("x", st, [])), "player-turn")


class ReviewFixesEngine(CampaignCase):
    def test_no_hand_back_after_acting(self) -> None:
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.run_cmd("next")
        shown: list[dict] = []
        r = E.PlayerTurnRunner(lambda ev: shown.append(ev), self.slug, self.state())
        r.engine.alive = lambda: True                                 # type: ignore[method-assign]

        def send(prompt: str) -> bool:                                # acts, then hands back anyway
            r.engine.emit(type="text_start")
            with r.engine.lock:
                r.engine._held.append({"type": "_tool"})              # type: ignore[union-attr]
            r.engine.emit(type="text", delta="You slip further. " + E.ESCALATE)
            return True
        r.engine.send = send                                          # type: ignore[method-assign]
        ok, text = r.play("14", self.state(), [])
        self.assertEqual((ok, text), (True, "You slip further."))    # resolved here: the main DM never gets it
        self.assertFalse(any(E.ESCALATE in ev.get("delta", "") for ev in shown))

    def test_no_compaction_mid_fight(self) -> None:
        import web
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.run_cmd("next")
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        hub.engine.combat_engaged = True
        calls: list[bool] = []
        hub.engine.compact_if_large = lambda after_fight=False: calls.append(after_fight) or False   # type: ignore[method-assign]
        hub.engine.context_tokens = 130_000
        hub._compact()
        self.assertEqual(calls, [])                                   # waits for the fight's end
        hub.engine.context_tokens = 200_000
        hub._compact()
        self.assertEqual(calls, [False])                              # unless it's huge

    def test_history_hides_compaction(self) -> None:
        lines = [{"type": "user", "message": {"content": "/start-session x"}},
                 {"type": "user", "isCompactSummary": True, "message": {"content": "This session is being continued…"}},
                 {"type": "user", "message": {"content": "<command-name>/compact</command-name><command-args>Keep it</command-args>"}},
                 {"type": "user", "message": {"content": "I draw my blade"}}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.jsonl"
            p.write_text("\n".join(json.dumps(l) for l in lines))
            old = E.transcript_path
            E.transcript_path = lambda sid: p                          # type: ignore[assignment]
            try:
                h = E.load_history("s")
            finally:
                E.transcript_path = old                               # type: ignore[assignment]
        self.assertEqual([m["text"] for m in h], ["/start-session x", "I draw my blade"])


class DebugInCombat(CampaignCase):
    """Debug mode reaches the combat runners (tagged), shows what the interface sent them and what
    was held back, and the interface's own routing decisions."""

    def test_runner_lines(self) -> None:
        lines: list[str] = []
        r = E.PlayerTurnRunner(lambda ev: lines.append(ev.get("line", "")) if ev["type"] == "debug" else None,
                               self.slug, {"tokens": []})
        r.engine.debug = True
        r.engine.dbg("[tool] mcp__dm__combat_attack")
        self.assertEqual(lines[-1], "{player-turn runner} [tool] mcp__dm__combat_attack")
        r.engine.hold()
        r.engine.emit(type="text", delta="secret thinking")
        r.engine.release(publish=False)
        self.assertIn("[not shown] secret thinking", lines[-1])

    def test_sent_briefings_and_toggle(self) -> None:
        import web
        lines: list[str] = []
        eng = E.Engine(lambda ev: lines.append(ev.get("line", "")) if ev["type"] == "debug" else None, role="runner")
        eng.debug = True

        class Proc:
            def poll(self) -> None:
                return None

            class stdin:                                               # noqa: N801 - a stand-in
                @staticmethod
                def write(s: str) -> None:
                    raise BrokenPipeError

                @staticmethod
                def flush() -> None:
                    pass
        eng.proc = Proc()                                              # type: ignore[assignment]
        try:
            eng.send("[Combat step, sent by the interface] plans…")
        except BrokenPipeError:
            pass
        self.assertTrue(any(l.startswith("{runner} [→ sent] [Combat step") for l in lines), lines)
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        runner = hub._get_runner(self.slug)
        self.assertFalse(runner.engine.debug)
        hub.command(":debug")
        self.assertTrue(runner.engine.debug)                           # follows the toggle
        hub.dbg("message → the main DM")
        self.assertEqual(hub.history[-1], {"role": "debug", "text": "{interface} message → the main DM"})


class QueueDuringCompaction(CampaignCase):
    """While the DM's conversation is compacted after a reply, the chat stays open: messages typed
    meanwhile are queued and sent, in order, right after."""

    def test_message_waits_for_the_compaction(self) -> None:
        import web
        hub = web.Hub(self.slug)
        hub.engine = E.Engine(lambda ev: None)
        sent: list[str] = []
        hub._exchange = lambda text: sent.append(text) or True       # type: ignore[method-assign]
        busy: list[bool] = []
        hub.publish = lambda ev: busy.append(ev["busy"]) if ev["type"] == "busy" else None   # type: ignore[method-assign]
        during: list[tuple[int, str]] = []

        def compact(after_fight: bool = False) -> bool:
            if not during:                                             # the player types while it runs
                during.append(hub.send("Second message"))
                during.append(hub.send("Third message"))
            return True
        hub.engine.compact_if_large = compact                          # type: ignore[method-assign]
        self.assertEqual(hub.send("First message")[0], 202)
        hub.worker.join(5)
        self.assertEqual(during, [(202, "queued"), (202, "queued")])
        self.assertEqual(sent, ["First message", "Second message", "Third message"])
        self.assertEqual(busy[:2], [True, False])                      # the chat opened before the compaction
        self.assertFalse(hub.compacting)
        self.assertEqual(hub.queue, [])


class SessionStartBundle(CampaignCase):
    """The interface does /start-session's mechanical steps and hands the DM the files in one message."""

    def setUp(self) -> None:
        super().setUp()
        self.write("campaign.md", "# Test\n**System:** pf1e\n- **Status:** planning\n- **Sessions played:** 2\n")
        self.write("players/session-zero.md", "# Session zero\nLines: none.\n")
        self.write("players/party.md", "# Party\n")
        self.write("players/recaps/session-01.md", "old recap")
        self.write("players/recaps/session-02.md", "the latest recap")
        self.write("players/characters/corin.md", "# Corin\n```combat-profile\n{\"kind\": \"pc\"}\n```\n")
        self.write("dm/state.md", "# State\nThe party is at the inn.\n")
        self.write("dm/session-prep/session-03-prep.md", "# Prep 03\nStrong start: a knock at the door.\n")
        self.write("dm/world.md", "# World\n## Clocks\nsecret clock text\n## Triggers\n")

    def test_new_session(self) -> None:
        msg = E.session_start_bundle(self.slug)
        self.assertTrue(msg.startswith(f"[Session start, from the interface: campaign `{self.slug}`, session 03."))
        log = (self.dir / "dm/session-log/session-03.md").read_text()
        self.assertTrue(log.startswith("# Session 03"))
        self.assertIn("**Status:** active", (self.dir / "campaign.md").read_text())
        self.assertIn("reset the world's session count", msg)
        self.assertIn("ran combat_profile_check", msg)
        for text in ("the latest recap", "The party is at the inn.", "Strong start: a knock", "Behind the screen"):
            self.assertIn(text, msg)
        self.assertNotIn("old recap", msg)                              # only the latest recap
        self.assertIn("## Clocks", msg)
        self.assertNotIn("secret clock text", msg)                      # world.md: headings only
        self.assertEqual(E.exchange_kind(msg), "command:start-session")
        self.assertIsNone(E.player_part(msg))                           # never shown as the player's message

    def test_resume(self) -> None:
        self.write("dm/session-log/session-03.md", "# Session 03\n## Log\n- the party reached the bridge\n")
        msg = E.session_start_bundle(self.slug)
        self.assertIn("a RESUME of an interrupted session", msg)
        self.assertIn("the party reached the bridge", msg)
        self.assertNotIn("created the live log", msg)
        self.assertIn("**Status:** planning", (self.dir / "campaign.md").read_text())   # untouched on a resume


class StashTab(CampaignCase):
    def test_party_stash_doc(self) -> None:
        import web
        self.write("players/party.md", "# Party\n")
        doc = web.player_doc(self.slug, "stash")
        self.assertEqual(doc, {"title": "Party stash", "markdown": "*No inventory yet.*"})
        self.assertIsNotNone(web.player_doc(self.slug, "party"))

    def test_character_tab_shows_generated_gear(self) -> None:
        import json
        import web
        self.write("players/characters/corin.md", "# Corin\n## Gear\n<!-- gear:begin x -->\nold\n<!-- gear:end -->\n## Backstory\nborn\n")
        self.write("players/characters/mira.md", "# Mira\n## Backstory\nraised\n")
        self.write("dm/items/rope.json", json.dumps({"name": "Rope", "category": "gear", "price": 1, "weight": 10, "source": "t"}))
        self.write("players/inventory.json", json.dumps({"containers": {
            "corin": {"label": "Corin", "kind": "character", "sheet": "players/characters/corin.md", "coins": {"gp": 5},
                      "items": [{"item": "rope", "qty": 1}]},
            "mira": {"label": "Mira", "kind": "character", "sheet": "players/characters/mira.md", "coins": {}, "items": []}}}))
        doc = web.player_doc(self.slug, "character")["markdown"]
        self.assertNotIn("<!--", doc)
        self.assertNotIn("old", doc)
        self.assertIn("## Gear\n**Coins:** 5 gp", doc)
        self.assertIn("| Rope | 1 | 10 lb | 1 gp |", doc)
        self.assertLess(doc.index("## Gear\n**Coins:** no coins"), doc.index("raised"))   # added before the backstory


class CastList(CampaignCase):
    """The runners' who's-who: kind, worn armor (or explicitly none), what's in hand and what's stowed."""

    def test_party_and_enemies(self) -> None:
        import json
        self.write("players/characters/brenna.md", "# Brenna\n- **Race / Class / Level:** Dwarf / Monk / 1\n")
        self.write("players/characters/kovan.md", "# Kovan\n- **Race / Class / Level:** Half-Orc / Slayer / 1\n")
        self.write("dm/npcs/thug.md", "# Thug (CR 1/2)\n**Gear** leather armor, club\n```combat-profile\n{}\n```\n")
        for slug, d in (("breastplate", {"name": "Breastplate", "category": "armor", "price": 200, "weight": 30, "source": "t"}),
                        ("kukri", {"name": "Kukri", "category": "weapon", "price": 8, "weight": 2, "source": "t"})):
            self.write(f"dm/items/{slug}.json", json.dumps(d))
        self.write("players/inventory.json", json.dumps({"containers": {
            "brenna": {"label": "Brenna", "kind": "character", "sheet": "players/characters/brenna.md", "coins": {}, "items": []},
            "kovan": {"label": "Kovan", "kind": "character", "sheet": "players/characters/kovan.md", "coins": {},
                      "items": [{"item": "breastplate", "qty": 1, "equipped": True}, {"item": "kukri", "qty": 1}]}}}))
        bow = {"composite longbow": {"bonus": 5, "damage": "1d8+2", "type": "ranged", "range": 110},
               "kukri": {"bonus": 5, "damage": "1d4+2", "type": "melee", "ability": "dex"}}
        self.new(blank="8x6")
        rel = f"campaigns/{self.slug}/"
        self.add("B", "Brenna", "B2", dict(GOBLIN, attacks={"unarmed strike": {"bonus": 3, "damage": "1d6", "type": "melee"}}), "ally", 10,
                 "--ref", rel + "players/characters/brenna.md")
        self.add("K", "Kovan", "C2", dict(GOBLIN, attacks=bow, wielding=["composite longbow"]), "ally", 9,
                 "--ref", rel + "players/characters/kovan.md")
        self.add("t1", "Thug", "F2", GOBLIN, "enemy", 5, "--ref", rel + "dm/npcs/thug.md")
        text = E.cast_list(self.state())
        self.assertIn("- Brenna (B, ally): Dwarf Monk · wears no armor · in hand: nothing", text)
        self.assertIn("Kovan (K, ally): Half-Orc Slayer · wears Breastplate · in hand: nothing (unarmed or spells) · carries (stowed): Kukri",
                      text)   # nothing equipped in the inventory: empty hands, whatever the profile's default
        self.assertIn("Thug (t1, enemy): Thug · gear its stat block lists", text)
        self.assertIn("leather armor, club", text)
        self.assertIn(text, E._step_context(self.state(), next(t for t in self.state()["tokens"] if t["token"] == "t1")))


class SessionClosed(CampaignCase):
    def test_sessions_played_is_incremented_once(self) -> None:
        self.write("campaign.md", "# Test\n**System:** pf1e\n- **Sessions played:** 4\n")
        self.assertTrue(E.mark_session_closed(self.slug, 5))
        self.assertIn("**Sessions played:** 5", (self.dir / "campaign.md").read_text())
        self.assertFalse(E.mark_session_closed(self.slug, 5))                # the DM already did it, or a second call
