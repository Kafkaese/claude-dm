---
name: lookup
description: Look up game reference material (rules, conditions, spells, monsters, items, feats, class features, setting lore) for the DM's own use. Checks the local library first, then only the allowed web sources, and saves what it finds to the library. Use whenever you need a rule, stat block or lore detail you're not certain of.
user-invocable: false
---

# Lookup

This is for **your own use as DM**. The player has their own references. Look things up quietly, then use the result in play. Don't paste entries into the chat.

Use spoiler-free tool descriptions, e.g. "Checking the library" or "Looking up a creature", never "Looking up the vampire the mayor secretly is".

## Step 1: Pick the system & folder
The system comes from the campaign's `campaign.md`, defaulting to `pf1e`. Map the topic to a folder:

| Topic | Folder |
|---|---|
| Rules, conditions, procedures | `library/<system>/rules/` |
| Spells | `library/<system>/spells/` |
| Monsters, NPC stat blocks | `library/<system>/bestiary/` or `library/<system>/npcs/` |
| Magic items, gear | `library/<system>/items/` |
| Feats, traits, class features, archetypes, races | `library/<system>/character-options/` |
| Random tables | `library/<system>/tables/` or `library/general/tables/` |
| Setting lore | `library/settings/<setting>/` |

## Step 2: Check the library first
- Search with Glob and Grep. Try the kebab-case file name, then grep for the name and its synonyms.
- **Always check for overrides** as well: campaign house rules in `campaign.md`, then `library/<system>/house-rules/`. They take precedence over what you find (CLAUDE.md rule 7).
- If the entry exists and covers what you need, use it and stop.

## Step 3: Search the web
Only do this if the library doesn't have the entry, or has only part of it.
- Use only the domains listed in `library/<system>/sources.md` (rules) or `library/settings/<setting>/sources.md` (lore). Always set `allowed_domains` on WebSearch; a hook blocks everything else.
- Follow the priorities and conflict rules in `sources.md`, e.g. on d20pfsrd, check whether content is Paizo or third-party.
- **Third-party content:** if the campaign's allowed sources (in `players/session-zero.md`) don't include that publisher, you can still save it, but don't use it in this campaign.
- **Lore:** check that it fits the campaign's era. For PF1e Golarion, events after about 4719 AR belong to PF2e.
- If you can't find it, make a sensible ruling, note it in the live log as "Rulings to check", and move on.

## Step 4: Save it
Save one entry per file, named `<kebab-case-name>.md`. If the file already exists, update it instead of creating a duplicate.

```markdown
# <Name>
- **Source:** <book + page if known> · <URL>
- **Publisher:** Paizo | <third-party publisher>
- **Retrieved:** <YYYY-MM-DD>
- **Tags:** <type, e.g. spell · evocation · sorcerer/wizard 3>

<Condensed entry. Keep every mechanical detail exact: numbers, DCs, durations, ranges,
save types, prerequisites, and full stat blocks. Cut flavor text.>

## Notes
<Errata, source conflicts, common rulings, or house-rule interactions.>
```

- **Monsters:** save the full stat block, including tactics and morale if given.
- **Rules:** save one topic per file.
- **Lore:** update the relevant file in the setting folder, e.g. a region or deity file, rather than creating one file per fact.

## Step 5: Use it
Apply it in play. If the player asks about a rule directly, answer in a sentence or two with a citation. For things the characters wouldn't know, such as monster details, share only what an in-game check reveals.
