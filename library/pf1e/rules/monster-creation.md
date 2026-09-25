# Monster Creation & Adaptation (PF1e)
Source: Bestiary, Monster Creation. See https://www.d20pfsrd.com/bestiary/rules-for-monsters/monster-creation/ (table verified 2026-09-25). Also relevant: Unchained, Simple Monster Creation (https://aonprd.com/Rules.aspx?ID=1997).

## Preferred order
Stop at the first option that works:
1. **Official stat block.** Use `lookup` and save it to `library/pf1e/bestiary/`.
2. **Official stat block plus official adjustments:** simple templates (advanced, giant, young, celestial/fiendish, …), class levels, or added Hit Dice. Look up the exact template rules when you apply one.
3. **Reskin / proxy:** a mechanically identical official creature with new flavor, and small changes such as damage type, movement mode or senses. Save it as `Reskin of <creature>` and list only the changes. Keep CR, HP, AC, attacks and DCs the same, unless a change clearly adds or removes power (e.g. adding flight). In that case, re-check against the table below.
4. **Full homebrew:** follow the process below and check the result against the table.

Save homebrew and reskinned stat blocks to `library/pf1e/bestiary/` with `Publisher: Homebrew (<campaign>)`.

## Monster statistics by CR
These are the targets for homebrew and the sanity check for any adjusted stat block. Most monsters exceed the target in one area (often damage) and fall short in one or two others.

| CR | HP | AC | High Atk | Low Atk | Dmg High | Dmg Low | Primary DC | Secondary DC | Good Save | Poor Save |
|---|---|---|---|---|---|---|---|---|---|---|
| 1/2 | 10 | 11 | 1 | 0 | 4 | 3 | 11 | 8 | 3 | 0 |
| 1 | 15 | 12 | 2 | 1 | 7 | 5 | 12 | 9 | 4 | 1 |
| 2 | 20 | 14 | 4 | 3 | 10 | 7 | 13 | 9 | 5 | 1 |
| 3 | 30 | 15 | 6 | 4 | 13 | 9 | 14 | 10 | 6 | 2 |
| 4 | 40 | 17 | 8 | 6 | 16 | 12 | 15 | 10 | 7 | 3 |
| 5 | 55 | 18 | 10 | 7 | 20 | 15 | 15 | 11 | 8 | 4 |
| 6 | 70 | 19 | 12 | 8 | 25 | 18 | 16 | 11 | 9 | 5 |
| 7 | 85 | 20 | 13 | 10 | 30 | 22 | 17 | 12 | 10 | 6 |
| 8 | 100 | 21 | 15 | 11 | 35 | 26 | 18 | 12 | 11 | 7 |
| 9 | 115 | 23 | 17 | 12 | 40 | 30 | 18 | 13 | 12 | 8 |
| 10 | 130 | 24 | 18 | 13 | 45 | 33 | 19 | 13 | 13 | 9 |
| 11 | 145 | 25 | 19 | 14 | 50 | 37 | 20 | 14 | 14 | 10 |
| 12 | 160 | 27 | 21 | 15 | 55 | 41 | 21 | 15 | 15 | 11 |
| 13 | 180 | 28 | 22 | 16 | 60 | 45 | 21 | 15 | 16 | 12 |
| 14 | 200 | 29 | 23 | 17 | 65 | 48 | 22 | 16 | 17 | 12 |
| 15 | 220 | 30 | 24 | 18 | 70 | 52 | 23 | 16 | 18 | 13 |
| 16 | 240 | 31 | 26 | 19 | 80 | 60 | 24 | 17 | 19 | 14 |
| 17 | 270 | 32 | 27 | 20 | 90 | 67 | 24 | 18 | 20 | 15 |
| 18 | 300 | 33 | 28 | 21 | 100 | 75 | 25 | 18 | 20 | 16 |
| 19 | 330 | 34 | 29 | 22 | 110 | 82 | 26 | 19 | 21 | 16 |
| 20 | 370 | 36 | 30 | 23 | 120 | 90 | 27 | 20 | 22 | 17 |

- **High / Low Attack:** the total attack bonus. Use High for creatures that rely on weapons or natural attacks, and Low for others.
- **Damage:** the average total damage if all attacks hit.
- **Primary / Secondary DC:** save DCs for the creature's main and lesser special abilities.

## Full homebrew process
1. **Concept and role:** CR, type, size, combat style (brute, skirmisher, caster, controller), and 1–2 comparable official monsters to borrow from.
2. **Targets:** take them from the table above.
3. **Hit Dice** by type and CR (see the Bestiary's Creature Hit Dice table), then **size**, which sets base ability scores and natural attack damage.
4. **Ability scores** tuned to reach the targets.
5. **Skills and feats** by type and HD.
6. **Combat statistics:** AC, attacks, damage and saves. Check each against the targets, and justify any big deviation with a compensating weakness.
7. **Special abilities:** prefer the Universal Monster Rules, with DCs from the table.
8. **Final check:** does it fit the encounter budget (`encounter-building.md`), and does it play fair against the PCs' "abilities to plan around"?

For a quick unexpected encounter, Unchained's Simple Monster Creation (link above) is a faster alternative.
