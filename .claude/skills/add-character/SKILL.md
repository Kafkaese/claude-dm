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

## Step 3: Verify the character's abilities
Before writing anything, verify everything that isn't basic core material:
- class features from archetypes, and what they replace
- uncommon or unfamiliar spells, feats and traits
- special items
- anything that has a formula for uses per day, rounds per day, DCs or scaling

Make **one batched** call to the **dm-researcher** agent (wait for the result: `run_in_background: false`):
- **Description:** "Verify character abilities"
- **Prompt:** the campaign slug, the character's class, level and ability scores, and the list of items to check. Ask for the exact rules text, the formulas with the character's actual values worked out, and the library paths.

The character's own abilities aren't spoilers, so you can use the results openly.
- **Numbers the player gave that differ from the rules:** point out the difference and cite the source, e.g. "Archaeologist's Luck: by the rules it's X rounds per day (source), your sheet says Y. Which should I use?" Their sheet may include a feat or item you don't know about.
- **Things the sources don't have** (homebrew, or a third-party source that isn't allowed): ask the player for the text.

Never write "from my calculation, correct me if I'm wrong" for official content. Verify it instead.

## Step 4: Write the player sheet
The file slug is the character's name in kebab-case.

**`players/characters/<slug>.md`:** fill in `library/<system>/character-sheet.md`. Include only what the player is allowed to see. **Fill in its `combat-profile` block** from the same numbers (current and max HP, AC, touch, flat-footed, CMD, saves, Con and Dex scores, init, speed, reach, uncanny dodge, and relevant feats like Combat Reflexes). `combat.py` reads it, so it must match the sheet. On an update (level-up, new gear), update the block too. If the player wanted DM-filled blanks **revealed now**, leave them out for the moment: the scribe adds them (step 5).

## Step 5: DM notes behind the screen
Everything else is secret: inventing blanks, assessing abilities, and weaving the character into the plot. It may also need lore research. Delegate it to the **dm-scribe** agent (wait for the result: `run_in_background: false`):
- **Description:** "Weave the character into the campaign"
- **Prompt:** "campaign `<slug>`: integrate character `<slug>` following `.claude/skills/add-character/integrate-character.md`". Add the backstory answers from step 2 and the verified abilities from step 3: centrality, blanks and whether they're revealed or a surprise, leverage, and off-limits topics.

Relay only its spoiler-free summary. If blanks were meant to be revealed, the scribe has written them into the player sheet; read that part and show it.

## Step 6: Hand off

- Show the player sheet so the player can check the numbers.
- About the DM notes, say only that they've been noted, e.g. "I've noted a few hooks from your backstory." Never reveal the ability assessment or any surprises.
- Remind the player to tell you when anything changes, e.g. a level-up, a new item or an HP change, so the sheet stays current.
