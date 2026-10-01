"""combat_rules: conditions and their ability effects, saves, schemas and profile checks."""
from __future__ import annotations

import unittest

from tests.support import GOBLIN, PC_PROFILE, R


def tok(conds: list[str], **prof: object) -> dict:
    base = {"dex": 17, "str": 14, "saves": {"fort": 3, "ref": 5, "will": 1}}
    base.update(prof)
    return {"token": "C", "ac": 16, "touch": 14, "ff": 12, "profile": base,
            "conditions": [{"name": n} for n in conds]}


class Conditions(unittest.TestCase):
    def test_plain_ac_unchanged(self) -> None:
        self.assertEqual(R.defenses(tok([])), {"ac": 16, "touch": 14, "ff": 12})

    def test_grappled_is_minus_4_dex_not_minus_2_ac(self) -> None:
        t = tok(["grappled"])
        self.assertEqual(R.defenses(t), {"ac": 14, "touch": 12, "ff": 12})   # Dex 17→13: +3→+1
        self.assertEqual(R.total(t, "ac"), 0)
        self.assertEqual(R.save_bonus(t, "ref"), 3)
        self.assertEqual(R.total(t, "atk"), -2)

    def test_armor_cap_absorbs_dex_penalty(self) -> None:
        self.assertEqual(R.defenses(tok(["grappled"], max_dex=1))["ac"], 16)

    def test_negative_dex_lowers_flat_footed(self) -> None:
        self.assertEqual(R.defenses(tok(["grappled"], dex=11)), {"ac": 14, "touch": 12, "ff": 10})

    def test_helpless_is_dex_zero(self) -> None:
        self.assertEqual(R.defenses(tok(["helpless"])), {"ac": 8, "touch": 6, "ff": 7})

    def test_exhausted_str_and_two_handed_damage(self) -> None:
        t = tok(["exhausted"])
        self.assertEqual(R.mod_change(t, "str"), -3)
        self.assertEqual(R.str_damage_change(t, {"str_damage": 1.5}, "melee"), -4)

    def test_pinned_flat_footed_minus_4(self) -> None:
        t = tok(["pinned"])
        self.assertTrue(R.flag(t, "flatfooted"))
        self.assertEqual(R.total(t, "ac"), -4)

    def test_restrictions(self) -> None:
        self.assertEqual(R.condition_names(tok(["grappled", "shaken"]), ("no_move",)), ["grappled"])
        self.assertEqual(R.condition_names(tok(["stunned"]), ("no_aoo",)), ["stunned"])

    def test_timed_condition_expires(self) -> None:
        st = {"round": 1, "turn": "g1", "tokens": []}
        c = {"token": "C", "conditions": []}
        st["tokens"].append(c)
        R.add_condition(st, c, "shaken", rounds=1)
        self.assertEqual(R.expire(st, "C", 2), [])
        self.assertEqual([n for _, n in R.expire(st, "g1", 2)], ["shaken"])


class Profiles(unittest.TestCase):
    def test_creature_and_pc_schemas(self) -> None:
        self.assertEqual(R.check_profile(GOBLIN)[0], [])
        self.assertEqual(R.check_profile(PC_PROFILE)[0], [])

    def test_pc_schema_requires_senses_etc(self) -> None:
        errs, _ = R.check_profile({"kind": "pc", "init": 3, "max_hp": 10, "ac": 15, "touch": 12, "ff": 13})
        for field in ("cmd", "str", "dex", "senses", "perception", "feats"):
            self.assertTrue(any(f"'{field}'" in e for e in errs), field)

    def test_creature_schema_rejects_pc_kind_and_unknown_fields(self) -> None:
        errs, _ = R.check_profile(dict(GOBLIN, colour="red"))
        self.assertTrue(any("colour" in e for e in errs))
        errs, _ = R.check_profile(dict(GOBLIN, cmb_vs={"tripp": 5}))
        self.assertTrue(any("tripp" in e for e in errs))

    def test_bad_damage_expression(self) -> None:
        bad = dict(GOBLIN, attacks={"spear": {"bonus": 2, "damage": "1d8+x", "type": "melee"}})
        self.assertTrue(R.check_profile(bad)[0])

    def test_find_attack(self) -> None:
        self.assertEqual(R.find_attack(GOBLIN, "spe")[0], "spear")
        self.assertEqual(R.find_attack(GOBLIN, "bow")[0], "shortbow")
        self.assertEqual(R.find_attack(GOBLIN, "axe"), (None, None))


class Validator(unittest.TestCase):
    def test_subset(self) -> None:
        s = {"type": "object", "required": ["a"], "additionalProperties": False,
             "properties": {"a": {"anyOf": [{"type": "integer"}, {"enum": ["roll"]}]},
                            "m": {"type": "object", "propertyNames": {"enum": ["x"]}, "additionalProperties": {"type": "integer"}}}}
        self.assertEqual(R._validate({"a": "roll", "m": {"x": 1}}, s, "p", []), [])
        self.assertTrue(R._validate({"a": "nope"}, s, "p", []))
        self.assertTrue(R._validate({"a": 1, "m": {"y": 1}}, s, "p", []))
        self.assertTrue(R._validate({}, s, "p", []))
