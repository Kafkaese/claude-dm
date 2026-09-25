# Integrate a Character (spec for dm-scribe)

The player sheet `players/characters/<slug>.md` is written, and the caller gave you the backstory answers. Follow `CLAUDE.md`, `continuity.md` and `published-content.md`.

1. **`dm/characters/<slug>.md`:** fill in `.claude/skills/add-character/dm-notes-template.md`:
   - **Backstory settings:** centrality, blanks, revealed or surprise, leverage, and off-limits topics.
   - **Blanks:** invent the ones the player asked for, consistent with the setting (research lore if needed), the timeline and the campaign's lines and veils. Surprises stay in the DM notes. Blanks the player wanted **revealed** also go into the player sheet's backstory section.
   - **Hooks** from the backstory.
   - **Abilities to plan around:** assess the character quietly against the campaign's challenge settings. The harsher the settings, the more carefully you plan around strong abilities. Examples:
     - a permanent fly speed makes melee-only enemies trivial, so answers include ranged foes, flying foes, tight interiors and bad weather
     - at-will *detect evil* spoils many mysteries
     Plan to challenge these sometimes, not every time. The player should enjoy what they built.
2. **Continuity:** backstory facts the player wrote are `[locked S00]`. Your inventions are `[flex]` until they're revealed (revealed-now blanks are `[locked S00]`). Check them against `dm/timeline.md` and `dm/threads.md`, then add backstory events to the timeline. Register hooks in `dm/threads.md`, either as a character thread (respecting the side-thread budget) or as dormant seeds, depending on centrality.
3. **Weave the character in:** update `dm/campaign-plan.md` and the current adventure, with depth matching the centrality:
   - **Central or woven in:** real arcs and hooks
   - **Light touch:** a few seeded hooks
   - **Outsider:** a reason to get involved
4. **Report,** spoiler-free: e.g. "Added DM notes, 3 hooks registered (1 thread, 2 seeds), 2 blanks filled (1 revealed in the sheet)."
