---
name: add-character
description: Record a player character the player built themselves. Collects the key numbers, hidden-roll modifiers and backstory preferences, and writes a player-facing sheet plus private DM notes. Also use to update a character after a level-up or change. Does not build characters.
argument-hint: "[campaign] [character name]"
---

# Add Character

The player builds their character themselves. Your job is to record what a DM needs to run the game. **Don't build, optimize or second-guess the character.** Only mention a rules problem if something is clearly illegal under the campaign's `players/character-creation.md`.

Work out which campaign this is for from `$ARGUMENTS`, or ask; if there is only one campaign, use it. Read the campaign's `campaign.md`, `players/session-zero.md` and `players/character-creation.md` first.

If the character already has a file, this is an **update**. Ask what changed, e.g. a level-up, a new item or an ability change. Update both files and add a changelog line.

## Step 1: The numbers

The player can paste their sheet, point you to a file (PDF, image or export), or answer questions. From a full sheet, pull out only what the template needs. Otherwise ask for these in one compact message:
- race, class and level, alignment and deity
- ability scores, HP, AC (normal / touch / flat-footed), saves, initiative, CMB / CMD, speed(s), senses
- main attacks
- **hidden-roll skills:** Perception, Sense Motive, trained Knowledges, and any other skill you might roll in secret
- **permanent and situational modifiers:** always-on bonuses and penalties from race, traits, class features, feats or items. Explain why you're asking: these matter for rolls you make secretly. Give examples such as Elven Immunities (+2 vs enchantment) or Hardy.
- **notable abilities:** anything that shapes play, e.g. a fly speed, invisibility, at-will detection, strong social skills, teleportation, summons

Don't ask for every skill, feat or spell.

## Step 2: Backstory

Ask for the backstory (full text, summary, or "none yet"). Then ask these questions, using AskUserQuestion when it's available:

1. **Centrality:** how central is the character's backstory to the campaign?
   - Woven in: backstory threads become side arcs and personal stakes (Recommended)
   - Central: the campaign revolves around them, e.g. a lost throne, a chosen one, a personal quest
   - Light touch: occasional hooks and cameos
   - Outsider: arrives with no ties to the setting
   In a multi-player game, point out that other PCs need spotlight too.
2. **Blanks for the DM:** Which parts would they like you to invent? Examples: unknown parents, lost memories, a mysterious mentor, why their village burned. Should those be **revealed to them now** (written in the player sheet) or **kept as a surprise** (DM notes only, uncovered through play)?
3. **Backstory as leverage:** may NPCs from the backstory be threatened, turned or harmed?
   - Yes
   - Ask first
   - No
   Is anything off-limits?

Respect the campaign's lines and veils in everything you invent.

## Step 3: Write the files

The file slug is the character's name in kebab-case.

- **`players/characters/<slug>.md`:** fill in `library/<system>/templates/character-sheet.md`. Include only what the player is allowed to see.
- **`dm/characters/<slug>.md`:** fill in [dm-notes-template.md](dm-notes-template.md):
  - backstory settings, hooks, and any surprise blanks you filled in
  - **Abilities to plan around:** assess the character quietly against the campaign's challenge settings. The harsher the challenge settings, the more carefully you plan around strong abilities. Examples:
    - a permanent fly speed makes melee-only enemies trivial, so answers include ranged foes, flying foes, tight interiors and bad weather
    - at-will *detect evil* spoils many mysteries
    Plan to challenge these abilities sometimes, not every time. Players should get to enjoy what they built.
- **Continuity:** backstory facts the player wrote are `[locked S00]`. Blanks you fill in are `[flex]` until they're revealed. Check your inventions against `dm/timeline.md` and `dm/threads.md`, then add backstory events to the timeline. Register hooks in `dm/threads.md`: as a character thread (respecting the side-thread budget) or as dormant seeds, depending on centrality.
- Weave the character into `dm/campaign-plan.md` and the current adventure, with depth matching the centrality they chose.
  - Central or woven in: add real arcs and hooks.
  - Light touch: seed a few hooks.
  - Outsider: give a reason to get involved.

## Step 4: Hand off

- Show the player sheet so the player can check the numbers.
- About the DM notes, say only that they've been noted, e.g. "I've noted a few hooks from your backstory." Never reveal the ability assessment or any surprises.
- Remind the player to tell you when anything changes, e.g. a level-up, a new item or an HP change, so the sheet stays current.
