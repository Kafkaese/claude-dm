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
| **Senses** darkvision 60 ft., low-light vision, scent; **Perception** +5 | `"senses": {"darkvision": 60, "low_light": true, "scent": true}, "perception": 5`. Other keys: `see_in_darkness`, `blindsight`/`blindsense`/`tremorsense` (ft), and from **Weaknesses** `light_sensitivity` / `light_blindness`. Always fill this in, for PCs too (race: elves and half-elves low-light, dwarves darkvision 60): the script decides what each creature sees from it |
| **hp** 11 (2d8+2) | `"hp": 11` (optionally `"max_hp"`) |
| **AC** 16, touch 13, flat-footed 14 | `"ac": 16, "touch": 13, "ff": 14` |
| AC … ; +4 dodge vs. giants | `"ac_notes": ["+4 dodge vs. giants"]` |
| **Fort** +3, **Ref** +2, **Will** −1 | `"saves": {"fort": 3, "ref": 2, "will": -1}` |
| … ; +2 vs. fear | `"save_notes": ["+2 vs. fear"]` |
| **DR** 5/magic | `"dr": 5, "dr_bypass": "magic"` |
| **Hardness** 10 (objects) | `"dr": 10, "dr_bypass": "-"` |
| **Immune** fire, sleep; **Resist** cold 10 | `"immune": ["fire", "sleep"], "resist": {"cold": 10}` |
| **SR** 15 | `"sr": 15`: spells and spell-like abilities must beat it with a caster level check (1d20 + CL); supernatural and extraordinary abilities ignore it |
| **fast healing** 2 / **regeneration** 5 (fire, acid) | `"fast_healing": 2` / `"regeneration": {"amount": 5, "stopped_by": "fire, acid"}` |
| **Defensive Abilities** uncanny dodge | `"uncanny_dodge": true` |
| **Defensive Abilities** improved uncanny dodge | `"improved_uncanny_dodge": true` (can't be flanked) |
| Other defensive abilities (ferocity, evasion, …) | `"special": ["ferocity", "evasion"]` |
| **Speed** 30 ft., fly 60 ft. (good) | `"speed": 30, "speeds": {"fly": 60, "fly_maneuverability": "good"}` |
| **Space** 10 ft.; **Reach** 10 ft. | `"size": 2, "reach": 10` (5 ft. → 1, 10 ft. → 2, 15 ft. → 3, 20 ft. → 4; Small and Tiny creatures → 1) |
| **Str** 17, **Dex** 15, **Con** 12 … | `"str": 17, "dex": 15, "con": 12` (a score of "—" → `null`). Always include Str and Dex: conditions like grappled (−4 Dex) or fatigued (−2 Str/Dex) are applied through them |
| Armor with a max Dex bonus that limits the creature's Dex bonus (e.g. Dex 16 in a breastplate, max Dex +3) | `"max_dex": 3`. Skip it when the cap doesn't bite (the Dex bonus is at or below it) |
| **Base Atk** +1; **CMB** +3; **CMD** 15 | `"cmb": 3, "cmd": 15` |
| **CMB** +5 (+7 trip); **CMD** 17 (21 vs. trip) | `"cmb": 5, "cmb_vs": {"trip": 7}, "cmd": 17, "cmd_vs": {"trip": 21}` (maneuver names: bull-rush, dirty-trick, disarm, drag, grapple, overrun, reposition, steal, sunder, trip). Copy the stat block's numbers: the script doesn't add Improved/Greater feat bonuses itself, but it does read the feats for "no AoO" and the Greater effects |
| can't be tripped (oozes, legless or flying creatures) | `"maneuver_immune": ["trip"]` |
| **grab** (on an attack) | keep it in `rider`; the DM resolves it with `maneuver … grapple --grab` (+4, no AoO) |
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
| **Melee** rapier; **Ranged** composite longbow, holding the bow when the fight starts | `"wielding": ["composite longbow"]` (default: its first weapon). Attacks need the weapon in hand; drawing another is `wield`. Two-handed weapons and bows take both hands (`"hands": 2`, guessed from the name if left out); natural attacks (bite, claw, slam…) are always at hand (`"natural": true` where the name doesn't say), and so are supernatural or spell-like attacks like a ray (`"supernatural": true`; guessed for ranged touch attacks named bolt, ray, blast…). Better still, put a spell-like attack in `sla` with its effect. `"bab"`: drawing rides on a move with +1 or more (default) |
| **Gear** 20 arrows; 4 javelins | `"ammo": 20` on the bow, `"ammo": 4` on the javelin. The script counts shots and throws and refuses an empty one (a thrown weapon has to be picked up: a move action that provokes). Leave it out to not track it |
| longspear (reach) | `"reach": 10` on that attack |

- **Crit:** `crit` is the **lowest** number of the threat range (`/18–20` → 18), and `mult` the multiplier (`/×3` → 3). Leave them out for 20/×2.
- **Damage:** only dice and flat numbers. Extra damage like "plus 1d6 fire" goes in `rider`, as does poison, grab and trip.
- **Range increments aren't in the stat block.** Take them from the weapon table (`library/pf1e/items/` or the allowed sources), e.g. shortbow 60, longbow 100, light crossbow 80, javelin 30, dagger 10, sling 50.
- **Primary and secondary natural attacks:** the stat block already prints the right bonuses and damage, so copy them.
- **Which ability an attack uses** matters only when a condition changes Str or Dex. The defaults are Str for melee rolls and Dex for ranged rolls; add `"ability": "dex"` for a Weapon Finesse attack. Str on damage defaults to ×1 for melee and thrown and ×0 for other ranged attacks. Add `"str_damage": 1.5` for two-handed weapons or a sole natural attack, `0.5` for off-hand or secondary natural attacks, and `1` for composite bows.
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

**Spell-like abilities (Sp)** go in `sla`: they provoke like spells, can be used defensively (concentration), and spell resistance applies. Supernatural (Su) and extraordinary (Ex) abilities, such as channel energy, bardic performance or a breath weapon, go in `abilities` instead (`library/pf1e/rules/special-abilities.md`):

| Stat block | Profile |
|---|---|
| **Spell-Like Abilities** (CL 3rd; concentration +5) | one entry per ability, each with `"cl": 3` |
| At will—*detect magic* | `{"name": "detect magic", "per_day": "at will", "level": 0}` |
| 3/day—*darkness* | `{"name": "darkness", "per_day": 3, "level": 2}` |
| 1/day—*hold person* (DC 15) | `{"name": "hold person", "per_day": 1, "level": 2, "dc": 15}` |
| Constant—*detect evil* | `{"name": "detect evil", "per_day": "constant"}` |

Where the stat block lists the spell's level, put it in `level`, because the concentration DC depends on it.

**Spell effects come from the library.** List the spells; the script takes each one's effect from `library/pf1e/spells/<name>.md` (its ```spell-effect block, see that folder's README) and works it out at this entry's `cl` when the creature joins a fight. Most casters need **no** `effects` at all. `effects` holds only what's specific to this caster, merged on top:

| Situation | `effects` entry |
|---|---|
| a touch or ray spell (*ray of frost*, Small caster, BAB +0, Dex 16) | `"ray of frost": {"attack": 4}`: the touch attack bonus (ranged: BAB + Dex + size; melee: BAB + Str + size), rolled against touch AC before the effect lands |
| bloodline arcana or another fixed extra (+1 damage) | `"burning hands": {"dmg_bonus": 1}` |
| a printed DC that differs from `dc_base` + level (Spell Focus) | `"daze": {"dc": 13}` |
| a spell the library doesn't have yet | add it to the library instead (spells/README.md); a whole effect here works too, as a stopgap |
| an SLA | the same, as `"effect"` on the `sla` entry (usually nothing: the library has it) |

`profile check` resolves every listed spell and warns about the ones without effect data. Conditions and buffs use the names in `library/pf1e/conditions.json` (`blessed`, `frightened`, `evil eye (attack rolls)`, …); a custom one brings `cond_mods` (`{}` = tracked by name on purpose).


## Skills the script rolls
| Stat block | Profile |
|---|---|
| **Skills** Heal +5 | `"skills": {"heal": 5}`: first aid on a dying ally (DC 15). Untrained: the Wis modifier; with a healer's kit, +2 more |

## Sneak attack and special abilities
Each entry in `abilities` takes `"type": "su"` (default) or `"ex"`. Neither provokes, needs concentration or is subject to spell resistance.

| Stat block | Profile |
|---|---|
| **Special Attacks** sneak attack +2d6 | `"sneak_attack": "2d6"`. The script adds it when the target is flanked or denied its Dex (not against concealment; ranged only within 30 ft) |
| bardic performance 8 rounds/day (inspire courage +1) | `"abilities": {"inspire courage": {"action": "standard", "maintain": "free", "uses": 8, "kind": "buff", "allies": {"atk": 1, "dmg": 1}, "buff": "inspired (courage)", "buff_rounds": 1}}`. Inspire courage's +1 is a competence bonus on attack and weapon damage rolls, plus +1 on saves against charm and fear: note that part in `notes` |
| channel positive energy 4/day (1d6, DC 12) | `"channel": {"action": "standard", "uses": 4, "kind": "heal", "target": "area", "area": "burst 30", "center": "self", "heal": "1d6", "who": "allies"}` |
| breath weapon (15-ft. cone, 2d6 fire, Ref DC 13 half, usable every 1d4 rounds) | `"breath": {"action": "standard", "kind": "damage", "target": "area", "area": "cone 15", "save": "ref", "dc": 13, "half": true, "dmg": "2d6", "notes": "again after 1d4 rounds"}` |

`combat.py ability TOKEN "NAME"` uses one (`--target`, `--at` or `--toward` as the effect needs).

## Tactics (personality and morale)
The tactical options rank whole-turn plans by expected value. `tactics` adds this creature's preferences as points on top (about one point per point of expected damage: +3 is a clear preference, −3 a clear aversion). Plan kinds: `melee`, `ranged`, `spell` (offensive spells, SLAs and abilities), `buff`, `heal`, `defense` (total defense), `retreat` (withdraw).

| Creature | Tactics |
|---|---|
| a cowardly kobold sniper | `"tactics": {"weights": {"ranged": 2, "melee": -3}, "morale": {"hp": 0.5, "allies_down": 0.5, "weights": {"retreat": 6}, "note": "flees toward its warren"}}` |
| a berserker | `"tactics": {"weights": {"melee": 4, "defense": -4, "retreat": -6}}` |
| a devoted healer | `"tactics": {"weights": {"heal": 3, "buff": 2}, "morale": {"allies_down": 1, "weights": {"retreat": 4, "defense": 2}, "note": "surrenders when cornered"}}` |

Morale breaks at or below `hp` of its maximum HP, or when `allies_down` of its side is down (1 = all of them). Then its `weights` are added. An encounter can give a combatant its own `tactics` for that fight (it replaces the stat block's).

## Player characters
**Player characters** use their own schema, `combat-profile-pc.schema.json`, in the character sheet's block (template: `library/pf1e/character-sheet.md`). It requires only what the script uses for a PC:
- `init` (the modifier: the player rolls initiative, the script breaks ties with it)
- `max_hp` (current HP stays on the sheet's HP line)
- `ac`, `touch`, `ff` and `cmd` (what enemies roll against)
- `str`, `dex` and `con` (conditions, and death at −Con)
- `speed` and `size`
- `senses` (`{}` = normal vision) and `perception`
- `feats` (Combat Reflexes, Blind-Fight, Precise Shot, Improved maneuvers; `[]` if none)

Optional: `weapons` and `wielding` (what the PC carries and holds, so the script enforces drawing and knows when they threaten: `{"rapier": {"type": "melee"}, "shortbow": {"type": "ranged", "hands": 2}}`), `bab`, `max_dex`, `reach`, `uncanny_dodge`, `sneak_attack` (the script reminds when it applies), `ammo` (by attack name, e.g. `{"shortbow": 20, "javelin": 3}`: counted on attacks with that name; update the sheet after the fight), `cmd_vs`, DR, resistances and immunities. Attacks, spells, saves and CMB aren't needed, because the player rolls them. `combat.py add` refuses a PC without a passing block. The DM fills it from the sheet and asks the player for anything missing.

## A complete example
```combat-profile
{"kind": "creature", "init": 6, "hp": 6, "ac": 16, "touch": 13, "ff": 14, "cmb": 1, "cmd": 13,
 "saves": {"fort": 3, "ref": 2, "will": -1}, "speed": 30, "size": 1, "reach": 5,
 "con": 12, "dex": 15, "feats": ["Improved Initiative"],
 "attacks": {"short sword": {"bonus": 2, "damage": "1d4", "type": "melee", "crit": 19, "damage_type": "P"},
             "shortbow": {"bonus": 4, "damage": "1d4", "type": "ranged", "mult": 3, "range": 60, "damage_type": "P"}},
 "source": "Bestiary pg. 156"}
```
