"""Shared test helpers: a throwaway campaign, in-process script calls, and fixed dice.

Run the whole suite from the repo root with:  python3 -m unittest discover -s tests -t .
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import random
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import combat  # noqa: E402
import combat_rules as R  # noqa: E402
import vision as V  # noqa: E402
import world  # noqa: E402

PC_PROFILE = {"kind": "pc", "init": 3, "max_hp": 30, "ac": 16, "touch": 14, "ff": 12, "cmd": 17,
              "str": 12, "dex": 17, "con": 12, "speed": 30, "size": 1, "senses": {}, "perception": 6, "feats": []}
GOBLIN = {"kind": "creature", "init": 6, "hp": 12, "ac": 15, "touch": 13, "ff": 14, "cmb": 1, "cmd": 13,
          "saves": {"fort": 3, "ref": 2, "will": -1}, "str": 11, "dex": 15, "speed": 30,
          "attacks": {"spear": {"bonus": [4, -1], "damage": "1d8", "type": "melee"},
                      "shortbow": {"bonus": 4, "damage": "1d6", "type": "ranged", "range": 60}}}
CASTER = dict(GOBLIN, spellcasting=[{"class": "sorcerer", "cl": 3, "type": "spontaneous", "dc_base": 13,
                                     "concentration": 5, "slots": {"1": 2, "2": 1},
                                     "spells": {"1": ["magic missile"], "2": ["darkness"]}}])


def sheet(name: str, profile: dict[str, Any] | None = None, hp: str = "30 / 30") -> str:
    """A minimal character sheet with an HP line and a combat-profile block."""
    return f"# {name}\n**HP:** {hp}\n```combat-profile\n{json.dumps(profile or PC_PROFILE)}\n```\n"


class CampaignCase(unittest.TestCase):
    """A test case with its own throwaway campaign, fixed dice, and no play-mode environment."""

    def setUp(self) -> None:
        self.slug = f"_test_{uuid.uuid4().hex[:8]}"
        self.dir = REPO / "campaigns" / self.slug
        for d in ("dm/combat/maps", "dm/combat/encounters", "players/characters"):
            (self.dir / d).mkdir(parents=True)
        (self.dir / "campaign.md").write_text("# Test\n**System:** pf1e\n")
        self._env = os.environ.pop("CLAUDE_DM_MODE", None)
        combat.RNG = random.Random(1)
        world.RNG = random.Random(1)
        R.SPELLS_DIR = self.dir / "spells"   # hermetic: only the spells a test writes (the library's are local data)

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)
        combat.RNG = None
        world.RNG = None
        R.SPELLS_DIR = None
        if self._env is not None:
            os.environ["CLAUDE_DM_MODE"] = self._env

    # --- running commands ---
    def run_cmd(self, *argv: str, ok: bool = True) -> str:
        """Run combat.py in-process; assert it succeeded (or failed, with ok=False). Returns the output."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = combat.main(["-c", self.slug, *argv])
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 2
        text = (out.getvalue() + err.getvalue()).strip()
        if ok:
            self.assertEqual(rc, 0, f"`{' '.join(argv)}` failed:\n{text}")
        else:
            self.assertNotEqual(rc, 0, f"`{' '.join(argv)}` should have failed:\n{text}")
        return text

    def fail_cmd(self, *argv: str) -> str:
        """Run a command that must fail; returns its error text."""
        return self.run_cmd(*argv, ok=False)

    # --- building fights ---
    def write(self, rel: str, text: str) -> Path:
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def new(self, blank: str = "10x8", light: str | None = None, map_text: str | None = None) -> None:
        if map_text is not None:
            self.write("dm/combat/maps/m.txt", map_text)
            self.run_cmd("new", str(self.dir / "dm/combat/maps/m.txt"), *(["--light", light] if light else []))
        else:
            self.run_cmd("new", "--blank", blank, *(["--light", light] if light else []))

    def add(self, tok: str, name: str, pos: str, profile: dict[str, Any], side: str = "enemy",
            init: int = 10, *extra: str) -> None:
        args = ["add", tok, name, "--pos", pos, "--side", side, "--init", str(init), "--profile", json.dumps(profile)]
        if side == "pc" and "hp" not in profile:
            args += ["--hp", str(profile.get("max_hp", 30))]
        self.run_cmd(*args, *extra)

    def state(self) -> dict[str, Any]:
        return combat.load(self.slug)

    def tok(self, t: str) -> dict[str, Any]:
        return combat.token(self.state(), t)
