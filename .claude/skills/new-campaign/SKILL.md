---
name: new-campaign
description: Start a new tabletop RPG campaign, adventure or one-shot. Runs a session-zero interview (scope, setting, theme, style, starting level, mechanics, boundaries), creates the campaign folder from campaigns/_template, and prepares the setting, campaign plan and opening adventure. Use when the user wants to start, create or set up a new campaign or adventure.
argument-hint: "[campaign name or pitch]"
---

# New Campaign

You are the DM running session zero. The goal is to agree with the player(s) on what game you're playing, then build a campaign folder that is ready for session 1.

The system is **pf1e** unless the user asks for another. Use `library/pf1e/` for rules.

## Step 1: Interview

Follow [interview.md](interview.md).
- Ask in rounds. Don't send the whole questionnaire at once.
- Use the AskUserQuestion tool when it is available (up to 4 questions per call, 2–4 options each; the user can always answer "Other"). Put the option you recommend first.
- Skip anything already answered in `$ARGUMENTS` or earlier in the conversation.
- If the user says "you decide" or "surprise me", pick something that fits the other answers and note that you chose it.
- **Quick mode:** if the user wants to get playing fast, ask only scope, setting, theme, starting level and "name a few works you love", and use the defaults in interview.md for the rest.

When the interview is done, show a compact summary of all choices. Ask for corrections before you create any files.

## Step 2: Setting

Settings live in `library/settings/<slug>/` and can be reused across campaigns. See `library/settings/README.md`.

- **Golarion (default):** Use canonical lore. Default era is about 4707 AR unless the user chose another. Make sure the starting region has a file in `library/settings/golarion/regions/`. If you're unsure of a detail, check the library, then look it up using the sites in `library/settings/golarion/sources.md`, and save what you learn with its source.
- **Claude-made setting:** Build only as much as the scope needs. A one-shot needs a town and its surroundings. An epic needs a continent overview, major powers and a pantheon. PF1e clerics need deities with domains, so either define domains or reskin Golarion deities. Write `overview.md`, then add files as needed.
- **Homebrew from the user's material:** Ask for files, paths, URLs or pasted text. Save the raw material to `source/`, then write `overview.md`. List any gaps and contradictions. Ask the user about the important ones, fill minor ones yourself, and mark them `[Claude invention]`.

## Step 3: Create the campaign

1. Pick a kebab-case slug. If there's no name yet, propose three. Never overwrite an existing campaign folder.
2. Run `cp -R campaigns/_template campaigns/<slug>`.
3. Fill in these files:
   - `campaign.md`: name, system, setting, status `planning`, starting level, player-safe pitch, campaign-specific house rules
   - `players/session-zero.md`: every choice the table agreed on
   - `players/character-creation.md`: build rules, plus the roles and skills that will be useful and hooks for backstories
   - `players/setting-primer.md`: one page of common knowledge about the world and the starting region
   - `dm/campaign-plan.md`: premise, antagonists and what they do if unopposed, arcs, themes, hooks
   - `dm/adventures/<first-adventure>/`: the opening adventure, detailed enough to run session 1
   - `dm/npcs/` and `dm/locations/`: the key people and places for the opening
   - `dm/state.md`: the starting situation
4. Match your prep to the structure the table chose:
   - **Sandbox:** factions with goals, locations, rumors and clocks rather than plot.
   - **Story-driven:** arcs and key beats.
   - **Either way:** plan in detail only up to the first adventure. Keep later arcs loose, since the players will change them.
5. For variant rules and house rules:
   - Campaign-only rules go in `campaign.md`.
   - Rules the user wants at every table go in `library/pf1e/house-rules/`.
   - For an official or third-party variant system, check whether `library/pf1e/rules/` already has a summary with its source. If not, write one.

## Step 4: Hand off

The user is probably a player too, so **don't reveal what's in `dm/`**. Say that the secret campaign plan and the opening adventure are ready, but share no details. Only share them if the user explicitly asks, and warn about spoilers first.

Summarize the files meant for players, then offer character creation as the next step.
