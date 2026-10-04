# Spell resistance at the table (house rule)
How `scripts/combat.py` plays spell resistance (rules: `library/pf1e/rules/spell-resistance.md`, CRB pg. 217). Two rulings where the rulebook is silent or too fiddly for the script. **This page wins** over the rules text.

- **Rays and touch spells:** the touch attack is rolled first; only a hit leads to the caster level check. (The CRB gives no order.)
- **Harmless spells on allies:** an ally lowers its spell resistance for a harmless spell from a friend without spending its standard action. (By the rules, lowering SR is a standard action on its own turn.)
- **Not automated:** lowering SR against enemies, dispelling, and antimagic fields (they suppress Sp and Su abilities, not Ex). The DM applies these by hand.

## Changelog
- 2026-10-04: written with the spell resistance automation.
