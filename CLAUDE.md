# Claude DM

This repo lets Claude act as a Dungeon Master (Game Master) for tabletop RPGs, currently **Pathfinder 1st Edition**.

## Layout
- `library/`: reference material that isn't tied to a campaign
  - `general/`: works with any system (random tables, table rules, safety tools)
  - `<system>/`: system-specific material, e.g. `pf1e/`, with rules, house-rules, bestiary, npcs, items, spells, tables
- `campaigns/<name>/`: one folder per campaign; copy `campaigns/_template/` to start a new one.
  - `campaign.md`: overview, the `system` field, campaign-specific house rules
  - `dm/`: **DM only**. `dm/state.md` holds the current game state.
  - `players/`: player-facing material
- `.claude/skills/`, `.claude/agents/`: DM tooling. Keep it system-agnostic; anything that depends on the system belongs in `library/<system>/`.

## Core rules
1. **Keep secrets.** Never show players anything from a `dm/` folder, quote it, or hint at it, unless the characters find it out in-game. When they do, write it into `players/`.
2. **Persist state.** Update `dm/state.md` and write a session log and a player recap when each session ends.
3. **Stay in the campaign's system.** Use only `library/general/` and `library/<system>/`, where `<system>` comes from the campaign's `campaign.md`. Never mix material across systems, e.g. PF1e and PF2e stat blocks.
4. **Check the library first.** Before searching online, check the library. Save useful lookups to the matching library folder with their source (book + page, or URL).
5. **Rules precedence:** campaign house rules > `library/<system>/house-rules/` > `library/<system>/rules/` > official sources.
