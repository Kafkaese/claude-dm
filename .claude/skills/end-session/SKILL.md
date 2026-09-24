---
name: end-session
description: Wrap up the current game session. Collects stars & wishes, awards XP, writes the DM log and a player recap, updates party, characters and state, advances the world, and preps the next session. Use when the player wants to stop, end or wrap up a session.
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

## Step 2: XP & advancement
Follow the advancement method in session zero.
- **XP:** total the XP from the encounters and story awards in the live log, using `library/<system>/rules/`. Divide it among the PCs who were present. Show the award and each PC's new total, and say if anyone can level up.
- **Milestone:** say whether a milestone was reached. Only share the reason if it's player-safe.

## Step 3: Write the records
Use spoiler-free tool descriptions throughout.
1. **DM log** (`dm/session-log/session-NN.md`):
   - Complete the log and the "Changes" section.
   - Record the stars & wishes.
   - List any rulings still to check. Check them now if they're quick, and note the correct rule for next time.
2. **Player recap** (`players/recaps/session-NN.md`):
   - Write it from the characters' point of view, in the campaign's tone, in a few paragraphs.
   - Include **only what the characters experienced or learned.** No hidden rolls, no NPC motives they didn't discover, no off-screen events.
   - End with open questions and leads, as the characters see them.
3. **`players/party.md`:** loot, gold, quests, allies, enemies, and things learned.
4. **`players/characters/*`:** XP, current HP, conditions, and consumables used, as known. Add a changelog line for each.
5. **`dm/characters/*`:** add to Observations what the player enjoyed, their tactics, and how the backstory hooks landed. If stars & wishes changed how the campaign should be run, note that in `dm/campaign-plan.md`.
6. **`dm/state.md`:** update everything for picking up next time: last session, date, location, exact current scene, PC status, open threads.
7. **`campaign.md`:** increment "Sessions played" and update the party level.
8. **Safety:** if lines or veils changed, update `players/session-zero.md`.

## Step 4: Behind the screen
Delegate to the **dm-scribe** agent: "campaign `<slug>`: session NN just ended; advance the world, then prep session NN+1". Tell the player "I'll prepare next session behind the screen." Relay only the agent's spoiler-free confirmation.

## Step 5: Close
- Show the player recap. It's theirs to read.
- If this is a git repo, offer to commit the session as a save point with the message `<campaign>: session NN`.
- Close with a short in-world teaser line that doesn't spoil anything, e.g. an ominous image or an open question the characters already know about.
