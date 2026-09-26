---
name: end-session
description: Wrap up the current game session. Collects stars & wishes, awards XP, writes the DM log and a player recap, updates party, characters and state, runs a continuity check, advances the world, and preps the next session. Use when the player wants to stop, end or wrap up a session.
argument-hint: "[campaign]"
---

# End Session

Use the campaign that was just played, or `$ARGUMENTS`. `NN` is the current session number, and its live log is at `dm/session-log/session-NN.md`.

If the session stops mid-scene (including mid-combat), that's fine. Record the exact situation, including enemy HP and initiative, so play can resume there.

## Step 1: Wrap up with the player
Keep this to one message, out of character:
1. **Stars & wishes:** what did they enjoy this session, and what would they like to see more of? A short answer, or "skip", is fine.
2. **Anything to note:** rulings they disagreed with, or changes to lines and veils.

Wait for the reply.

## Step 2: DM records behind the screen
Delegate to the **gm-screen** agent:
- **Description:** "Close the session"
- **Prompt:** "campaign `<slug>`, session NN: `close-session`", plus "Events since last call" and the player's stars & wishes, rulings feedback and safety changes.

It completes the DM log and its "Changes" section, records the stars & wishes, checks quick rulings, and updates `dm/characters/*`, `dm/campaign-plan.md` (if stars & wishes change how to run it), `dm/state.md` and `dm/world.md`. It also works out the **XP or milestone** award using the advancement method in session zero and `library/<system>/rules/`. It returns the award and the PC status as player-safe facts.

## Step 3: Player records
Write these yourself. They only contain what the player knows:
1. **Player recap** (`players/recaps/session-NN.md`):
   - Write it from the characters' point of view, in the campaign's tone, in a few paragraphs.
   - Include **only what the characters experienced or learned.** No hidden rolls, no NPC motives they didn't discover, no off-screen events.
   - End with open questions and leads, as the characters see them.
2. **`players/party.md`:** loot, gold, quests, allies, enemies, and things learned.
3. **`players/characters/*`:** the XP award, current HP, conditions, and consumables used. Add a changelog line for each. Tell the player the award and whether anyone can level up. For milestones, give the reason only if it's player-safe.
4. **`campaign.md`:** increment "Sessions played" and update the party level.
5. **Safety:** if lines or veils changed, update `players/session-zero.md`.

## Step 4: Continuity check
(The `close-session` call has already done the final checkpoint: revealed facts are locked, and "New elements" and "Revealed" are complete.)

Then delegate to the **continuity-checker** agent: "campaign `<slug>`, session NN". Relay only its spoiler-free summary.
- If it reports a problem with a locked fact that **needs raising OOC**, raise it now, briefly and honestly, e.g. *"(OOC: I realized I contradicted myself about when the fire started. The earlier version stands / let's say X instead. Okay?)"*. Record the outcome as locked.

## Step 5: Behind the screen
Delegate to the **dm-scribe** agent: "campaign `<slug>`: session NN just ended; act on the continuity report's 'For next prep' section, advance the world, then prep session NN+1". Tell the player "I'll prepare next session behind the screen." Relay only the agent's spoiler-free confirmation.

## Step 6: Close
- Show the player recap. It's theirs to read.
- If this is a git repo, offer to commit the session as a save point with the message `<campaign>: session NN`.
- Close with a short in-world teaser line that doesn't spoil anything, e.g. an ominous image or an open question the characters already know about.
