# <Character Name>

- **Player:**
- **Race / Class / Level:**
- **Alignment / Deity:**
- **Size / Speed:** (include fly, swim, climb and burrow speeds with maneuverability)
- **Senses:** (darkvision, low-light vision, scent, …)
- **Languages:**

## Numbers
| Str | Dex | Con | Int | Wis | Cha |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

- **HP:** current / max
- **AC:** normal / touch / flat-footed
- **Saves:** Fort / Ref / Will
- **Initiative:**
- **CMB / CMD:**
- **Main attacks:** (to-hit, damage, crit range)

## Combat profile
Read by `scripts/combat.py` (`add C … --ref players/characters/<slug>.md`), which refuses to add a PC whose block doesn't pass `library/pf1e/combat-profile-pc.schema.json`. Keep it in sync with the numbers above, and update it on every level-up or gear change. The player rolls their own attacks, saves and spells, so only what enemies and conditions need is here:
- **senses:** `{}` for normal vision, else e.g. `{"low_light": true}` or `{"darkvision": 60}`.
- **max_dex:** only when the armor caps the Dex bonus. Current HP stays on the HP line above.
```combat-profile
{"kind": "pc", "init": 0, "max_hp": 1, "ac": 10, "touch": 10, "ff": 10, "cmd": 10,
 "str": 10, "dex": 10, "con": 10, "speed": 30, "size": 1, "senses": {}, "perception": 0,
 "feats": [], "uncanny_dodge": false}
```

## Hidden-roll skills
Total modifiers. Only the skills the DM might roll in secret.
- **Perception:**
- **Sense Motive:**
- **Knowledge (trained only):**
- **Other** (Survival, Disable Device, Linguistics, …):

## Permanent & situational modifiers
Always-on bonuses and penalties and their conditions. Examples: Elven Immunities (immune to magic sleep; +2 vs enchantment), Hardy (+2 vs poison, spells and spell-like abilities), Trap Sense, Evasion, Stonecunning, Defensive Training, a trait bonus to one save, spell resistance.
-

## Notable abilities
Things the character can do that shape play, briefly: spells known or prepared at a high level, class features, special gear. Give uses per day with the formula and a library link, e.g. `Archaeologist's Luck: N rounds/day ([formula], library/pf1e/character-options/…)`.
-

## Gear
(Not listed here: the interface shows the character's gear from `players/inventory.json`, kept by the `gear` tool. A new character's container: `gear container`, or `gear init`.)

## Backstory (player version)
Summary, or a link to the player's own text.

## Changelog
- <date>: added at level N
