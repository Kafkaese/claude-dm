# Prepared encounters (DM ONLY)
One file per fight, written during prep (by the scribe) so the fight can be set up in one call at the table:
`python3 scripts/combat.py -c <campaign> setup <name> --init C=17` (in web/terminal play: the `combat_setup` tool).

Each file has DM notes in prose, plus one ` ```encounter ` JSON block. The format is `library/general/encounter.schema.json`. Check every file with `python3 scripts/combat.py -c <campaign> encounter check` until it reports OK; it validates the map, every combat profile, the squares and the light sources without creating anything.

Example (`dm/combat/encounters/ford-ambush.md`):

    # Ambush at the ford
    Kobolds wait in the reeds on the far bank. Why they're here, and what they want, in prose.

    ```encounter
    {"title": "Ambush at the ford",
     "map": "dm/combat/maps/ford.txt",
     "light": "dim",
     "pc_start": ["B4"],
     "combatants": [
       {"token": "k", "count": 2, "name": "Kobold", "ref": "library/pf1e/bestiary/kobold.md",
        "pos": ["H2", "I4"], "hidden": true, "cr": "1/4"},
       {"token": "s1", "name": "Scalecaster", "ref": "library/pf1e/bestiary/kobold-scalecaster.md",
        "pos": "I2", "cr": "1"}],
     "lights": [{"kind": "torch", "on": "s1"}],
     "tactics": "The kobolds shoot from the reeds; the scalecaster opens with a spell, then stays behind them.",
     "morale": "They flee when the scalecaster drops.",
     "exit_ramp": "If the PC goes down, they take the purse and run."}
    ```

- **Paths:** `map` and `ref` are relative to the campaign folder, except `library/…` and `campaigns/…`.
- **PCs:** `pc_start` places the sheets in `players/characters/` in order (tokens: first letter of the name). `setup --place C=E5` overrides a square at the table, e.g. when the PC arrives from another side. A `pcs` list sets PCs explicitly instead.
- **Groups:** `count` with a one-letter `token` makes k1, k2, … and numbers the names.
- **Lighting:** the ambient `light` (or the map file's `ambient:` line), `zones`, and `lights` (at a square or carried by a combatant).
- **Who plays whom:** in web/terminal play, the combat runner (a lean process) plays the NPCs' turns. Give a boss or a story NPC with plans and dialogue `"dm_plays": true`, so the main DM, who knows the campaign, plays it.
- **Initiative:** NPCs roll from their profiles (or `"init": 15`); the PCs' rolls come from the player at setup.
