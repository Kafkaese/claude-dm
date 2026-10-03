"""mcp_server: the JSON-RPC protocol, schema validation, batches, and the command-line mapping."""
from __future__ import annotations

import json

import mcp_server as M
from tests.support import GOBLIN, PC_PROFILE, CampaignCase


class Protocol(CampaignCase):
    def test_initialize_and_list(self) -> None:
        srv = M.Server()
        r = M.handle(srv, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")
        self.assertIsNone(M.handle(srv, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
        tools = M.handle(srv, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        names = {t["name"] for t in tools}
        for n in ("combat_attack", "combat_batch", "combat_setup", "combat_options", "combat_act", "dice_roll", "world"):
            self.assertIn(n, names)
        self.assertEqual(M.handle(srv, {"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"], -32601)

    def test_every_tool_builds_a_command(self) -> None:
        # each schema's required fields are enough to build a command line
        for t in M.TOOLS:
            if t.script == "batch":
                continue
            args = {k: ("x" if t.props[k].get("type") == "string" else 1 if t.props[k].get("type") == "integer"
                        else ["x"] if t.props[k].get("type") == "array" else {"x": 1} if t.props[k].get("type") == "object"
                        else True) for k in t.required}
            if "enum" in str(t.props.get("action", "")):
                args["action"] = t.props["action"]["enum"][0]
            for k in t.required:
                if "enum" in t.props[k]:
                    args[k] = t.props[k]["enum"][0]
            try:
                self.assertTrue(M.cli_equivalent(t.name, args).startswith("python3 scripts/"), t.name)
            except ValueError as e:     # a conditional field is missing: must be a clear message
                self.assertIn("needs", str(e), t.name)


class Calls(CampaignCase):
    def setUp(self) -> None:
        super().setUp()
        self.srv = M.Server()

    def call(self, name: str, **args: object) -> tuple[bool, str]:
        return self.srv.call(name, args)

    def test_campaign_is_remembered(self) -> None:
        with self.assertRaises(M.ToolError):
            self.call("combat_info", what="show")
        ok, _ = self.call("combat_new", campaign=self.slug, blank="8x6")
        self.assertTrue(ok)
        ok, text = self.call("combat_info", what="show")
        self.assertTrue(ok, text)

    def test_validation_and_batch(self) -> None:
        self.call("combat_new", campaign=self.slug, blank="8x6")
        with self.assertRaises(M.ToolError) as e:
            self.call("combat_attack", attacker="g1", target="C", wiht="spear")
        self.assertIn("wiht", str(e.exception))
        ok, text = self.call("combat_batch", actions=[
            {"tool": "combat_add", "args": {"token": "C", "name": "Corin", "pos": "B2", "side": "pc", "init": "20",
                                            "hp": 30}},
            {"tool": "combat_light", "args": {"action": "ambient", "level": "dim"}}])
        self.assertFalse(ok)                                   # Corin has no profile: stops at [1]
        self.assertIn("[1] combat_add", text)
        self.assertNotIn("[2]", text)

    def test_dice(self) -> None:
        ok, text = self.call("dice_roll", campaign=self.slug, rolls=["Test: 1d20+5"])
        self.assertTrue(ok)
        self.assertIn("Test: 1d20+5 →", text)


class CampaignLock(CampaignCase):
    def test_locked_server_refuses_other_campaigns(self) -> None:
        import os
        import mcp_server as M
        os.environ["CLAUDE_DM_CAMPAIGN"] = self.slug
        try:
            srv = M.Server()
        finally:
            del os.environ["CLAUDE_DM_CAMPAIGN"]
        self.assertEqual(srv._campaign({}), self.slug)
        with self.assertRaises(M.ToolError):
            srv._campaign({"campaign": "some-other-campaign"})


class BatchCampaignSlip(CampaignCase):
    def test_campaign_inside_actions_is_accepted(self) -> None:
        import mcp_server as M
        self.new(blank="8x6")
        self.add("g1", "Gob", "B2", GOBLIN, init=10)
        srv = M.Server()
        ok, text = srv.call("combat_batch", {"campaign": self.slug, "actions": [
            {"tool": "combat_move", "args": {"campaign": self.slug, "token": "g1", "to": "C3", "out_of_turn": True}}]})
        self.assertTrue(ok, text)
        ok, text = srv.call("combat_batch", {"campaign": self.slug, "actions": [
            {"tool": "combat_move", "args": {"campaign": "another", "token": "g1", "to": "C4", "out_of_turn": True}}]})
        self.assertFalse(ok)
        self.assertIn("one batch plays one campaign", text)
