"""combat.py: adding, turn order and the actor lock, attacks, movement, spells, maneuvers,
action economy, encounters and tactical options."""
from __future__ import annotations

import json
import os

from tests.support import CASTER, GOBLIN, PC_PROFILE, CampaignCase, sheet


class Adding(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new()

    def test_pc_needs_a_complete_profile(self) -> None:
        self.assertIn("no combat profile", self.fail_cmd("add", "C", "Corin", "--pos", "A1", "--side", "pc", "--init", "5", "--hp", "9"))
        partial = {k: PC_PROFILE[k] for k in ("kind", "init", "max_hp", "ac", "touch", "ff")}
        err = self.fail_cmd("add", "C", "Corin", "--pos", "A1", "--side", "pc", "--init", "5", "--profile", json.dumps(partial))
        self.assertIn("missing cmd", err)
        self.assertIn("ASK THE PLAYER", err)

    def test_pc_hp_from_sheet(self) -> None:
        self.write("players/characters/corin.md", sheet("Corin", hp="7 / 30"))
        self.run_cmd("add", "C", "Corin", "--pos", "A1", "--side", "pc", "--init", "5",
                     "--ref", f"campaigns/{self.slug}/players/characters/corin.md")
        self.assertEqual((self.tok("C")["hp"], self.tok("C")["max_hp"]), (7, 30))

    def test_pc_profile_on_an_enemy_is_refused(self) -> None:
        self.assertIn("PC profile", self.fail_cmd("add", "g1", "G", "--pos", "A1", "--init", "5", "--profile", json.dumps(PC_PROFILE)))

    def test_occupied_square(self) -> None:
        self.add("g1", "G", "A1", GOBLIN)
        self.assertIn("occupied", self.fail_cmd("add", "g2", "G", "--pos", "A1", "--init", "5", "--profile", json.dumps(GOBLIN)))


class TurnOrder(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new()
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=15)
        self.add("g1", "Gob", "C2", GOBLIN, init=20)
        self.add("g2", "Gob2", "H7", GOBLIN, init=5)

    def test_order_and_wrap(self) -> None:
        self.assertIn("g1", self.run_cmd("next"))
        self.assertIn("C", self.run_cmd("next"))
        self.run_cmd("next")
        out = self.run_cmd("next")
        self.assertIn("Round 2", out)

    def test_actor_lock(self) -> None:
        self.run_cmd("next")
        self.assertIn("it's g1 (Gob)'s turn", self.fail_cmd("attack", "g2", "C", "--with", "spear"))
        self.assertIn("tell the player that Gob acts first", self.fail_cmd("move", "C", "B3"))
        self.run_cmd("move", "C", "B3", "--out-of-turn")    # forced movement is fine

    def test_next_refused_in_play_mode(self) -> None:
        os.environ["CLAUDE_DM_MODE"] = "play"
        try:
            self.assertIn("you ARE in the player interface", self.fail_cmd("next"))
            err = self.fail_cmd("attack", "g1", "C", "--with", "spear")      # before the first turn
            self.assertIn("starts the turns right after your reply", err)
        finally:
            del os.environ["CLAUDE_DM_MODE"]

    def test_pc_acting_early_gets_told_who_is_first(self) -> None:
        self.run_cmd("next")                                                  # g1 (init 20) is up
        err = self.fail_cmd("attack", "C", "g1", "--total", "15", "--damage", "3")
        self.assertIn("tell the player that Gob acts first", err)

    def test_actor_dropping_on_its_turn_keeps_the_order(self) -> None:
        self.run_cmd("next")                     # g1
        self.run_cmd("hp", "g1", "-20")          # drops on its own turn
        self.assertIn("C (Corin)", self.run_cmd("next"))   # continues after g1, not from the top


class Attacks(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new()
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "C2", GOBLIN, init=10)
        self.add("g2", "Gob2", "D2", GOBLIN, init=5)
        self.run_cmd("next")

    def test_pc_total_against_flat_footed_ac(self) -> None:
        out = self.run_cmd("attack", "C", "g1", "--total", "14", "--damage", "5")
        self.assertIn("vs AC 14 (flat-footed)", out)                # hasn't acted yet
        self.assertEqual(self.tok("g1")["hp"], 7)

    def test_miss_leaves_hp(self) -> None:
        self.run_cmd("attack", "C", "g1", "--total", "5", "--damage", "5")
        self.assertEqual(self.tok("g1")["hp"], 12)

    def test_flanking(self) -> None:
        self.run_cmd("move", "g2", "A2", "--out-of-turn")
        self.run_cmd("next")
        out = self.run_cmd("attack", "g1", "C", "--with", "spear")
        self.assertIn("+2 flanking", out)

    def test_grappled_attacker_and_defender(self) -> None:
        self.run_cmd("cond", "g1", "add", "grappled")
        out = self.run_cmd("attack", "C", "g1", "--total", "30", "--damage", "1")
        self.assertIn("target grappled", out)

    def test_melee_needs_reach_and_charge_needs_its_move(self) -> None:
        self.run_cmd("next")                                   # g1 (C2, next to Corin at B2)
        self.run_cmd("next")                                   # g2 (D2): 10 ft away
        self.assertIn("out of g2's melee reach", self.fail_cmd("attack", "g2", "C", "--with", "spear"))
        self.assertIn("--as charge", self.fail_cmd("attack", "g2", "C", "--with", "spear", "--charge"))
        self.run_cmd("attack", "g2", "C", "--with", "shortbow")          # ranged is fine

    def test_minimum_damage_is_one_nonlethal(self) -> None:
        self.run_cmd("next")   # g1's turn
        self.run_cmd("attack", "g1", "C", "--roll", "1d20+30", "--dmg", "1d2-5", "--name", "claw")
        c = self.tok("C")
        self.assertEqual((c["hp"], c.get("nonlethal", 0)), (30, 1))   # 1d2-5 is always below 1

    def test_area_needs_dc(self) -> None:
        self.assertIn("--dc", self.fail_cmd("area", "burst", "10", "--at", "C2", "--save", "ref", "--dmg", "1d6"))


class Movement(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new()
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "C2", GOBLIN, init=10)
        self.run_cmd("next")

    def test_leaving_threat_provokes_npc_aoo(self) -> None:
        self.run_cmd("next")   # g1 hasn't acted… make it act first so it can take AoOs
        self.run_cmd("next")
        out = self.run_cmd("move", "C", "B5")
        self.assertIn("Attack of opportunity", out)

    def test_flat_footed_npc_takes_no_aoo(self) -> None:
        out = self.run_cmd("move", "C", "B5")
        self.assertIn("flat-footed", out)

    def test_five_foot_step_rules(self) -> None:
        self.run_cmd("move", "C", "B3", "--step")
        self.assertIn("5-foot step", self.fail_cmd("move", "C", "B5"))

    def test_down_and_grappled_cant_move(self) -> None:
        self.run_cmd("cond", "C", "add", "grappled")
        self.assertIn("can't move", self.fail_cmd("move", "C", "B4"))


class Spells(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new()
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=5)
        self.add("s1", "Caster", "H6", CASTER, init=20)
        self.run_cmd("next")

    def test_cast_spends_slot_and_resolves(self) -> None:
        out = self.run_cmd("cast", "s1", "magic missile", "--target", "C", "--dmg", "1d4+1")
        self.assertIn("slots left: 1/2", out)
        self.assertLess(self.tok("C")["hp"], 30)

    def test_area_refuses_casters_own_spell(self) -> None:
        self.assertIn("cast", self.fail_cmd("area", "burst", "10", "--at", "B2", "--from", "s1", "--name", "magic missile",
                                            "--save", "ref", "--dc", "12", "--dmg", "1d6"))

    def test_darkness_spell_creates_light_effect(self) -> None:
        self.run_cmd("cast", "s1", "darkness", "--light-at", "B2")
        self.assertTrue(any(s["kind"] == "darkness" for s in self.state()["light"]["sources"]))


class Maneuvers(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new()
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "C2", dict(GOBLIN, feats=["Improved Grapple"]), init=10)
        self.run_cmd("next")

    def test_trip(self) -> None:
        self.run_cmd("maneuver", "C", "g1", "trip", "--total", "30")
        self.assertTrue(any(x["name"] == "prone" for x in self.tok("g1")["conditions"]))

    def test_grapple_lifecycle(self) -> None:
        self.run_cmd("next")
        self.run_cmd("maneuver", "g1", "C", "grapple", "--cmb", "40")
        self.assertEqual(len(self.state()["grapples"]), 1)
        self.run_cmd("next")
        self.run_cmd("maneuver", "C", "g1", "escape", "--total", "1")      # fails
        self.run_cmd("next")
        self.run_cmd("maneuver", "g1", "C", "grapple", "--cmb", "40", "--option", "pin")
        self.assertTrue(any(x["name"] == "pinned" for x in self.tok("C")["conditions"]))
        self.run_cmd("next")
        self.run_cmd("next")     # g1's turn again: it doesn't maintain…
        out = self.run_cmd("next")
        self.assertIn("grapple ends", out)
        self.assertEqual(self.state()["grapples"], [])

    def test_out_of_reach_and_size(self) -> None:
        self.run_cmd("move", "g1", "H7", "--out-of-turn")
        self.assertIn("beyond", self.fail_cmd("maneuver", "C", "g1", "trip", "--total", "30"))


class ActionEconomy(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(blank="14x6")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "C2", CASTER, init=10)
        self.run_cmd("next")

    def test_second_attack_becomes_full_attack(self) -> None:
        self.run_cmd("attack", "C", "g1", "--total", "1", "--damage", "1")
        self.assertIn("swift, 5-foot step", self.run_cmd("attack", "C", "g1", "--total", "1", "--damage", "1"))
        self.assertIn("full-round", self.fail_cmd("move", "C", "B5"))
        self.run_cmd("move", "C", "B3", "--step")

    def test_movement_cant_split_around_a_standard(self) -> None:
        self.run_cmd("next")
        self.run_cmd("move", "g1", "G2")
        self.run_cmd("cast", "g1", "magic missile", "--target", "C", "--dmg", "1d4+1", "--no-provoke")
        self.assertIn("both used", self.fail_cmd("move", "g1", "H2"))

    def test_charge_is_one_full_round_action(self) -> None:
        self.run_cmd("move", "g1", "M5", "--out-of-turn")
        self.run_cmd("next")
        self.run_cmd("move", "g1", "C3", "--as", "charge")
        out = self.run_cmd("attack", "g1", "C", "--with", "spear", "--charge")
        self.assertIn("+2 charge", out)
        self.assertIn("actions left for g1: swift", out)

    def test_immediate_takes_next_swift(self) -> None:
        self.run_cmd("next")
        self.run_cmd("act", "C", "immediate", "feather fall")
        self.run_cmd("next")
        self.assertIn("already used", self.fail_cmd("act", "C", "swift", "boots"))

    def test_stand_up_and_surprise(self) -> None:
        self.run_cmd("cond", "C", "add", "prone")
        self.run_cmd("act", "C", "move", "stand up")
        self.assertFalse(any(x["name"] == "prone" for x in self.tok("C")["conditions"]))
        self.run_cmd("surprise", "on")
        self.assertIn("only one action", self.fail_cmd("attack", "C", "g1", "--total", "1", "--damage", "1"))


ENC = {"title": "Ford", "map": "dm/combat/maps/ford.txt", "pc_start": ["B3"], "surprise": True,
       "combatants": [{"token": "k", "count": 2, "name": "Kobold", "ref": "library/pf1e/bestiary/kobold.md",
                       "pos": ["H2", "H4"], "hidden": True}],
       "lights": [{"kind": "torch", "on": "k1"}], "tactics": "Shoot from the reeds."}


class Encounters(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.write("dm/combat/maps/ford.txt", "ambient: dim\n##########\n#........#\n#..~~~...#\n#........#\n##########\n")
        self.write("players/characters/corin.md", sheet("Corin"))
        self.write("dm/combat/encounters/ford.md", f"# Ford\n```encounter\n{json.dumps(ENC)}\n```\n")

    def test_check_and_setup(self) -> None:
        self.assertIn("OK", self.run_cmd("encounter", "check"))
        self.assertIn("initiative roll", self.fail_cmd("setup", "ford"))
        out = self.run_cmd("setup", "ford", "--init", "C=12")
        self.assertIn("Shoot from the reeds", out)
        st = self.state()
        self.assertEqual(sorted(t["token"] for t in st["tokens"]), ["C", "k1", "k2"])
        self.assertTrue(st["surprise"])
        self.assertIn("active", self.fail_cmd("setup", "ford", "--init", "C=12"))

    def test_broken_encounter_creates_nothing(self) -> None:
        bad = dict(ENC, combatants=[dict(ENC["combatants"][0], pos=["H2", "A1"])])   # A1 is a wall
        self.write("dm/combat/encounters/bad.md", f"```encounter\n{json.dumps(bad)}\n```\n")
        self.assertIn("wall", self.fail_cmd("setup", "bad", "--init", "C=12"))
        self.assertFalse((self.dir / "dm/combat/current.json").exists())


class Options(CampaignCase):
    def test_flanking_square_and_area(self) -> None:
        self.new(blank="12x7")
        self.add("C", "Corin", "C3", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "J5", GOBLIN, init=20)
        self.add("g2", "Gob2", "B2", GOBLIN, init=15)
        self.run_cmd("next")
        out = self.run_cmd("options", "g1", "--area", "burst 10", "--range", "100")
        self.assertIn("from D4", out)          # opposite g2: flanking
        self.assertIn("[flanking]", out)
        self.assertIn("charge:", out)
        self.assertIn('--area "burst 10"', out)
        self.assertEqual((self.tok("g1")["x"], self.tok("g1")["y"]), (9, 4))   # options never move anything


class MovementLine(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(map_text="#########\n#.......#\n#...#...#\n#...#...#\n#.......#\n#########\n")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "G3", GOBLIN, init=20)
        self.add("h1", "Lurker", "G5", GOBLIN, "enemy", 15, "--hidden")
        self.run_cmd("next")                                   # g1

    def line(self) -> dict | None:
        import combat
        return combat.movement_line(self.state())

    def test_route_around_the_wall_and_handoff(self) -> None:
        self.run_cmd("move", "g1", "C3")
        mv = self.line()
        assert mv is not None
        self.assertEqual(mv["token"], "g1")
        self.assertEqual(mv["path"][0], [6, 2])
        self.assertEqual(mv["path"][-1], [2, 2])
        self.assertTrue(all(sq != [4, 2] and sq != [4, 3] for sq in mv["path"]))   # never through the wall
        self.run_cmd("next")                                   # h1 (hidden) moves: never shown
        self.run_cmd("move", "h1", "F5")
        self.assertEqual(self.line()["token"], "g1")
        self.run_cmd("next")                                   # Corin: g1's line stays until he moves
        self.assertEqual(self.line()["token"], "g1")
        self.run_cmd("move", "C", "B3", "--step")
        self.assertEqual(self.line()["path"], [[1, 1], [1, 2]])

    def test_actor_that_doesnt_move_clears_it(self) -> None:
        self.run_cmd("move", "g1", "F3")
        self.run_cmd("next")
        self.run_cmd("next")                                   # Corin, then he ends without moving
        self.run_cmd("next")                                   # g1 again (new round)
        self.assertIsNone(self.line())                         # the last actor (Corin) didn't move


class AoOPath(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(blank="10x3")
        self.add("C", "Corin", "A2", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "E1", GOBLIN, init=20)
        self.run_cmd("next")                                              # g1 acts: no longer flat-footed
        self.run_cmd("next")                                              # Corin

    def test_passing_by_provokes(self) -> None:
        out = self.run_cmd("move", "C", "H2")                             # starts unthreatened, passes E1's reach
        self.assertIn("Attack of opportunity", out)
        self.assertEqual(self.tok("g1")["aoo_used"], 1)

    def test_one_opportunity_per_opponent_per_round(self) -> None:
        out = self.run_cmd("move", "C", "C2", "--override")               # up to its reach: nothing left yet
        self.assertNotIn("Attack of opportunity", out)
        out = self.run_cmd("move", "C", "H2", "--override")               # through D2/E2/F2: its one chance
        self.assertIn("Attack of opportunity", out)
        self.run_cmd("move", "C", "E3", "--override", "--out-of-turn")
        out = self.run_cmd("move", "C", "A3", "--override")               # past it again, same round
        self.assertNotIn("Attack of opportunity", out)

    def test_dropped_mid_move_falls_there(self) -> None:
        self.run_cmd("hp", "C", "-29")                                    # 1 HP left
        import combat
        combat.RNG = __import__("random").Random(4)
        out = self.run_cmd("move", "C", "H2")
        c = self.tok("C")
        if c["hp"] <= 0:                                                  # the AoO hit: it stopped next to g1
            self.assertIn("dropped by an attack of opportunity", out)
            self.assertLess(c["x"], 7)
        else:
            self.assertEqual((c["x"], c["y"]), (7, 1))


class Undo(CampaignCase):
    """The player corrects a roll: undo the last PC command and enter it again; NPC rolls stand."""

    def setUp(self) -> None:
        super().setUp()
        self.new()
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "C2", GOBLIN, init=10)
        self.run_cmd("next")                                              # Corin

    def test_corrected_roll(self) -> None:
        self.run_cmd("attack", "C", "g1", "--total", "13", "--damage", "5")     # 13 vs AC 14: miss
        self.assertEqual(self.tok("g1")["hp"], 12)
        self.run_cmd("undo")                                              # "I forgot +2 flanking"
        out = self.run_cmd("attack", "C", "g1", "--total", "15", "--damage", "5")
        self.assertEqual(self.tok("g1")["hp"], 7)
        self.assertIn("actions left for C: move, swift", out)            # still one attack, not a full attack
        self.assertTrue(any("correction" in e["text"] for e in self.state()["events"]))

    def test_npc_rolls_stand_and_no_undo_past_the_turn(self) -> None:
        self.run_cmd("attack", "C", "g1", "--total", "13", "--damage", "5")
        self.run_cmd("next")                                              # the turn moved on
        self.assertIn("nothing to undo", self.fail_cmd("undo"))
        self.run_cmd("attack", "g1", "C", "--with", "spear")
        self.assertIn("NPC rolls stand", self.fail_cmd("undo"))


class Healing(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new()
        self.add("s1", "Healer", "B2", CASTER, side="ally", init=20)
        self.add("C", "Corin", "C2", PC_PROFILE, side="pc", init=5)
        self.run_cmd("hp", "C", "-10")
        self.run_cmd("next")

    def test_cast_heals_the_target(self) -> None:
        out = self.run_cmd("cast", "s1", "magic missile", "--target", "C", "--heal", "1d8+3", "--no-provoke")
        self.assertIn("heals", out)
        self.assertGreater(self.tok("C")["hp"], 20)
        self.assertLessEqual(self.tok("C")["hp"], 30)                       # never above max

    def test_a_targeted_spell_without_effect_says_so(self) -> None:
        out = self.run_cmd("cast", "s1", "magic missile", "--target", "C", "--no-provoke")
        self.assertIn("no effect was applied", out)


class SpellConditions(CampaignCase):
    """A spell's condition lands on failed saves (or without a save); a PC's waits for their roll."""

    def setUp(self) -> None:
        super().setUp()
        self.new()
        caster = dict(CASTER, spellcasting=[dict(CASTER["spellcasting"][0], dc_base=30)])   # everyone fails
        self.add("s1", "Witch", "F5", caster, init=20)
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=5)
        self.add("g1", "Gob", "C4", GOBLIN, side="ally", init=3)
        self.add("g2", "Gob2", "D4", GOBLIN, side="ally", init=2)
        self.run_cmd("next")

    def conds(self, tok: str) -> list[str]:
        return [x["name"] for x in self.tok(tok)["conditions"]]

    def test_npc_target_fails_and_gets_the_condition(self) -> None:
        out = self.run_cmd("cast", "s1", "magic missile", "--target", "g1", "--save", "will", "--cond", "asleep",
                           "--cond-rounds", "3", "--no-provoke")
        self.assertIn("asleep", self.conds("g1"))
        self.assertNotIn("isn't a known condition", out)

    def test_pc_condition_waits_for_the_save(self) -> None:
        self.run_cmd("cast", "s1", "magic missile", "--target", "C", "--save", "will", "--cond", "shaken",
                     "--cond-rounds", "2", "--no-provoke")
        self.assertEqual(self.conds("C"), [])                                # pending
        self.run_cmd("save", "C", "--total", "5")                            # fails
        self.assertIn("shaken", self.conds("C"))

    def test_area_and_no_save_and_unknown_name(self) -> None:
        self.run_cmd("cast", "s1", "magic missile", "--area", "burst 10", "--at", "D4", "--save", "will",
                     "--cond", "stunned", "--cond-rounds", "1", "--no-provoke")
        self.assertIn("stunned", self.conds("g1"))
        self.assertIn("stunned", self.conds("g2"))
        for _ in range(4):
            self.run_cmd("next")                                             # round 2: the witch again
        out = self.run_cmd("cast", "s1", "darkness", "--target", "g1", "--cond", "befuddled", "--no-provoke")
        self.assertIn("befuddled", self.conds("g1"))                         # no save: it just applies
        self.assertIn("isn't a known condition", out)


ROGUE = dict(GOBLIN, sneak_attack="2d6", attacks={"dagger": {"bonus": 40, "damage": "1d4", "type": "melee"},
                                                   "sling": {"bonus": 40, "damage": "1d4", "type": "ranged", "range": 50}})


class SneakAttack(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(blank="12x6")
        self.add("r1", "Rogue", "C2", ROGUE, init=20)
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=15)
        self.add("g1", "Gob", "J5", GOBLIN, init=10)
        self.run_cmd("next")                                              # r1: Corin hasn't acted yet

    def test_flat_footed_target(self) -> None:
        self.assertIn("sneak attack 2d6", self.run_cmd("attack", "r1", "C", "--with", "dagger"))

    def test_rules_that_stop_it(self) -> None:
        for _ in range(3):
            self.run_cmd("next")                                          # round 2: Corin has acted
        out = self.run_cmd("attack", "r1", "C", "--with", "dagger")
        self.assertIn("no sneak attack: the target is neither flanked nor denied its Dex", out)

    def test_flanking_gives_it(self) -> None:
        for _ in range(3):
            self.run_cmd("next")
        self.run_cmd("move", "g1", "A2", "--out-of-turn")                 # opposite r1 across Corin
        self.assertIn("sneak attack 2d6", self.run_cmd("attack", "r1", "C", "--with", "dagger"))

    def test_ranged_beyond_30_ft(self) -> None:
        self.run_cmd("move", "r1", "J2", "--out-of-turn")
        out = self.run_cmd("attack", "r1", "C", "--with", "sling")
        self.assertIn("more than 30 ft away", out)


BARD = dict(GOBLIN, abilities={
    "inspire courage": {"action": "standard", "maintain": "free", "uses": 3, "kind": "buff",
                        "allies": {"atk": 1, "dmg": 1}, "buff": "inspired", "buff_rounds": 1},
    "channel": {"action": "standard", "uses": 2, "kind": "heal", "target": "area", "area": "burst 30", "center": "self",
                "heal": "1d6", "who": "allies"}},
    spellcasting=[dict(CASTER["spellcasting"][0], effects={
        "magic missile": {"target": "one", "range": 100, "dmg": "1d4+1"},
        "darkness": {"target": "area", "area": "burst 10", "center": "point", "save": "will", "cond": "shaken", "cond_rounds": 2}})])


class Abilities(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(blank="12x6")
        self.add("b1", "Bard", "C3", BARD, side="ally", init=20)
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=15)
        self.add("g1", "Gob", "I3", GOBLIN, init=10)
        self.run_cmd("next")

    def test_inspire_courage_buffs_and_is_maintained(self) -> None:
        out = self.run_cmd("ability", "b1", "inspire")
        self.assertIn("C", out.split("on ")[1])
        self.assertTrue(any(x["name"] == "inspired" for x in self.tok("C")["conditions"]))
        self.assertIn("actions left for b1: move", out)                   # it cost the standard action
        for _ in range(3):
            self.run_cmd("next")                                          # round 2: the bard again
        out = self.run_cmd("ability", "b1", "inspire")                    # maintained: a free action
        self.assertIn("standard", out.split("actions left for b1:")[1])

    def test_channel_heals_allies_in_the_burst(self) -> None:
        self.run_cmd("hp", "C", "-10")
        self.run_cmd("ability", "b1", "channel")
        self.assertGreater(self.tok("C")["hp"], 20)
        self.assertEqual(self.tok("g1")["hp"], 12)                        # the enemy is out of it anyway

    def test_spell_effect_comes_from_the_profile(self) -> None:
        out = self.run_cmd("cast", "b1", "magic missile", "--target", "g1", "--no-provoke")
        self.assertIn("damage 1d4+1", out)
        self.assertIn("--at", self.fail_cmd("cast", "b1", "darkness", "--no-provoke", "--override"))   # a burst needs a point


SCALECASTER = dict(GOBLIN, spellcasting=[dict(CASTER["spellcasting"][0], spells={"1": ["burning hands"]}, slots={"1": 1},
                                              effects={"burning hands": {"target": "area", "area": "cone 15", "save": "ref",
                                                                         "half": True, "dmg": "3d4"}})])


class TurnPlans(CampaignCase):
    def plans(self, tok: str) -> list[str]:
        out = self.run_cmd("options", tok)
        lines = out.split("Turn plans", 1)[1].split("Details:", 1)[0].splitlines()[1:]
        return [ln.strip() for ln in lines if ln.strip()]

    def test_area_spell_on_two_beats_a_spear(self) -> None:
        self.new(blank="12x8")
        self.add("s1", "Scale", "C6", SCALECASTER, init=20)
        self.add("C", "Corin", "G4", PC_PROFILE, side="pc", init=15)
        self.add("M", "Mir", "H5", PC_PROFILE, side="pc", init=14)
        self.run_cmd("next")
        plans = self.plans("s1")
        self.assertIn("cast burning hands --toward", plans[0])
        self.assertIn("hits C, M", plans[0])

    def test_spent_spell_is_not_offered(self) -> None:
        self.new(blank="12x8")
        self.add("s1", "Scale", "C6", SCALECASTER, init=20)
        self.add("C", "Corin", "D6", PC_PROFILE, side="pc", init=15)
        self.run_cmd("next")
        self.run_cmd("cast", "s1", "burning hands", "--toward", "D6")
        self.assertFalse(any("burning hands" in p for p in self.plans("s1")))

    def test_sneak_attack_and_buff_show(self) -> None:
        self.new(blank="12x8")
        self.add("b1", "Bard", "B2", BARD, init=20)
        self.add("r1", "Rogue", "F4", dict(ROGUE, attacks={"dagger": {"bonus": 5, "damage": "1d4", "type": "melee"}}), init=18)
        self.add("C", "Corin", "G4", PC_PROFILE, side="pc", init=15)
        self.run_cmd("next")
        self.assertTrue(any("inspire courage" in p and "support" in p for p in self.plans("b1")))
        self.run_cmd("next")
        self.assertIn("sneak", self.plans("r1")[0])              # Corin hasn't acted: flat-footed


RAYCASTER = dict(GOBLIN, spellcasting=[dict(CASTER["spellcasting"][0], spells={"0": ["ray of frost"]}, slots={"0": 99},
                                            effects={"ray of frost": {"target": "one", "range": 25, "touch": True,
                                                                      "attack": 4, "dmg": "1d3"}})])


class TouchEffects(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(blank="10x6")
        self.add("s1", "Ray", "B2", RAYCASTER, init=20)
        self.add("C", "Corin", "E2", PC_PROFILE, side="pc", init=10)
        self.run_cmd("next")

    def test_touch_attack_is_rolled_against_touch_ac(self) -> None:
        out = self.run_cmd("cast", "s1", "ray of frost", "--target", "C")
        self.assertIn("ranged touch attack", out)
        self.assertIn("vs touch AC 12", out)                 # flat-footed: Corin hasn't acted
        hp = self.tok("C")["hp"]
        self.assertEqual(hp < 30, ": hit" in out)            # damage only on a hit

    def test_missing_attack_bonus_is_refused(self) -> None:
        prof = json.loads(json.dumps(RAYCASTER))
        del prof["spellcasting"][0]["effects"]["ray of frost"]["attack"]
        self.add("s2", "Ray2", "B4", prof, init=5)
        self.assertIn("touch attack", self.fail_cmd("cast", "s2", "ray of frost", "--target", "C", "--out-of-turn"))

    def test_plans_show_the_touch_roll(self) -> None:
        self.assertTrue(any("ray of frost on C (touch, hits on" in ln for ln in self.run_cmd("options", "s1").splitlines()))


class Movement(CampaignCase):
    def test_diagonal_step_past_a_creature(self) -> None:
        self.new(map_text="######\n#....#\n#....#\n#....#\n######\n")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "C2", GOBLIN, init=10)      # beside Corin: its corner is on the diagonal
        self.run_cmd("next")
        self.assertIn("5-foot step", self.run_cmd("move", "C", "C3", "--step"))   # past g1's corner (CRB p. 192)

    def test_no_diagonal_past_a_wall_corner(self) -> None:
        self.new(map_text="######\n#.#..#\n#....#\n#....#\n######\n")   # C2 is wall
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.run_cmd("next")
        self.assertIn("exactly one square", self.fail_cmd("move", "C", "C3", "--step"))   # past C2's corner



class PlayerDamage(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(blank="8x6")
        self.add("C", "Corin", "B2", dict(PC_PROFILE, ammo={"shortbow": 2}), side="pc", init=20)
        self.add("g1", "Gob", "C2", GOBLIN, init=10)
        self.run_cmd("next")

    def test_hit_waits_for_the_players_damage(self) -> None:
        out = self.run_cmd("attack", "C", "g1", "--total", "25", "--name", "rapier")
        self.assertIn("Ask the player for the damage", out)
        self.assertEqual(self.tok("g1")["hp"], 12)
        self.assertIn("roll damage", self.state()["awaiting"])
        self.run_cmd("damage", "C", "5")
        self.assertEqual(self.tok("g1")["hp"], 7)
        self.assertNotIn("awaiting", self.state())
        self.fail_cmd("damage", "C", "5")                     # nothing pending any more

    def test_pc_ammo_is_counted(self) -> None:
        out = self.run_cmd("attack", "C", "g1", "--total", "1", "--name", "shortbow", "--ranged", "--override")
        self.assertIn("shortbow: 1/2 left", out)
        self.run_cmd("attack", "C", "g1", "--total", "1", "--name", "shortbow", "--ranged", "--override")
        self.assertIn("no shortbow ammunition", self.fail_cmd("attack", "C", "g1", "--total", "1", "--name", "shortbow",
                                                              "--ranged", "--out-of-turn"))

    def test_npc_thrown_weapon_runs_out(self) -> None:
        thrower = dict(GOBLIN, attacks={"javelin": {"bonus": 3, "damage": "1d6", "type": "ranged", "thrown": True,
                                                    "range": 30, "ammo": 1}})
        self.add("j1", "Thrower", "G5", thrower, init=5)
        self.run_cmd("attack", "j1", "C", "--with", "javelin", "--out-of-turn")
        self.assertIn("picked up", self.fail_cmd("attack", "j1", "C", "--with", "javelin", "--out-of-turn"))

    def test_total_defense_is_a_standard_action(self) -> None:
        out = self.run_cmd("act", "C", "full", "total defense")
        self.assertIn("charged as standard", out)
        self.assertIn("move", out.splitlines()[-1])            # the move action is still there
        import combat_rules as R
        self.assertTrue(R.has(self.tok("C"), "total defense"))
        self.assertIn("player rolls any dice", out)


class SensesAndUncanny(CampaignCase):
    def test_unseen_attacker_and_uncanny_dodge(self) -> None:
        self.new(blank="10x6", light="dark")
        seer = dict(GOBLIN, senses={"darkvision": 60})
        self.add("g1", "Gob", "B2", seer, init=20)
        self.add("C", "Corin", "C2", dict(PC_PROFILE, uncanny_dodge=True), side="pc", init=10)
        self.add("D", "Dara", "C3", PC_PROFILE, side="pc", init=5)
        self.run_cmd("next")
        import combat
        st = self.state()
        g, c, d = (combat.token(st, t) for t in ("g1", "C", "D"))
        c["acted"] = d["acted"] = True
        _, ac_c, notes_c, _, _ = combat.attack_mods(st, g, c, "melee")
        _, ac_d, notes_d, _, _ = combat.attack_mods(st, g, d, "melee")
        self.assertEqual(ac_c, 16 - 2)                         # uncanny dodge: keeps Dex, −2 for the dark
        self.assertEqual(ac_d, 12 - 2)                         # flat-footed against the unseen goblin
        self.assertNotIn("flat-footed", notes_c)

    def test_opponents_presumed_to_have_normal_vision(self) -> None:
        self.new(blank="10x6", light="dark")
        self.add("C", "Corin", "B2", dict(PC_PROFILE, senses={"darkvision": 60}), side="pc", init=20)
        self.add("g1", "Gob", "F2", GOBLIN, init=10)
        self.run_cmd("next")
        out = self.run_cmd("sight", "g1")
        self.assertIn("senses unknown", out)
        self.assertIn("C can't see it", out)                   # it thinks it's hidden in the dark
        self.run_cmd("attack", "C", "g1", "--total", "30", "--damage", "1", "--ranged")
        self.assertTrue(self.tok("C").get("senses_known"))
        self.assertIn("darkvision", self.run_cmd("sight", "g1"))


class TacticsWeights(CampaignCase):
    def plans(self, tok: str) -> str:
        return self.run_cmd("options", tok).split("Details:", 1)[0]

    def test_weights_and_broken_morale(self) -> None:
        self.new(blank="12x8")
        coward = dict(GOBLIN, tactics={"weights": {"melee": -3},
                                       "morale": {"hp": 0.5, "weights": {"retreat": 20}, "note": "flees"}})
        self.add("g1", "Coward", "C4", coward, init=20)
        self.add("C", "Corin", "D4", PC_PROFILE, side="pc", init=10)
        self.run_cmd("next")
        out = self.plans("g1")
        self.assertIn("melee -3", out)
        self.assertNotIn("MORALE BREAKS", out)
        self.run_cmd("hp", "g1", "-8")
        out = self.plans("g1")
        self.assertIn("MORALE BREAKS", out)
        first = out.split("  1. ", 1)[1].splitlines()[0]
        self.assertIn("withdraw", first)

    def test_encounter_tactics_override(self) -> None:
        self.new(blank="8x6")
        self.run_cmd("add", "g1", "Gob", "--pos", "B2", "--init", "5", "--profile", json.dumps(GOBLIN),
                     "--tactics", '{"weights": {"ranged": 2}}')
        self.assertEqual(self.tok("g1")["profile"]["tactics"], {"weights": {"ranged": 2}})

    def test_casting_in_melee_and_healing_the_dying(self) -> None:
        self.new(blank="12x8")
        healer = dict(GOBLIN, spellcasting=[{"class": "cleric", "cl": 1, "type": "spontaneous", "dc_base": 12,
                                             "concentration": 4, "slots": {"1": 2}, "spells": {"1": ["cure light wounds"]},
                                             "effects": {"cure light wounds": {"target": "one", "range": 0, "heal": "1d8+1"}}}])
        self.add("h1", "Healer", "C4", healer, init=20)
        self.add("a1", "Hurt", "C5", dict(GOBLIN, con=12), init=15)
        self.add("C", "Corin", "D4", PC_PROFILE, side="pc", init=25)
        self.run_cmd("hp", "a1", "-14")                      # dying
        self.run_cmd("next")                                  # Corin acts first: he can make AoOs now
        self.run_cmd("endturn", "C")
        self.run_cmd("next")
        out = self.plans("h1")
        heal = next(ln for ln in out.splitlines() if "cure light wounds on a1" in ln)
        self.assertIn("dying", heal)
        self.assertTrue("cast defensively" in heal or "provokes" in heal)   # Corin threatens the healer


class DiagonalCount(CampaignCase):
    def test_count_carries_over_within_the_turn_and_resets(self) -> None:
        self.new(blank="12x8")
        self.add("C", "Corin", "B2", PC_PROFILE, side="pc", init=20)
        self.add("g1", "Gob", "L8", GOBLIN, init=10)
        self.run_cmd("next")
        self.assertIn("B2 → C3: 5 ft", self.run_cmd("move", "C", "C3"))    # first diagonal
        self.assertIn("C3 → D4: 10 ft", self.run_cmd("move", "C", "D4"))   # second diagonal, same turn
        self.run_cmd("endturn", "C")
        self.run_cmd("next")
        st = self.state()
        self.assertEqual(st["turn"], "g1")
        self.run_cmd("next")                                       # Corin again: the count starts over
        self.assertIn("D4 → E5: 5 ft", self.run_cmd("move", "C", "E5"))


CLERIC = dict(GOBLIN, spellcasting=[{"class": "cleric", "cl": 3, "type": "prepared", "dc_base": 13, "concentration": 6,
                                     "slots": {"1": 2}, "spells": {"1": ["bless", "bless"]},
                                     "effects": {"bless": {"target": "area", "area": "burst 50", "center": "self",
                                                           "allies": {"atk": 1}, "buff": "blessed", "buff_rounds": 30}}}])


class SpellBuffsAndConditions(CampaignCase):
    def test_bless_buffs_allies_in_the_burst(self) -> None:
        self.new(blank="20x6")
        self.add("m1", "Mireth", "B2", CLERIC, side="ally", init=20)
        self.add("C", "Corin", "E2", PC_PROFILE, side="pc", init=10)
        self.add("a1", "Far ally", "T5", GOBLIN, side="ally", init=5)
        self.add("g1", "Gob", "D4", GOBLIN, init=1)
        self.run_cmd("next")
        out = self.run_cmd("cast", "m1", "bless")
        self.assertIn("blessed on", out)
        import combat_rules as R
        self.assertTrue(R.has(self.tok("C"), "blessed") and R.has(self.tok("m1"), "blessed"))
        self.assertFalse(R.has(self.tok("a1"), "blessed"))      # 90 ft away
        self.assertFalse(R.has(self.tok("g1"), "blessed"))      # an enemy
        self.assertEqual(R.total(self.tok("C"), "atk"), 1)

    def test_unknown_condition_names_fail_the_check(self) -> None:
        import combat_rules as R
        bad = dict(CASTER, spellcasting=[dict(CASTER["spellcasting"][0], effects={
            "magic missile": {"target": "one", "cond": "frightened (shaken if HD > 5)"}})])
        errs, _ = R.check_profile(bad)
        self.assertTrue(any("isn't a condition the script knows" in e for e in errs))
        ok = dict(CASTER, spellcasting=[dict(CASTER["spellcasting"][0], effects={
            "magic missile": {"target": "one", "cond": "evil eye", "cond_mods": {"atk": -2}}})])
        self.assertFalse([e for e in R.check_profile(ok)[0] if "cond" in e])


class FearAndAdvance(CampaignCase):
    def plans(self, tok: str) -> str:
        return self.run_cmd("options", tok).split("Details:", 1)[0]

    def test_frightened_only_flees(self) -> None:
        self.new(blank="12x8")
        self.add("g1", "Gob", "C4", GOBLIN, init=20)
        self.add("C", "Corin", "D4", PC_PROFILE, side="pc", init=10)
        self.run_cmd("next")
        self.run_cmd("cond", "g1", "add", "frightened", "--rounds", "2")
        out = self.plans("g1")
        self.assertIn("FRIGHTENED", out)
        self.assertNotIn("attack C", out)
        self.assertIn("withdraw", out)

    def test_out_of_reach_melee_closes_in(self) -> None:
        self.new(blank="16x8")
        brute = dict(GOBLIN, attacks={"club": {"bonus": 5, "damage": "1d6+3", "type": "melee"}})
        self.add("b1", "Brute", "A1", brute, init=20)
        self.add("C", "Corin", "P8", PC_PROFILE, side="pc", init=10)
        self.run_cmd("next")
        out = self.plans("b1")
        self.assertIn("closing on C", out)

    def test_briefing_lookup(self) -> None:
        self.new(blank="8x6")
        self.add("g1", "Gob", "B2", GOBLIN, init=20)
        self.add("C", "Corin", "D2", PC_PROFILE, side="pc", init=10)
        st = self.state()
        self.write("dm/combat/briefings.jsonl", json.dumps({"started": st.get("started"), "round": 1, "token": "g1",
                                                            "name": "Gob", "briefing": "PLANS HERE", "sight": ""}) + "\n")
        self.assertIn("PLANS HERE", self.run_cmd("briefing", "g1"))
        self.fail_cmd("briefing", "g1", "--round", "4")


BURNING = '# Burning Hands\n```spell-effect\n{"target": "area", "area": "cone 15", "save": "ref", "half": true, "dmg": "{min(cl,5)}d4"}\n```\n'
SLEEPY = '# Sleep\n```spell-effect\n{"target": "area", "area": "burst 10", "center": "point", "range": "medium", "save": "will", "cond": "asleep", "cond_rounds": "10*cl"}\n```\n'


class LibrarySpells(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.write("spells/burning-hands.md", BURNING)
        self.write("spells/sleep.md", SLEEPY)
        self.write("spells/detect-magic.md", '# Detect Magic\n```spell-effect\n{"utility": true}\n```\n')

    def caster(self, cl: int, **effects: dict) -> dict:
        return dict(GOBLIN, spellcasting=[{"class": "sorcerer", "cl": cl, "type": "spontaneous", "dc_base": 13,
                                           "concentration": 5, "slots": {"0": 99, "1": 4},
                                           "spells": {"0": ["detect magic"], "1": ["burning hands", "sleep", "magic missile"]},
                                           "effects": effects}])

    def test_effects_scale_with_caster_level(self) -> None:
        import combat_rules as R
        prof, errs, warns = R.resolve_spell_effects(self.caster(3))
        eff = prof["spellcasting"][0]["effects"]
        self.assertEqual(errs, [])
        self.assertEqual(eff["burning hands"]["dmg"], "3d4")
        self.assertEqual(eff["sleep"]["range"], 130)           # medium: 100 + 10/level
        self.assertEqual(eff["sleep"]["cond_rounds"], 30)
        self.assertNotIn("detect magic", eff)                    # utility: no effect, no warning
        self.assertTrue(any("magic missile" in w for w in warns))
        self.assertEqual(R.resolve_spell_effects(self.caster(9))[0]["spellcasting"][0]["effects"]["burning hands"]["dmg"], "5d4")

    def test_caster_overrides_merge_on_top(self) -> None:
        import combat_rules as R
        prof, errs, _ = R.resolve_spell_effects(self.caster(1, **{"burning hands": {"dmg_bonus": 1}}))
        self.assertEqual(prof["spellcasting"][0]["effects"]["burning hands"]["dmg"], "1d4+1")
        self.assertEqual(prof["spellcasting"][0]["effects"]["burning hands"]["save"], "ref")
        _, errs, _ = R.resolve_spell_effects(self.caster(1, **{"sleep": {"cond_rounds": "10*level"}}))
        self.assertTrue(any("not allowed in a formula" in e for e in errs))

    def test_cast_uses_the_library_effect(self) -> None:
        self.new(blank="10x6")
        self.add("s1", "Caster", "B3", self.caster(1), init=20)
        self.add("C", "Corin", "C3", PC_PROFILE, side="pc", init=10)
        self.run_cmd("next")
        out = self.run_cmd("cast", "s1", "burning hands", "--toward", "C3")
        self.assertIn("1d4", out)
        self.assertIn("PC saves pending (Corin)", out)
        self.assertIn("burning hands", self.run_cmd("options", "s1"))   # the plans see it too


class EffectDetails(CampaignCase):
    def test_dice_duration_self_buff_and_notes(self) -> None:
        self.write("spells/cause-fear.md", '```spell-effect\n{"target": "one", "range": "close", "save": "will", '
                                           '"cond": "frightened", "cond_rounds": "1d4", "notes": "6+ HD immune"}\n```\n')
        self.write("spells/shield.md", '```spell-effect\n{"target": "self", "range": "personal", "allies": {"ac": 4}, '
                                       '"buff": "shield", "buff_rounds": "10*cl"}\n```\n')
        caster = dict(GOBLIN, saves={"fort": 0, "ref": 0, "will": -20},
                      spellcasting=[{"class": "wizard", "cl": 2, "type": "spontaneous", "dc_base": 13, "concentration": 5,
                                     "slots": {"1": 3}, "spells": {"1": ["cause fear", "shield"]}}])
        self.new(blank="10x6")
        self.add("w1", "Witch", "B2", caster, init=20)
        self.add("a1", "Pal", "C2", GOBLIN, side="ally", init=15)
        self.add("g1", "Foe", "F2", dict(GOBLIN, saves={"fort": 0, "ref": 0, "will": -20}), init=10)
        self.run_cmd("next")
        out = self.run_cmd("cast", "w1", "cause fear", "--target", "g1")
        self.assertIn("DM, by hand: 6+ HD immune", out)
        cond = next(x for x in self.tok("g1")["conditions"] if x["name"] == "frightened")
        self.assertIn(cond["expires"]["round"] - 1, range(1, 5))     # 1d4 rounds, rolled
        self.run_cmd("cast", "w1", "shield", "--override")
        import combat_rules as R
        self.assertTrue(R.has(self.tok("w1"), "shield"))
        self.assertFalse(R.has(self.tok("a1"), "shield"))           # self only
