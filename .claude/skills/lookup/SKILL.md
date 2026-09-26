---
name: lookup
description: Look up game reference material (rules, conditions, spells, monsters, items, feats, class features, setting lore) for the DM's own use. Delegates the research to the dm-researcher agent so searches stay hidden from the player and free of published-adventure spoilers. Use it before stating exact mechanics (formulas, uses per day, DCs, archetype replacements), whenever you'd hedge ("I believe", "correct me if I'm wrong"), and whenever you don't recognize a spell, feat, ability, item or creature. Don't ask the player to explain official content.
user-invocable: false
---

# Lookup

This is for **your own use as DM**. The player has their own references, and is watching the chat and the tool calls.

## When to look up
Don't rely on memory for PF1e details that are easy to get wrong. Look them up when:
- **You'd hedge.** Words like "I believe", "if I remember correctly", "correct me if I'm wrong" or "according to my calculation" mean it's time to look something up, not to ask the player.
- **You don't recognize it,** e.g. an uncommon spell, feat, archetype, trait or item. If it's official content, the allowed sources have it.
- **It's exact mechanics:** formulas, uses per day, rounds per day, DCs, scaling by level, prerequisites, or what an archetype replaces and how the replacement differs. Check these even when you feel sure, because they're the classic memory errors.

Common core rules you use constantly (e.g. how attacks of opportunity work) can come from memory, or from the quick references in `library/<system>/rules/`.

Ask the player only if the sources come up empty (homebrew, or a third-party source that isn't allowed), and say that you looked.

## Hidden by default: delegate
**Never call WebFetch or WebSearch from the main session.** A visible search for "drow assassin stat block" spoils the hidden assassin on the map, and web calls clutter the chat.

Delegate to the **dm-researcher** agent (wait for the result: `run_in_background: false`):
- **Description** (visible to the player): spoiler-free and generic, e.g. "Look up a creature", "Check a rule", "Research local lore".
- **Prompt:** the campaign slug, exactly what you need and why (e.g. "stat block for an assassin-type NPC around CR 4, humanoid, for an ambush"), and any constraints.
- The agent checks the library, searches only the allowed sources, filters out published-adventure spoilers (`library/general/table-rules/published-content.md`), saves the result to the library, and returns what you need.

**Use the result silently.** Don't paste it into the chat, and don't mention excluded content.

## Quick library check in the main session
You may read the library directly, without the agent, **only for things the players already know about**: a condition affecting them, their own spells, feats and gear, or general rules. That's fast and spoils nothing. Everything else goes through the agent: monsters, NPCs, items they haven't found, and lore.

## Folder map
The system comes from the campaign's `campaign.md` and defaults to `pf1e`.

| Topic | Folder |
|---|---|
| Rules, conditions, procedures | `library/<system>/rules/` |
| Spells | `library/<system>/spells/` |
| Monsters, NPC stat blocks | `library/<system>/bestiary/` or `library/<system>/npcs/` |
| Magic items, gear | `library/<system>/items/` |
| Feats, traits, class features, archetypes, races | `library/<system>/character-options/` |
| Random tables | `library/<system>/tables/` or `library/general/tables/` |
| Setting lore | `library/settings/<setting>/` |

Campaign house rules (`campaign.md`) and `library/<system>/house-rules/` override library entries (CLAUDE.md rule 7).

## Entry format
Used by the agent when it saves, one entry per file named `<kebab-case-name>.md`. Existing files are updated, not duplicated.

```markdown
# <Name>
- **Source:** <book + page if known> · <URL>
- **Publisher:** Paizo | <third-party publisher>
- **Published adventure:** none | <AP or module name> (spoiler)
- **Retrieved:** <YYYY-MM-DD>
- **Tags:** <type, e.g. spell · evocation · sorcerer/wizard 3>

<Condensed entry. Keep every mechanical detail exact: numbers, DCs, durations, ranges,
save types, prerequisites, and full stat blocks. Cut flavor text.>

## Notes
<Errata, source conflicts, common rulings, or house-rule interactions.>
```

- **Monsters:** the full stat block, including tactics and morale if given.
- **Rules:** one topic per file.
- **Lore:** update the relevant file in the setting folder, e.g. a region or deity file. Mark any paragraphs taken from an adventure with `[AP: <name>]`.

## If nothing is found
Make a sensible ruling, or use the generic alternative the agent suggests. Note it in the live log under "Rulings to check", and move on.

## Using it in play
If the player asks about a rule directly, answer in a sentence or two with a citation. For things the characters wouldn't know, such as monster details, share only what an in-game check reveals.
