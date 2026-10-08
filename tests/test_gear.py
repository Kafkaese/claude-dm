"""gear.py: items, containers, money, prices by the rules, shops, the live log and the generated sheet sections."""
from __future__ import annotations

import contextlib
import io
import json

from tests.support import CampaignCase

import gear  # noqa: E402  (tests.support puts scripts/ on the path)

ITEMS = {
    "longsword": {"name": "Longsword", "category": "weapon", "price": 15, "weight": 4, "source": "test",
                  "weapon": {"proficiency": "martial", "use": "one-handed", "damage_m": "1d8", "critical": "19-20/x2"}},
    "arrows": {"name": "Arrows", "category": "ammunition", "price": 1, "unit": 20, "weight": 3, "source": "test"},
    "studded-leather": {"name": "Studded leather", "category": "armor", "price": 25, "weight": 20, "source": "test",
                        "armor": {"kind": "light", "bonus": 3, "max_dex": 5, "check_penalty": -1}},
    "potion-of-cure-light-wounds": {"name": "Potion of cure light wounds", "category": "potion", "price": 50, "weight": 0,
                                    "consumable": True, "source": "test"},
    "wand-of-magic-missile": {"name": "Wand of magic missile", "category": "wand", "price": 750, "weight": 0, "charges": 50,
                              "source": "test"},
    "garnet": {"name": "Garnet", "category": "gem", "price": 100, "weight": 0, "source": "test"},
    "backpack": {"name": "Backpack", "category": "gear", "price": 2, "weight": 2, "source": "test"},
    "composite-longbow": {"name": "Composite longbow", "category": "weapon", "price": 100, "weight": 3, "str_rating_price": 100,
                          "source": "test"},
}
SHEET = """# Corin — Human Fighter 1
## Combat profile
```combat-profile
{"kind": "pc", "str": 14, "size": 1}
```
## Gear
- an old note the player wrote
"""


class GearCase(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        for slug, data in ITEMS.items():
            self.write(f"dm/items/{slug}.json", json.dumps(data))
        self.write("players/characters/corin.md", SHEET)
        self.write("players/party.md", "# Party\n## Gold & shared loot\n- old prose\n\n## Quests\n")
        self.write("dm/session-log/session-01.md", "# Session 01\n## Log\n-\n\n## Changes\n- **Loot & gold:**\n")
        self.write("dm/shops/smithy.json", json.dumps({
            "name": "Ossa's smithy", "settlement": "Sable's Landing", "purchase_limit": 100,
            "stock": [{"item": "longsword", "qty": 2}, {"item": "longsword", "masterwork": True, "qty": 1},
                      {"item": "arrows"}, {"item": "studded-leather", "qty": 1}]}))
        self.g("init", "--where", "a chest at the Cormorant's Rest")

    def g(self, *argv: str, ok: bool = True) -> str:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = gear.main(["-c", self.slug, *argv])
        self.assertEqual(rc == 0, ok, f"`{' '.join(argv)}`: {out.getvalue()}{err.getvalue()}")
        return (out.getvalue() + err.getvalue()).strip()

    def inv(self) -> dict:
        return json.loads((self.dir / "players/inventory.json").read_text())

    def corin(self) -> dict:
        return self.inv()["containers"]["corin"]


class Basics(GearCase):
    def test_init_containers_and_markers(self) -> None:
        cs = self.inv()["containers"]
        self.assertEqual(set(cs), {"stash", "corin"})
        self.assertEqual(cs["corin"]["label"], "Corin")
        self.assertEqual(cs["stash"]["where"], "a chest at the Cormorant's Rest")
        sheet = (self.dir / "players/characters/corin.md").read_text()
        self.assertIn(gear.MARK_BEGIN, sheet)
        self.assertIn("an old note the player wrote", sheet)          # existing prose stays
        self.assertIn(gear.MARK_BEGIN, (self.dir / "players/party.md").read_text())
        self.assertIn("exists already", self.g("init", ok=False))
        self.write("players/characters/mira.md", "# Mira\n## Gear\n")
        self.g("container", "mira", "--label", "Mira", "--kind", "character", "--sheet", "players/characters/mira.md")
        self.g("container", "horse", "--label", "Packhorse", "--kind", "other", "--where", "Bessie, the party's mule")
        self.assertEqual(set(self.inv()["containers"]), {"stash", "corin", "mira", "horse"})
        self.assertIn(gear.MARK_BEGIN, (self.dir / "players/characters/mira.md").read_text())
        self.assertIn("Bessie", (self.dir / "players/party.md").read_text())
        self.g("where", "stash", "a locked chest at the Gull & Lantern")
        self.assertEqual(self.inv()["containers"]["stash"]["where"], "a locked chest at the Gull & Lantern")

    def test_money(self) -> None:
        self.g("receive", "stash", "100 gp", "--why", "bounty")
        self.g("move", "25 gp 5 sp", "--from", "stash", "--to", "corin")
        self.assertEqual(self.corin()["coins"], {"gp": 25, "sp": 5})
        self.g("pay", "corin", "3 sp", "--why", "a room")
        self.assertEqual(self.corin()["coins"], {"gp": 25, "sp": 2})
        self.g("pay", "corin", "2 cp", "--why", "a bread")                # makes change
        self.assertEqual(gear.coins_cp(self.corin()["coins"]), 2518)
        self.assertIn("has only", self.g("pay", "corin", "50 gp", "--why", "a horse", ok=False))
        self.assertIn("--why", self.g("pay", "corin", "1 gp", ok=False))
        log = (self.dir / "dm/session-log/session-01.md").read_text()
        self.assertIn("## Gear & money", log)
        self.assertLess(log.index("## Gear & money"), log.index("## Changes"))
        self.assertIn("Party stash receives 100 gp (bounty)", log)

    def test_items_stack_split_and_equip(self) -> None:
        self.g("add", "stash", "arrows", "--qty", "20", "--why", "loot")
        self.g("add", "stash", "arrows", "--qty", "10")
        self.assertEqual([e["qty"] for e in self.inv()["containers"]["stash"]["items"]], [30])
        self.g("move", "arrows", "--from", "stash", "--to", "corin", "--qty", "12")
        self.assertEqual(self.inv()["containers"]["stash"]["items"][0]["qty"], 18)
        self.g("add", "corin", "longsword", "--mw", "--name", "Rasa's blade")
        self.g("equip", "corin", "rasa")
        e = next(x for x in self.corin()["items"] if x.get("name") == "Rasa's blade")
        self.assertTrue(e["equipped"] and e["masterwork"])
        self.assertIn("matches several", self.g("remove", "corin", "o", "--why", "x", ok=False))
        self.g("remove", "corin", "arrows", "--qty", "2", "--why", "lost in the river")
        self.assertEqual(next(x for x in self.corin()["items"] if x["item"] == "arrows")["qty"], 10)

    def test_use_consumables_and_charges(self) -> None:
        self.g("add", "corin", "potion of cure", "--qty", "2")
        self.g("use", "corin", "potion")
        self.assertEqual(self.corin()["items"][0]["qty"], 1)
        self.g("add", "corin", "wand of magic missile", "--charges", "10")
        self.g("use", "corin", "wand", "--charges", "3")
        self.assertEqual(next(x for x in self.corin()["items"] if x["item"].startswith("wand"))["charges"], 7)
        self.g("add", "corin", "backpack")
        self.assertIn("isn't used up", self.g("use", "corin", "backpack", ok=False))


class Prices(GearCase):
    def test_rules(self) -> None:
        self.assertIn("costs 15 gp, sells for 7 gp 5 sp", self.g("price", "longsword"))
        self.assertIn("costs 315 gp", self.g("price", "longsword", "--mw"))
        self.assertIn("costs 2315 gp", self.g("price", "longsword", "--plus", "1"))            # 15 + 300 + 2000
        self.assertIn("costs 4175 gp", self.g("price", "studded leather", "--plus", "2"))      # 25 + 150 + 4000
        self.assertIn("costs 6 gp 5 cp", self.g("price", "arrows", "--mw"))                    # 5 cp + 6 gp a piece
        self.assertIn("costs 1 gp, sells for 5 sp · 3 lbs", self.g("price", "arrows", "--qty", "20"))
        self.assertIn("2 lbs", self.g("price", "longsword", "--size", "small"))
        self.assertIn("sells for 100 gp", self.g("price", "garnet"))                           # gems: full value
        self.assertIn("Composite longbow (+2 Str): costs 300 gp", self.g("price", "composite longbow", "--str-rating", "2"))
        item, e = ITEMS["wand-of-magic-missile"], {"item": "wand", "qty": 1, "charges": 25}
        self.assertEqual(gear.sale_value_cp(item, e), 18750)                                   # half of half
        self.assertEqual(gear.sale_value_cp(ITEMS["longsword"], {"item": "x", "qty": 1, "broken": True}), 562)

    def test_carrying_capacity(self) -> None:
        self.assertEqual(gear.heavy_load(10), 100)
        self.assertEqual(gear.heavy_load(15), 200)
        self.assertEqual(gear.heavy_load(21), 460)
        self.assertEqual(gear.heavy_load(30), 1600)
        self.assertEqual(gear.heavy_load(10, "small"), 75)
        self.assertEqual(gear.load_of(58, 14), "light")                                        # Str 14: 175 → ≤58
        self.assertEqual(gear.load_of(59, 14), "medium")


class Shops(GearCase):
    def setUp(self) -> None:
        super().setUp()
        self.g("receive", "corin", "400 gp", "--why", "savings")

    def test_buy(self) -> None:
        out = self.g("buy", "smithy", "masterwork longsword", "--by", "corin")
        self.assertIn("buys masterwork Longsword at Ossa's smithy for 315 gp", out)
        self.assertEqual(gear.coins_cp(self.corin()["coins"]), 8500)
        self.assertIn("has only 0", self.g("buy", "smithy", "masterwork longsword", "--by", "corin", ok=False))   # sold out
        self.g("buy", "smithy", "arrows", "--by", "corin", "--qty", "40", "--to", "stash")       # unlimited stock
        self.assertEqual(self.inv()["containers"]["stash"]["items"][0]["qty"], 40)
        self.assertIn("has only", self.g("buy", "smithy", "studded leather", "--by", "corin", "--qty", "2", ok=False))
        self.assertIn("needs a reason", self.g("buy", "smithy", "longsword", "--by", "corin", "--price", "10", ok=False))
        self.g("buy", "smithy", "longsword", "--by", "corin", "--price", "10", "--why", "haggled")
        shop = json.loads((self.dir / "dm/shops/smithy.json").read_text())
        self.assertEqual(shop["stock"][0]["qty"], 1)

    def test_sell(self) -> None:
        self.g("add", "corin", "longsword", "--qty", "2", "--why", "loot")
        out = self.g("sell", "smithy", "corin", "longsword", "--qty", "1")
        self.assertIn("sells Longsword to Ossa's smithy for 7 gp 5 sp", out)
        self.assertEqual(json.loads((self.dir / "dm/shops/smithy.json").read_text())["stock"][0]["qty"], 3)   # restocked
        self.g("add", "corin", "garnet")
        self.assertIn("doesn't deal in gem", self.g("sell", "smithy", "corin", "garnet", ok=False))
        self.g("add", "corin", "longsword", "--plus", "1")
        self.assertIn("purchase limit", self.g("sell", "smithy", "corin", "+1", ok=False))       # worth 1157 gp > 100
        self.g("sell", "smithy", "corin", "+1", "--price", "100", "--why", "purchase limit")
        self.assertIn("Ossa's smithy", self.g("shop", "smithy"))
        self.assertEqual(self.g("check"), "OK")


class Rendering(GearCase):
    def test_sheet_and_party_sections(self) -> None:
        self.g("add", "corin", "studded leather", "--equipped")
        self.g("receive", "corin", "12 gp", "--why", "wages")
        self.g("add", "stash", "backpack", "--qty", "2")
        sheet = (self.dir / "players/characters/corin.md").read_text()
        block = sheet.split(gear.MARK_BEGIN)[1].split(gear.MARK_END)[0]
        self.assertIn("Studded leather (equipped)", block)
        self.assertIn("Coins: 12 gp", block)
        self.assertIn("Load: light (Str 14", block)
        party = (self.dir / "players/party.md").read_text()
        self.assertIn("2 × Backpack", party.split(gear.MARK_BEGIN)[1])
        self.assertIn("a chest at the Cormorant's Rest", party)
        self.assertIn("## Quests", party)                                                       # the rest is untouched

    def test_mcp_tool(self) -> None:
        import mcp_server as M
        srv = M.Server()
        ok, text = srv.call("gear", {"campaign": self.slug, "action": "receive", "container": "stash", "amount": "5 gp",
                                     "why": "found"})
        self.assertTrue(ok, text)
        ok, text = srv.call("gear", {"action": "show", "container": "stash"})
        self.assertIn("5 gp", text)
        with self.assertRaises(M.ToolError):                                                    # why is missing
            srv.call("gear", {"action": "remove", "container": "stash", "item": "x"})
