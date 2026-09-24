---
name: start-session
description: Start or resume a game session in a campaign. Loads the campaign state, checks prep, gives a player-safe recap and sets the opening scene. Use when the player wants to play, continue, or start the next session.
argument-hint: "[campaign]"
---

# Start Session

## Step 1: Pick the campaign
Use `$ARGUMENTS` if given. Otherwise use the only campaign whose `campaign.md` has status `active` or `planning`, or ask. If there's no campaign yet, suggest `/new-campaign`. If `players/characters/` is empty, suggest `/add-character` first.

Session number: `NN` = "Sessions played" in `campaign.md` + 1, zero-padded to two digits. If `dm/session-log/session-NN.md` already exists, this is a **resume** of an interrupted session. Continue that log and skip ahead to Step 4.

## Step 2: Load context (silently)
Read all of these. Use spoiler-free tool descriptions.
- `library/general/table-rules/safety-tools.md`, `running-the-game.md`, `continuity.md` and `living-world.md`
- `campaign.md`, `players/session-zero.md`, `players/party.md`, `players/characters/*`
- `dm/state.md`, `dm/campaign-plan.md`, `dm/threads.md`, `dm/timeline.md`, `dm/world.md`, `dm/characters/*`
- the latest `dm/session-log/` (including its continuity report) and `players/recaps/` files
- `dm/session-prep/session-NN-prep.md`. For session 1, read the opening adventure in `dm/adventures/` instead.
- `library/<system>/rules/` quick references relevant to play

**Missing prep:** if there's no prep file (and it isn't session 1), tell the player "One moment, I'm preparing the session." Delegate to the **dm-scribe** agent, telling it: "campaign `<slug>`: advance the world if not yet done since session NN-1, then prep session NN". Then read the prep it wrote.

Create `dm/session-log/session-NN.md` from [session-log-template.md](session-log-template.md). Set `campaign.md` status to `active`.

## Step 3: Out-of-character check-in
Keep this short, in one message:
- **"Session NN of <campaign>."**
- **Character changes:** ask whether anything changed since last time, e.g. a level-up, new gear or an HP change. If so, update the sheet, or run the `/add-character` update flow for bigger changes.
- **Safety reminder:** for session 1, show the table of in-chat signals from `safety-tools.md`. After that, a one-liner is enough: *"(Reminder: X, pause, rewind, fade, check work any time.)"*
- **Session 1 only:** confirm how the player wants to declare actions and roll dice, per session zero.

Wait for the reply before continuing.

## Step 4: Recap and opening scene
1. **Recap:** "Previously…" in a few sentences, in the campaign's tone. Use only player-safe sources: the latest `players/recaps/` file and `players/party.md`. Skip it for session 1, or give a short in-world intro from `players/setting-primer.md` instead.
2. **Opening scene:** if in-game time passed since the last session, run a world turn first (`living-world.md`). Then pick up exactly where `dm/state.md` says. For session 1 or after a time skip, use the prep's strong start. Set the scene with a few vivid details, and end on a prompt the player can act on.

Then run the game following `running-the-game.md` and `continuity.md`. Run the improvisation protocol for anything with plot weight, run a world turn at every transition (travel, rest, time passing, notable PC actions, stuck signals), and do a checkpoint at every scene break. When the player wants to stop, or the session reaches a natural end, suggest `/end-session`.
