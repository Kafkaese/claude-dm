# Preparing Combat

Building a fight: where the numbers come from, and how to keep it fair for a solo character. For prep (the scribe, `/new-campaign`) and for a fight that comes up unprepared at the table. Running the fight is `combat.md`.

## Stat blocks
Always use real stat blocks, never numbers made up in the moment. Stop at the first option that works:
1. **Official stat block,** found with `lookup`. It delegates to the `dm-researcher` agent, so the player never sees which creature you looked up. Skip unique creatures and named NPCs from published adventures (`published-content.md`).
2. **Official stat block plus official adjustments:** templates, class levels, extra Hit Dice.
3. **Reskin / proxy:** a mechanically identical official creature with new flavor. For example, a flying seahorse is a giant eagle with bludgeoning damage and a swim speed.
4. **Homebrew,** built and checked against the system's monster creation guidelines (for PF1e: `library/pf1e/rules/monster-creation.md`).

For an **unexpected fight,** take a moment and prefer options 1–3; they're fast and balanced. Save every stat block you use to the library, so the next fight is faster. Size encounters with `library/<system>/rules/encounter-building.md`.

**Combat profiles:** every combatant needs a ` ```combat-profile ` block. Creatures: in the stat block, following `library/<system>/combat-profile-guide.md` and `combat-profile.schema.json`. If a stat block has none yet, add one before the fight, taken exactly from the stat block, and check it with `combat.py profile check <file>`. PCs: in the character sheet, following `combat-profile-pc.schema.json`. `add` refuses a PC whose block is incomplete; fill in what the sheet shows and ask the player for the rest.

## Morale: fun first
Enemies flee **late**. A fight where they run as soon as they're bloodied, or once half their friends are down, is over too early and too easily, and turns into a chase. Fun beats realism here:
- **Most enemies fight on** until they're nearly down or nearly alone. Give a combatant `morale` only when it has a reason to break (a hireling, a coward, a beast that wants to live). Fanatics, guardians and the cornered get none.
- **The floor, enforced by the script:** morale breaks at **15% of its HP** at the earliest, or when **¾ of its side** is down, and adds at most **+4** to a plan kind (a tilt toward retreating, not an order). Lower `hp` and higher `allies_down` are fine; anything earlier is held to the floor, and the checks warn about it.
- **Story triggers stay yours:** "they surrender when the boss falls" is a fine exit ramp in the encounter's prose. Use it for the decisive moment, not as a way to end every fight after the first kill.
- **Leaving takes effort:** fleeing the battlefield is a full-round action from the map edge, not while threatened (`library/<system>/house-rules/`, e.g. pf1e `fleeing.md`), so a broken enemy first has to get there.

## Solo and small parties
Balance is the hardest part of solo play, and challenge ratings underestimate how dangerous enemies are to a lone character. Use the system's solo guideline (for PF1e: `library/pf1e/house-rules/solo-play.md`), plus these principles:
- **Every fight either has an ally or is easy.** Give the PC help (a companion, a temporary ally like a turned henchman, a guard who joins in, a summoned creature, or terrain that works like an ally) or keep the encounter at the easy end of the scale. A challenging or hard solo fight without any help is only for a climax, and only if session zero's lethality allows it.
- **Build for the worst plausible case,** e.g. an ally who might not join, or reinforcements who might arrive.
- **Plan an exit ramp for every serious fight:** morale, surrender, bargaining, escape routes, or capture instead of death. Know it before the fight starts, not only once the PC is dying.
- **Spread the threat across rounds:** waves, enemies at a distance, a boss who talks before fighting. That beats everything happening at once.
- **Companions:** a companion played by the player takes PC turns (with its own "end turn"). One played by the DM gets its own steps like the other non-PC actors. It acts in character with its own judgment, not as a perfect optimizer, and the player can give it simple instructions like "stay back and heal".
- **Listen to feedback.** If stars & wishes say fights feel too hard (or too easy), adjust the campaign's effective APL in session zero, and tell the scribe.
