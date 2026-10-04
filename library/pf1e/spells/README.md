# Spells
Spell entries, for anything that comes up often or that you need to adjudicate. One file per spell, named after it: `cure-light-wounds.md`.

## Combat effect (```spell-effect)
Every spell a combatant can cast in a fight gets a `spell-effect` block. `scripts/combat.py` reads it when a caster joins a fight, works it out at the caster's level, and uses it for `cast`, the save, the damage, buffs and conditions, and the tactical options. Stat blocks then only **list** the spell. Write the block once, from the spell's own text.

```spell-effect
{"target": "area", "area": "cone 15", "save": "ref", "half": true, "dmg": "{min(cl,5)}d4"}
```

- **Fields:** see `library/pf1e/spell-effect.schema.json`. They are `target` (one, area, self), `area` (burst/cone/line N), `center`, `range`, `save`, `half`, `dmg`, `heal`, `cond`, `cond_rounds`, `cond_mods`, buffs (`allies`, `buff`, `buff_rounds`), `touch`, `immunity`, and `notes`.
- **Formulas of the caster level `cl`:** numbers can be formulas, like `"cond_rounds": "10*cl"` (1 min./level). Dice put the formula in braces, like `"dmg": "{min(cl,5)}d4"` or `"heal": "1d8+{min(cl,5)}"`. Allowed: `+ - * //`, `min()`, `max()`; `/` rounds down.
- **Range keywords:** `touch`, `personal`, `close`, `medium`, `long` (formulas in `library/pf1e/spellcasting.json`), or feet.
- **Conditions:** use a name from `library/pf1e/conditions.json` (`asleep`, `frightened`, `blessed`, …). A custom one brings `cond_mods`; `{}` means it's tracked by name only, on purpose. Buffs work the same way: `"buff": "blessed"` takes the catalog's modifiers, or `allies` gives them.
- **Immunity afterwards:** `"immunity": {"rounds": 10, "from": "anyone", "after": "affected"}` (daze: a creature dazed by it is immune to it for 1 minute). `from: "caster"` for "not again from the same caster" (many hexes), `after: "targeted"` when it applies whether or not the save succeeded. The target gets a tracked "immune to …" condition; a single-target use is refused while it lasts, and an area skips it.
- **Spell resistance:** `"sr": true` or `false`, from the spell's Spell Resistance line; `"sr_harmless": true` for "yes (harmless)". A missing `sr` counts as yes. The script makes the caster level check (1d20 + CL vs SR) per target before the effect; a PC's check is the player's roll.
- **What the script can't apply** (temporary HP, a bonus only against fear, HD limits, choices) goes in `notes`; the DM handles it.
- **No combat effect** (detect magic, prestidigitation): `{"utility": true}`.
- **Not in the block:** anything that depends on the caster. The DC comes from the stat block (`dc_base` + spell level). The touch attack bonus goes in the stat block's `effects` entry, e.g. `{"attack": 4}`. So do extras like bloodline arcana's `{"dmg_bonus": 1}`.

Check with `python3 scripts/combat.py -c <campaign> profile check <stat block>`: it resolves every spell of the caster and validates the result.
