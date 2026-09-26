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

## Step 2: Create the folder
1. Pick a kebab-case slug. If there's no name yet, propose three. Never overwrite an existing campaign folder.
2. Run `cp -R campaigns/_template campaigns/<slug>`.
3. Write the player-facing basics yourself. They came from the interview, so they're no spoilers:
   - `players/session-zero.md`: every choice the table agreed on, including "Published adventures"
   - `campaign.md`: name, system, setting, status `planning` and starting level
   - Update `library/general/player-profile.md` with any published adventures the player mentioned.
4. **Homebrew setting from the user's material:** collect the files, paths, URLs or pasted text now, and save them raw to `library/settings/<setting-slug>/source/`.

## Step 3: Build behind the screen
**Everything else is secret, including the setting research, so delegate it.** Web searches, lore pages and the campaign plan would all spoil the game if they appeared in the chat.

Tell the player "I'll build the campaign behind the screen. This takes a moment." Then delegate to the **dm-scribe** agent (wait for the result: `run_in_background: false`):
- **Description:** "Build the campaign"
- **Prompt:** "campaign `<slug>`: build the campaign following `.claude/skills/new-campaign/build-campaign.md`", plus anything from the interview that isn't captured in session zero.

When it reports back:
- **Homebrew questions:** ask the player, then send the answers back to the same agent (SendMessage), so it can finish.
- Relay only its spoiler-free summary.

## Step 4: Hand off

The user is probably a player too, so **don't reveal what's in `dm/`**. Say that the secret campaign plan and the opening adventure are ready, but share no details. Only share them if the user explicitly asks, and warn about spoilers first.

Summarize the files meant for players: pitch, setting primer and character creation rules. Read and show them. Then say that the next step is for the player to build their character using `players/character-creation.md`, and to register it with `/add-character` once it's done.
