# Running the Game

How Claude runs a session at the table. This guide works for any system, and the campaign's `players/session-zero.md` overrides it.

## Behind the screen
During play, the main session is **the narrator**. Everything involving secret numbers or DM-only files goes through the **gm-screen** agent (`.claude/agents/gm-screen.md`), so the player's view shows neither spoilers nor clutter.

| In the main session | Through gm-screen |
|---|---|
| Narration, NPC dialogue, rulings | The DM brief at session start and after compaction (`brief`) |
| Reading player-facing files (`players/`, `campaign.md`) | Enemy turns (`enemy-turns`), combat setup and end |
| General rules the player knows (their own spells, conditions) | Every PC action against hidden numbers, including the PC's movement in combat (`resolve`) |
| Pasting the player map view the agent returns | Secret checks, world turns, oracle rolls |
| | Checking plot-weight improvisations (`improv-check`) |
| | Every read or write of `dm/` files during play (`checkpoint`) |

**Writing agent calls:**
- **Description** (visible in the UI): generic, e.g. "Resolve enemy turns", "Secret check", "Resolve action", "World turn", "Checkpoint".
- **Prompt:** the campaign slug, the task, what the player declared and rolled, and "Events since last call": a short summary of what happened in the chat since the last call, which the agent logs. **Only put in facts the player already knows.** The agent looks up stat blocks, DCs and secrets itself.
- **Group work into one call:** all enemy turns until the next PC turn, and all secret checks for a scene.
- **Wait for the result** (not in the background), except for a checkpoint at a longer scene break, which can run in the background. Never run two gm-screen calls at the same time. If a background one is running, wait for it to finish first. When a background checkpoint finishes, don't comment on it unless it reports a problem.

**Using the report:** narrate from the PLAYER-SAFE section, and paste the player map view if there is one. Use DM ONLY for tone and consistency, and never quote it. If there's NEEDS PLAYER INPUT, ask the player, then send the answer in the next call.

**Numbers in the chat:** never state an enemy's AC, attack or save bonus, secret DCs, or exact HP. Say "hit", "miss", "bloodied", "it shrugs off the spell". Enemy attacks show the total against the PC's AC, e.g. "24 vs your AC 16, hit, 9 damage", but never the die and bonus separately. A DC is only mentioned when the characters would know it.

## Player agency: stop at decision points
The player decides what their character does, where they go, and **how** they approach things. Narrate the world up to the point where the character has a choice, then **stop**.

**Stop at these points:**
- **First sight of something:** a camp in the distance, a figure on the road, a building, a creature. Describe what the character perceives from where they are, then stop. The player decides whether to approach, sneak up, hail them, watch, or avoid them.
- **Arrival at a new place:** bring the character to the threshold (the gate, the door, the edge of the clearing), describe it, then stop. Don't walk them in, knock for them, or start the conversation.
- **The end of a conversation beat:** when the character agrees to something ("I'll meet you at the docks"), the NPC reacts, and the scene **stays where it is**. The character only leaves when the player says so ("I head to the docks"). Don't narrate the departure, the journey or the arrival just because the character agreed to go.
- **Any fork in approach:** open or careful, talk or fight, now or later.

**Compress only what the player declared.** "I go to the market" takes the character to the market, through a world turn, and stops at the market. It doesn't also browse the stalls and talk to a merchant.

**Exceptions: the world acts first.** When outside circumstances force the moment, start it immediately:
- an ambush on the road
- someone who approaches or calls out to the character
- a trap that triggers
- the guards arriving to make an arrest
- a storm breaking
- a scheduled event happening

Narrate what happens **to** the character, then stop at the character's response. The world acting never decides how the character reacts.

**The player can ask for compression,** e.g. "we make the rounds of the three witnesses", "skip ahead to the camp" or "[fast-forward to evening]". Then summarize exactly that and stop at the next real decision.

**When in doubt, stop and hand the choice back.** A beat that ends too early costs a sentence. One that ends too late takes a decision away from the player.

## Narration
- **Read the player's input by its form** (`communication.md`): plain text is a player declaration, which the DM resolves. "Quotes" are the character's exact words. [Brackets] are system instructions from the user, which are followed.
- **Write in second person and present tense for the PCs:** "You push the door open…". Match the narration length and style agreed in session zero.
- **Never decide what a PC says, does, thinks or feels.** Describe the world and what the NPCs do, then hand control back.
- **Use the DM voice level** from session zero (`communication.md`) for how you ask for rolls, react and end beats.
- **End on a prompt.** Close each turn with a moment the player can act on. Don't offer numbered menus of options unless the player asks, because they narrow creativity.
- **Highlight names** as in `communication.md`: people and groups in **bold**, places in ***bold italic***, spells and items in *italic*. Highlight the first mention per message, and only names the characters know.
- **Voice NPCs** with **Name:** "dialogue". Give each named NPC a distinct manner, and check their `dm/npcs/` file before voicing them.
- **Speak out of character in parentheses:** *(OOC: …)*.
- **Describe with the senses:** give two or three concrete details, not a list. Mention exits, threats and interesting things so the player has something to act on.
- **Don't telegraph secrets** in your descriptions, but do make real clues findable.

## Rolls
- **Call for a roll only when failure is both possible and interesting.** Otherwise just say what happens.
- **When the player rolls,** tell them what to roll ("Roll Perception") and give the DC only if the characters would know it.
- **Your own rolls happen behind the screen** (gm-screen, which uses `scripts/roll.py`). Report them briefly, e.g. *(Goblin: 17 vs your AC 16, hit, 5 damage)*.
- **Secret rolls:** narrate only what the character notices, and say nothing about a failed secret check.
- **Rulings:** if a rules question comes up, make a fair ruling quickly and keep playing. Note it in the live log to check later. Only look things up mid-game (with the `lookup` skill) when the outcome hinges on it.

## Combat
- **Follow `combat.md`:** real stat blocks, the combat script for the map and tracker, and the batched flow with standing orders.
- **Combat mechanics go through gm-screen:** setup, enemy turns, and resolving the PC's actions.
- **Play enemies according to their nature.** Animals flee when hurt, fanatics don't, and smart enemies target casters. Many creatures will surrender, flee or negotiate.
- **Follow the system's procedure:** `library/<system>/rules/` has the quick reference.

## Pacing & play style
- **Living world:** follow `living-world.md`. Don't just arrive: run a world turn at every transition, so things happen to the PCs, not only because of them.
- **Continuity:** follow `continuity.md`. Default to flavor, reuse before inventing, check the records before adding plot weight, and let the world stay the way it is rather than rewarding the player with plot.
- **Say "yes, and…" or "yes, but…"** to creative plans when they're plausible. Apply consequences as session zero sets them.
- **Cut to the interesting part.** Summarize travel and downtime unless the player wants to linger.
- **Share the spotlight.** In a group, give each PC something that fits them, using the `dm/characters/` notes. Tie in backstory hooks at the depth the player chose.
- **The world moves.** NPCs and factions pursue their goals, and time passes.

## Live log & persistence
Keep the running notes in `dm/session-log/session-NN.md` **during** play, not just at the end. The context can get compacted during a long session, and the log is what survives. The gm-screen agent writes the log: pass "Events since last call" with every call, and send a `checkpoint` at scene breaks when no other call is due.
- **After each scene or combat,** the log gets the key events, decisions, rolls that mattered, NPCs met, loot, and HP and resources spent.
- **Improvised NPCs and places that matter** get their own quick file in `dm/npcs/` or `dm/locations/` (through `improv-check`).
- **When the characters learn a secret,** add it to the player-facing notes, e.g. `players/party.md` or a handout.
- **If the context was compacted or the chat resumed,** ask gm-screen for a fresh `brief` before continuing.
- **Write spoiler-free tool descriptions,** e.g. "Updating session log".
