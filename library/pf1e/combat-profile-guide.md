# Translating a PF1e Stat Block into a Combat Profile

`scripts/combat.py` runs fights from a ` ```combat-profile ` JSON block. The schema is `combat-profile.schema.json` (next to this file). It lists every field, which fields are required, and the allowed values. This guide covers how to fill it in from a stat block.

**The rules:**
- **Copy the numbers exactly as printed.** Don't recalculate or "fix" them, and don't add situational modifiers. The script applies flanking, conditions and the like itself.
- **One profile per stat block,** placed right after it in the same file.
- **Check it before you use it:** `python3 scripts/combat.py -c <campaign> profile check <file>`. `add` also rejects profiles that break the schema.
- **Anything the fields can't express** goes in `special`, `rider`, `save_notes` or `ac_notes`. The DM applies those by hand.

## Line by line

| Stat block | Profile |
|---|---|
| **Init** +6 | `"init": 6` |
| **hp** 11 (2d8+2) | `"hp": 11` (optionally `"max_hp"`) |
| **AC** 16, touch 13, flat-footed 14 | `"ac": 16, "touch": 13, "ff": 14` |
| AC … ; +4 dodge vs. giants | `"ac_notes": ["+4 dodge vs. giants"]` |
| **Fort** +3, **Ref** +2, **Will** −1 | `"saves": {"fort": 3, "ref": 2, "will": -1}` |
| … ; +2 vs. fear | `"save_notes": ["+2 vs. fear"]` |
| **DR** 5/magic | `"dr": 5, "dr_bypass": "magic"` |
| **Hardness** 10 (objects) | `"dr": 10, "dr_bypass": "-"` |
| **Immune** fire, sleep; **Resist** cold 10 | `"immune": ["fire", "sleep"], "resist": {"cold": 10}` |
| **SR** 15 | `"sr": 15` |
| **fast healing** 2 / **regeneration** 5 (fire, acid) | `"fast_healing": 2` / `"regeneration": {"amount": 5, "stopped_by": "fire, acid"}` |
| **Defensive Abilities** uncanny dodge | `"uncanny_dodge": true` |
| Other defensive abilities (ferocity, evasion, …) | `"special": ["ferocity", "evasion"]` |
| **Speed** 30 ft., fly 60 ft. (good) | `"speed": 30, "speeds": {"fly": 60, "fly_maneuverability": "good"}` |
| **Space** 10 ft.; **Reach** 10 ft. | `"size": 2, "reach": 10` (5 ft. → 1, 10 ft. → 2, 15 ft. → 3, 20 ft. → 4; Small and Tiny creatures → 1) |
| **Str** 17, **Dex** 15, **Con** 12 … | `"con": 12, "dex": 15` (a score of "—" → `null`) |
| **Base Atk** +1; **CMB** +3; **CMD** 15 | `"cmb": 3, "cmd": 15` |
| **Feats** Combat Reflexes, Improved Initiative | `"feats": ["Combat Reflexes", "Improved Initiative"]` |

## Attacks
Each distinct attack gets an entry in `attacks`. The **name** is the weapon or natural attack in lowercase (`"longsword"`, `"bite"`), and the DM uses it with `attack … --with <name>`.

| Stat block | Entry |
|---|---|
| **Melee** longsword +5 (1d8+3/19–20) | `"longsword": {"bonus": 5, "damage": "1d8+3", "type": "melee", "crit": 19}` |
| **Melee** greataxe +6 (1d12+4/×3) | `"greataxe": {"bonus": 6, "damage": "1d12+4", "type": "melee", "mult": 3}` |
| **Melee** mwk longsword +8/+3 (1d8+3/19–20) | `"bonus": [8, 3]` (iterative; `attack --full` uses all of them) |
| **Melee** bite +4 (1d6+1 plus trip) | `"bite": {"bonus": 4, "damage": "1d6+1", "type": "melee", "rider": "plus trip"}` |
| **Melee** 2 claws +5 (1d4+2), bite +5 (1d6+2) | `"claw": {…}, "bite": {…}`, plus `"full_attack": ["bite", "claw", "claw"]` |
| **Melee** touch +3 (1d6 negative energy) | `"type": "melee", "touch": true, "damage": "1d6", "damage_type": "negative energy"` |
| **Melee** sap +3 (1d6+1 nonlethal) | `"nonlethal": true` |
| **Ranged** shortbow +4 (1d6/×3) | `"shortbow": {"bonus": 4, "damage": "1d6", "type": "ranged", "mult": 3, "range": 60}` |
| **Ranged** javelin +4 (1d6+3) | `"type": "ranged", "thrown": true, "range": 30` |
| longspear (reach) | `"reach": 10` on that attack |

- **Crit:** `crit` is the **lowest** number of the threat range (`/18–20` → 18), and `mult` the multiplier (`/×3` → 3). Leave them out for 20/×2.
- **Damage:** only dice and flat numbers. Extra damage like "plus 1d6 fire" goes in `rider`, as does poison, grab and trip.
- **Range increments aren't in the stat block.** Take them from the weapon table (`library/pf1e/items/` or the allowed sources), e.g. shortbow 60, longbow 100, light crossbow 80, javelin 30, dagger 10, sling 50.
- **Primary and secondary natural attacks:** the stat block already prints the right bonuses and damage, so copy them.
- **Special attacks** (breath weapon, rend, pounce, trample, …) go in `special`. Area attacks run through `combat.py area`.

## Spellcasting
Each spellcasting class or source becomes one entry in `spellcasting`:

| Stat block | Profile |
|---|---|
| **Sorcerer Spells Known** (CL 5th; concentration +8) | `"class": "sorcerer", "type": "spontaneous", "cl": 5, "concentration": 8` |
| 2nd (5/day)—*scorching ray*, *invisibility* | `"slots": {"2": 5}`, `"spells": {"2": ["scorching ray", "invisibility"]}` |
| 0 (at will)—*detect magic*, *ray of frost* | `"slots": {"0": 99}`, `"spells": {"0": [...]}` |
| **Cleric Spells Prepared** (CL 3rd; concentration +6) | `"class": "cleric", "type": "prepared", "cl": 3, "concentration": 6` |
| 1st—*bless*, *cure light wounds* (2), *protection from evil*^D | `"slots": {"1": 4}`, `"spells": {"1": ["bless", "cure light wounds", "cure light wounds", "protection from evil"]}`, `"domain": {"1": "protection from evil"}` |
| (DCs) | `"dc_base"`: 10 + the casting ability modifier. The stat block's DCs are dc_base + spell level; check one to confirm. |

- **Spell names** are lowercase, without italics.
- **Prepared spells** are listed once **per copy**. `slots` counts how many are prepared at that level, including the domain spell.
- **Spontaneous casters** list their spells known in `spells`, and their spells per day in `slots`.

**Spell-like abilities** go in `sla`:

| Stat block | Profile |
|---|---|
| **Spell-Like Abilities** (CL 3rd; concentration +5) | one entry per ability, each with `"cl": 3` |
| At will—*detect magic* | `{"name": "detect magic", "per_day": "at will", "level": 0}` |
| 3/day—*darkness* | `{"name": "darkness", "per_day": 3, "level": 2}` |
| 1/day—*hold person* (DC 15) | `{"name": "hold person", "per_day": 1, "level": 2, "dc": 15}` |
| Constant—*detect evil* | `{"name": "detect evil", "per_day": "constant"}` |

Where the stat block lists the spell's level, put it in `level`, because the concentration DC depends on it.

## Player characters
`"kind": "pc"` needs only the defensive numbers (`init`, `hp`, `ac`, `touch`, `ff`, `saves`, and ideally `con`, `dex`, `cmd`, `uncanny_dodge`, `feats`), because the player rolls their own attacks and tracks their own spells. The PC's current HP lives on the sheet's HP line.

## A complete example
```combat-profile
{"kind": "creature", "init": 6, "hp": 6, "ac": 16, "touch": 13, "ff": 14, "cmb": 1, "cmd": 13,
 "saves": {"fort": 3, "ref": 2, "will": -1}, "speed": 30, "size": 1, "reach": 5,
 "con": 12, "dex": 15, "feats": ["Improved Initiative"],
 "attacks": {"short sword": {"bonus": 2, "damage": "1d4", "type": "melee", "crit": 19, "damage_type": "P"},
             "shortbow": {"bonus": 4, "damage": "1d4", "type": "ranged", "mult": 3, "range": 60, "damage_type": "P"}},
 "source": "Bestiary pg. 156"}
```
