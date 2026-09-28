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
Read by `scripts/combat.py` (`add C … --ref players/characters/<slug>.md`). Keep it in sync with the numbers above, and update it on every level-up or gear change. The player rolls their own attacks, so only the defensive numbers are needed:
```combat-profile
{"kind": "pc", "init": 0, "hp": 1, "max_hp": 1, "ac": 0, "touch": 0, "ff": 0, "cmd": 0,
 "saves": {"fort": 0, "ref": 0, "will": 0}, "con": 10, "dex": 10, "speed": 30, "size": 1,
 "reach": 5, "uncanny_dodge": false, "feats": []}
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

## Backstory (player version)
Summary, or a link to the player's own text.

## Changelog
- <date>: added at level N
