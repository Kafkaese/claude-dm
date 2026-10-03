# Terrain on the battle map (house rule)
How `scripts/combat.py` plays terrain, square by square. It follows the Core Rulebook's Environment chapter (`library/pf1e/rules/terrain.md`) where that gives numbers. Where the rulebook is silent (pillars, boulders, furniture, fences) or too fiddly for a grid, these are the table's rulings. **This page wins** over the rules text, so don't "correct" the script against it.

| Map | Terrain | Movement (squares) | Effect |
|---|---|---|---|
| `.` | floor, ground, road | 1 | none |
| `T` | tree | 1 | **partial cover** for whoever stands in it: +2 AC (CRB pg. 425) |
| `"` | light undergrowth, tall grass, crops | 2 | **20% concealment** for whoever stands in it; Stealth possible |
| `&` | heavy undergrowth, reeds | 4 | **30% concealment**; no running or charging |
| `Y` | tree in light undergrowth | 2 | partial cover and 20% concealment |
| `O` | massive tree, boulder, pillar, stalagmite | impassable | **blocks line of sight and effect** like a wall; cover behind it |
| `-` | low wall, fence, fallen log, hedgerow, crates, bar counter | 3 (crossing it: +2) | **cover** (+4 AC) to a creature within 30 ft beyond it, unless the attacker is closer to it than the target |
| `m` | furniture (tables, benches, beds) | 3 | hampers movement only |
| `^` | difficult: dense rubble, cave floor, steep uphill | 2 | none |
| `~` | shallow water, bog | 2 | none |
| `W` | deep water | impassable on foot | doesn't block sight; swimming is the DM's call |
| `#` | wall | impassable | blocks line of sight |
| `_` | pit, chasm | impassable | doesn't block sight |

**Simplifications**
- **Concealment from vegetation** counts for the square the target stands in, its whole space for a larger creature. It doesn't count for vegetation the line merely passes through. It doesn't stack with dim light or darkness: the higher miss chance counts. Darkvision doesn't see through leaves.
- **Partial cover** from a tree applies to AC only. The +1 Reflex bonus isn't automated.
- **Diagonal moves** into costly terrain cost 1.5× the square's cost, rounded down: difficult 3, a low wall 4, heavy undergrowth 6.
- **Not modelled:**
  - slopes (+1 melee from higher ground, uphill cost)
  - canopies
  - swimming and the cover a creature gets from being in deep water
  - Acrobatics DCs in undergrowth

  The DM applies these by hand when they matter.

**Battle maps.** Every fight gets a map that fits where it happens: a prepared one, or one generated with `combat_map` (forest-road, forest, clearing, field, river, village, tavern, cave, ruins, camp, swamp). A blank grid is only for a place that really is featureless.

## Changelog
- 2026-10-03: written with the terrain types and the map generator; rulings for pillars, boulders, furniture and fences per the rules check in `library/pf1e/rules/terrain.md`.
