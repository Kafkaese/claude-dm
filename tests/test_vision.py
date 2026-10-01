"""vision: light levels, sources, darkness spells, senses and concealment."""
from __future__ import annotations

from tests.support import GOBLIN, PC_PROFILE, CampaignCase, V

CAVE = "##########\n#........#\n#........#\n#...##...#\n#........#\n##########\n"


class Light(CampaignCase):
    def level(self, sq: tuple[int, int], mult: int = 1) -> str:
        lvl, deep, _ = V.level_at(self.state(), sq, mult)
        return V.LEVELS[lvl] + ("*" if deep else "")

    def test_torch_bands_and_walls(self) -> None:
        self.new(map_text=CAVE, light="dark")
        self.run_cmd("light", "add", "torch", "--at", "B5")
        self.assertEqual(self.level((1, 4)), "normal")      # its own square
        self.assertEqual(self.level((5, 4)), "normal")      # 20 ft
        self.assertEqual(self.level((6, 4)), "dim")         # 25 ft: the increased band
        self.assertEqual(self.level((5, 2)), "dark")        # behind the wall block
        self.assertEqual(self.level((6, 4), mult=2), "normal")   # low-light vision doubles it

    def test_candle_only_dim(self) -> None:
        self.new(light="dark")
        self.run_cmd("light", "add", "candle", "--at", "C3")
        self.assertEqual(self.level((2, 2)), "dim")
        self.assertEqual(self.level((5, 5)), "dark")

    def test_darkness_switches_off_mundane_light(self) -> None:
        self.new(light="normal")
        self.run_cmd("light", "add", "sunrod", "--at", "C3")
        self.run_cmd("light", "add", "darkness", "--at", "C3")
        self.assertEqual(self.level((2, 2)), "dim")         # normal −1, the sunrod doesn't count

    def test_deeper_darkness_is_supernatural(self) -> None:
        self.new(light="normal")
        self.run_cmd("light", "add", "deeper darkness", "--at", "C3")
        self.assertEqual(self.level((2, 2)), "dark*")

    def test_daylight_and_darkness_cancel(self) -> None:
        self.new(light="dim")
        self.run_cmd("light", "add", "darkness", "--at", "C3")
        self.run_cmd("light", "add", "daylight", "--at", "D3")
        self.assertEqual(self.level((2, 2)), "dim")         # the otherwise prevailing light

    def test_bullseye_cone(self) -> None:
        self.new(blank="12x7", light="dark")
        self.run_cmd("light", "add", "bullseye lantern", "--at", "A1", "--toward", "L7")
        self.assertEqual(self.level((5, 0)), "normal")      # in the cone
        self.assertEqual(self.level((0, 5)), "dark")        # 90° off

    def test_light_zone_from_map_file(self) -> None:
        self.new(map_text="ambient: dim\n#####\n#...#\n#####\nlight:\n.....\n.B...\n")
        self.assertEqual(self.level((1, 1)), "bright")
        self.assertEqual(self.level((2, 1)), "dim")


class Seeing(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.new(light="dark")
        self.add("C", "Corin", "B2", dict(PC_PROFILE, senses={"low_light": True}), side="pc", init=20)
        self.add("g1", "Gob", "F2", dict(GOBLIN, senses={"darkvision": 60}))

    def test_darkvision_vs_normal_vision(self) -> None:
        st = self.state()
        c, g = self.tok("C"), self.tok("g1")
        self.assertEqual(V.concealment(st, g, c)[0], 0)       # darkvision sees the PC
        self.assertEqual(V.concealment(st, c, g)[0], 50)      # the PC is blind in the dark

    def test_torch_reveals_both_ways(self) -> None:
        self.run_cmd("light", "add", "torch", "--on", "C")
        st = self.state()
        self.assertEqual(V.concealment(st, self.tok("C"), self.tok("g1"))[0], 0)

    def test_attack_from_darkness_and_aoo_blocked(self) -> None:
        self.run_cmd("next")
        self.run_cmd("next")
        self.run_cmd("move", "g1", "C2")
        out = self.run_cmd("attack", "g1", "C", "--with", "spear")
        self.assertIn("target can't see in the dark", out)        # flat-footed and −2 AC
        self.run_cmd("next")                                      # Corin's turn: stays next to g1
        self.run_cmd("next")
        out = self.run_cmd("move", "g1", "D2")
        self.assertIn("can't see g1", out)                        # no AoO against what you can't see

    def test_hide_refused_in_plain_sight(self) -> None:
        self.run_cmd("light", "add", "torch", "--on", "g1")
        self.run_cmd("next")
        self.assertIn("can't hide", self.fail_cmd("hide", "g1"))
