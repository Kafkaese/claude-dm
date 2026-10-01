---
name: start-session
description: Start or resume a game session in a campaign. Loads the campaign state, checks prep, gives a player-safe recap and sets the opening scene. Use when the player wants to play, continue, or start the next session.
argument-hint: "[campaign]"
---

# Start Session

## Step 1: Pick the campaign
Use `$ARGUMENTS` if given. Otherwise use the only campaign whose `campaign.md` has status `active` or `planning`, or ask. If there's no campaign yet, suggest `/new-campaign`. If `players/characters/` is empty, suggest `/add-character` first.

Session number: `NN` = "Sessions played" in `campaign.md` + 1, zero-padded to two digits. If `dm/session-log/session-NN.md` already exists, this is a **resume** of an interrupted session. Continue that log and skip ahead to Step 4.

## Step 2: Load context
**Read these yourself.** They're rules and player-facing files, so nothing here is a spoiler:
- `library/general/table-rules/safety-tools.md`, `communication.md`, `running-the-game.md` (especially "Behind the screen"), `combat.md`, `continuity.md` and `living-world.md`
- `campaign.md`, `players/session-zero.md`, `players/party.md`, `players/characters/*`, and the latest `players/recaps/` file
- `library/<system>/rules/` quick references relevant to play

**Don't open `dm/` files in the main session** in the Claude Code UI: their names and contents are spoilers. **In `play.py` mode** (tool calls are hidden), skip the gm-screen brief. Read what the brief would contain yourself, and write `dm/screen-digest.md` if you like (see `.claude/agents/gm-screen.md`, task `brief`), then create the session log and set the status as below.

**Missing prep:** if there's no `dm/session-prep/session-NN-prep.md` (and it isn't session 1), tell the player "One moment, I'm preparing the session." Delegate to the **dm-scribe** agent (wait for the result: `run_in_background: false`): "campaign `<slug>`: advance the world if not yet done since session NN-1, then prep session NN".

**Then get the DM brief** from the **gm-screen** agent (wait for the result: `run_in_background: false`):
- **Description:** "Prepare the DM brief"
- **Prompt:** "campaign `<slug>`, session NN: `brief`. Create `dm/session-log/session-NN.md` from `.claude/skills/start-session/session-log-template.md` if it doesn't exist, and set `campaign.md` status to `active`."

**Check the character sheets for combat:** run `python3 scripts/combat.py -c <slug> profile check players/characters/*.md`. Every PC's `combat-profile` block must pass `library/<system>/combat-profile-pc.schema.json`, or they can't be added to a fight. Fill in what the sheet already shows yourself. Collect whatever is still missing and ask the player for it in Step 3 (e.g. "For combat I still need your Strength score, Perception modifier and any special senses"). Then update the block.

Run `python3 scripts/world.py -c <slug> session` to reset the session's interruption count (and `day "<in-game date>"` if the date changed).

Keep the brief in mind for the whole session. It replaces reading the DM files.

## Step 3: Out-of-character check-in
Keep this short, in one message:
- **"Session NN of <campaign>."**
- **Character changes:** ask whether anything changed since last time, e.g. a level-up, new gear or an HP change. If so, update the sheet and its combat-profile block, or run the `/add-character` update flow for bigger changes.
- **Missing combat values:** if the sheet check in Step 2 found gaps, ask for exactly those values here.
- **Safety reminder:** for session 1, show the table of in-chat signals from `safety-tools.md`. After that, fold it into the one-line reminder below.
- **Session 1 only:** introduce the table conventions from `players/session-zero.md` in a short table (player text, "speech", [system], "end turn" in combat). Explain who has the last word, mention that they can be changed any time, and confirm how the player rolls dice.
- **Later sessions:** add the conventions to the one-line reminder, e.g. *"(Reminder: "quotes" = speech, [brackets] = talk to the system; X, pause, rewind, fade, check work any time.)"*

Wait for the reply before continuing.

## Step 4: Recap and opening scene
1. **Recap:** "Previously…" in a few sentences, in the campaign's tone. Use only player-safe sources: the latest `players/recaps/` file and `players/party.md`. Skip it for session 1, or give a short in-world intro from `players/setting-primer.md` instead.
2. **Opening scene:** if in-game time passed since the last session, run a world turn first through gm-screen. Then pick up exactly where the brief says. For session 1 or after a time skip, use the prep's strong start. Set the scene with a few vivid details, and end on a prompt the player can act on.

Then run the game following `running-the-game.md` and `continuity.md`, with all hidden mechanics and bookkeeping going through gm-screen: improvisation checks for anything with plot weight, a world turn at every transition (travel, rest, time passing, notable PC actions, stuck signals), secret checks, combat, and a checkpoint at every scene break. When the player wants to stop, or the session reaches a natural end, suggest `/end-session`.
