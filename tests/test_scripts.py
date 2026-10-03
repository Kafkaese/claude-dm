"""roll.py, world.py and telemetry.py."""
from __future__ import annotations

import random
import unittest

import roll
import telemetry
import world
import sys

from tests.support import REPO, CampaignCase


class Dice(unittest.TestCase):
    def test_expressions(self) -> None:
        rng = random.Random(3)
        total, detail, _ = roll.evaluate("2d6+3", rng)
        self.assertTrue(5 <= total <= 15)
        total, _, _ = roll.evaluate("4d6dl1", rng)
        self.assertTrue(3 <= total <= 18)
        with self.assertRaises(roll.RollError):
            roll.evaluate("2d6+", rng)

    def test_nat20_flag_and_oracle(self) -> None:
        rng = random.Random(0)
        flags = set()
        for _ in range(200):
            flags |= set(roll.evaluate("1d20", rng)[2])
        self.assertIn("NAT 20", flags)
        self.assertIn("YES", roll.oracle(100, random.Random(1)))
        self.assertIn("NO", roll.oracle(0, random.Random(1)))


class World(CampaignCase):
    def run_world(self, *argv: str) -> int:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            return world.main(["-c", self.slug, *argv])

    def test_hop_never_rolls_and_budget(self) -> None:
        self.assertEqual(self.run_world("config", "--pressure", "relentless"), 0)
        self.assertEqual(self.run_world("session"), 0)
        self.assertEqual(self.run_world("turn", "hop"), 0)
        st = world.load(self.slug)
        self.assertEqual(st["interruptions"], 0)


class TelemetryReport(unittest.TestCase):
    def test_masking(self) -> None:
        self.assertEqual(telemetry.mask("it's g1's turn, not C's: D4 'spear' 17"), "it's TOK's turn, not TOK's: SQ '…' N")

    def test_summary(self) -> None:
        recs = [{"ts": "2026-10-01 10:00:00", "session": "s", "kind": "combat-step", "seconds": 12, "num_turns": 2,
                 "tool_calls": 1, "tool_errors": 0, "chars_out": 100,
                 "tools": [{"name": "mcp__dm__combat_batch", "call": '{"actions":[{"tool":"combat_move"},{"tool":"combat_attack"}]}'}]}]
        out = telemetry.summarize(recs, False)
        self.assertIn("combat_batch: move+attack", telemetry.game_command("mcp__dm__combat_batch", recs[0]["tools"][0]["call"]))
        self.assertIn("combat-step", out)


class TelemetryCosts(unittest.TestCase):
    def test_running_totals_become_per_exchange_costs(self) -> None:
        recs = [{"total_cost_usd": 0.3}, {"total_cost_usd": 1.2}, {"total_cost_usd": 1.5},
                {"total_cost_usd": 0.2},                                   # a new process started
                {"cost_usd": 0.1, "process_cost_usd": 0.3}]               # a new-style record
        self.assertEqual([round(c, 2) for c in telemetry.exchange_costs(recs)], [0.3, 0.9, 0.3, 0.2, 0.1])


class PlayGuard(unittest.TestCase):
    """During play the DM can't hand-edit combat state or the code; outside play nothing is blocked."""

    def run_hook(self, path: str, play: bool) -> int:
        import json as _json
        import os as _os
        import subprocess
        env = dict(_os.environ, CLAUDE_DM_MODE="play") if play else {k: v for k, v in _os.environ.items() if k != "CLAUDE_DM_MODE"}
        r = subprocess.run([sys.executable, str(REPO / ".claude/hooks/play_guard.py")], env=env, capture_output=True, text=True,
                           input=_json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}}))
        return r.returncode

    def test_guard(self) -> None:
        self.assertEqual(self.run_hook("/r/campaigns/x/dm/combat/current.json", True), 2)
        self.assertEqual(self.run_hook("/r/scripts/combat.py", True), 2)
        self.assertEqual(self.run_hook("/r/campaigns/x/dm/session-log/session-01.md", True), 0)
        self.assertEqual(self.run_hook("/r/scripts/combat.py", False), 0)


class EngineOffLimits(unittest.TestCase):
    """A DM locked to a campaign may run the scripts, but not read or search the engine's code or
    the fight's state files; without the lock (working on the repo) nothing is blocked."""

    def run_hook(self, tool: str, inp: dict, locked: bool = True) -> int:
        import json as _json
        import os as _os
        import subprocess
        env = {k: v for k, v in _os.environ.items() if k != "CLAUDE_DM_CAMPAIGN"}
        env["CLAUDE_PROJECT_DIR"] = str(REPO)
        if locked:
            env["CLAUDE_DM_CAMPAIGN"] = "demo"
        r = subprocess.run([sys.executable, str(REPO / ".claude/hooks/campaign_lock.py")], env=env, capture_output=True,
                           text=True, cwd=REPO, input=_json.dumps({"tool_name": tool, "tool_input": inp}))
        return r.returncode

    def test_reads_and_searches(self) -> None:
        self.assertEqual(self.run_hook("Read", {"file_path": str(REPO / "scripts/combat.py")}), 2)
        self.assertEqual(self.run_hook("Read", {"file_path": "dm_engine.py"}), 2)
        self.assertEqual(self.run_hook("Read", {"file_path": str(REPO / "campaigns/demo/dm/combat/current.json")}), 2)
        self.assertEqual(self.run_hook("Read", {"file_path": str(REPO / "campaigns/demo/dm/combat/archive/1.json")}), 2)
        self.assertEqual(self.run_hook("Grep", {"pattern": "surprise", "path": "scripts"}), 2)
        self.assertEqual(self.run_hook("Glob", {"pattern": "scripts/*.py"}), 2)
        self.assertEqual(self.run_hook("Read", {"file_path": str(REPO / "campaigns/demo/dm/combat/maps/a.txt")}), 0)
        self.assertEqual(self.run_hook("Read", {"file_path": str(REPO / "library/pf1e/spells/README.md")}), 0)
        self.assertEqual(self.run_hook("Read", {"file_path": str(REPO / "scripts/combat.py")}, locked=False), 0)

    def test_shell(self) -> None:
        bash = lambda c: self.run_hook("Bash", {"command": c})
        self.assertEqual(bash("python3 scripts/world.py -c demo session"), 0)
        self.assertEqual(bash(f"cd {REPO} && python3 scripts/roll.py 1d20 && cat campaigns/demo/dm/state.md"), 0)
        self.assertEqual(bash("grep -n 'def cmd_act' -A 40 scripts/combat.py | head -60"), 2)
        self.assertEqual(bash(f"sed -n '1,80p' {REPO}/scripts/combat_rules.py"), 2)
        self.assertEqual(bash("python3 scripts/roll.py 1d20; cat web.py"), 2)
        self.assertEqual(bash("cat campaigns/demo/dm/combat/current.json"), 2)
        self.assertEqual(bash("python3 -c \"print(open('scripts/combat.py').read())\""), 2)
        self.assertEqual(bash("grep -n Clocks campaigns/demo/dm/world.md"), 0)
