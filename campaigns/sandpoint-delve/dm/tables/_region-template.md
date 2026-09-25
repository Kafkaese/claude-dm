# <Region> Events (DM ONLY)
Roll with `python3 scripts/roll.py -c <campaign> -H --table campaigns/<campaign>/dm/tables/<region>.md`.
The first column is the d% range. The ranges must cover 1–100 without gaps.

- **Region modifier:** ±N% (safe roads −10, wilderness +10, hostile +20)
- **Time of day matters:** yes / no. If yes, reinterpret night results.

| d% | Type | Event |
|---|---|---|
| 1–20 | Threat | <creature or hazard, CR, stat pointer> |
| 21–35 | Social | <travelers, merchants, pilgrims: flavor, maybe a rumor> |
| 36–50 | Environment | <weather, terrain obstacle, a strange sight> |
| 51–65 | Omen | <foreshadowing tied to a thread (T0N)> |
| 66–80 | Faction | <agents of a faction in world.md, doing what their agenda says> |
| 81–90 | Clue carrier | <delivers one of the floating clues in threads.md; if none are left, reroll> |
| 91–100 | Special | <a memorable one-off tied to the region's lore> |
