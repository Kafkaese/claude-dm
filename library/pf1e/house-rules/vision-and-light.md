# Vision and Light (house rule)
**Homebrew, on purpose.** This table plays light and vision with simpler, more intuitive rules than the Core Rulebook. `scripts/vision.py` and `scripts/combat.py` implement exactly this page. When the CRB text (`library/pf1e/rules/vision-and-light.md`) says something different, **this page wins** (house rules > rules). It isn't a script bug, so don't "fix" it, rule against it or ask the player about it.

## The idea
What counts is **what you're looking at, not where you stand.** Light doesn't blind the creature standing in the dark. It hides the creature standing in the dark from those who can't see there.

## How it works
1. **Seeing a creature:** judged from the **target's best-lit square** and the viewer's senses (darkvision, low-light vision, …). A creature in the light is seen clearly from the dark.
   - Normal or bright light: no concealment.
   - Dim light: 20% concealment.
   - Darkness: 50% (total concealment). Darkvision within its range sees there as in normal light.
   - No line of sight at all also counts as 50%.
2. **Not seeing your attacker** (it's in darkness you can't see into, or invisible): against that attacker only, you lose your Dex bonus to AC. If it's darkness, you also take −2 AC.
   - This is per attacker. The CRB instead makes a creature standing in darkness "effectively blinded" against everyone.
   - **Uncanny dodge** keeps the Dex bonus against an unseen attacker, as it does against an invisible one. The −2 still applies.
3. **Attacking a creature you can't see:** 50% miss chance, and you guess the square. You can't make attacks of opportunity against it. Sneak attack doesn't work through any concealment.
4. **Low-light vision** doubles the radii of light *sources* only. Ambient dim light, like moonlight, stays dim.
5. **Darkness spells** switch off nonmagical light in their area. Magical light only shines there if its spell level is higher (the Paizo blog/FAQ procedure).
6. **Light sensitivity** applies in any bright light, not only sunlight and *daylight*.
7. **Walls block light:** a source lights a square only with a clear line to it.

## What creatures know
When a creature picks its moves (tactical options, turn plans, hiding spots), it assumes its **opponents have normal vision**. It knows its own side's senses.
- An opponent's darkvision or low-light vision counts once that creature gives it away by attacking or targeting something it could only perceive that way. The script then marks it.
- This only affects decisions. The rule math always uses the real senses.

## Changelog
- 2026-10-02: written down as an explicit house rule, from the table rulings of 2026-09-29 and how the script works. Uncanny dodge against unseen attackers and presumed senses added.
