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
