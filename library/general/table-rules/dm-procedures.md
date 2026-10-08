# DM Procedures

The hidden bookkeeping of a session: what the DM does behind the screen, with the game tools (`dice_roll`, `world`, `combat_*`) and the `dm/` files. The player sees only your narration (see "Behind the screen" in `running-the-game.md`), so none of this shows. Keep it fast: every tool call is waiting time for the player.

## The digest: `dm/screen-digest.md`
A cached summary of what you need on every turn, so you don't re-read session zero, the sheets and the prep. Write it during the **brief**. Rewrite it when settings change (a [bracketed] change, a level-up, new gear) and at **close-session**. Keep it **under about 80 lines**:
- **Table settings:** lethality, the mercy policy and whether it's been used, dice and noticing-check conventions, effective APL, world pressure, event chance and session budget, branching budget, DM voice
- **Lines and veils**
- **PC quick stats:** HP, AC (touch / flat-footed), saves, init, secret-check modifiers (Perception, Sense Motive, Knowledges and so on), situational modifiers (e.g. +2 vs enchantment), notable abilities with uses left
- **Now:** in-game time, location, current scene, active combat, interruptions this session, last random event
- **Index:** where things are, as `file → section heading`: the current adventure's scenes, handouts, NPCs likely to appear, the prepared encounters

**Read files by section, not whole:** find the heading (`grep -n '^#' <file>`, or the digest's index), then read with an offset and limit. Don't re-read what you already have in this conversation.

## Brief (session start, or after the context was compacted)
Read the files `/start-session` lists, write the digest, and get the picture straight before you narrate:
- the current scene and exact situation
- what's prepped for this session: the strong start, likely scenes, secrets and clues and where they are
- the NPCs likely to appear: voice, wants, what they know, and what's locked vs. flexible
- active threads and their next beats
- clocks, scheduled events and reaction triggers that could fire soon
- floating clues, the current awareness and heat levels
- backstory hooks ready to use, and continuity notes from the last session

## Secret checks
Roll the checks for the PCs with `dice_roll` (`hidden: true`), using the modifiers from `players/characters/` (situational ones included), against the hidden DCs or opposed rolls. Narrate only what each character notices. A failure gives nothing, or the misleading result a failure produces. Checks the player initiated ("I examine the hands") get a roll marker if session zero has them on (`running-the-game.md`, "Rolls"); reactive and system-secret checks never do.

## World turn
At every transition, run the procedure in `living-world.md`: the `world` tool for the random-event part (transition class, settlement cooldown, session budget), plus scheduled events, clocks, reaction triggers and floating clues. The tool logs the turn in the live log (what else fired goes in its `note`); `dm/world.md` and `dm/state.md` are updated at close-session.

## Oracle
For a yes/no question the records don't answer: set the odds from the established facts, roll with `dice_roll` (`oracle`), and interpret the result consistently with the records (`continuity.md`).

## Improvisation check
Before saying anything with plot weight: run the protocol in `continuity.md`. Reuse existing elements, check the timeline, threads and NPC files, and adjust flexible facts if needed. Record it at once if you use it.

## Live log and checkpoints
- **Log as you go:** key events, decisions, rolls that mattered, NPCs met, loot, HP and resources spent, in the right sections of `dm/session-log/session-NN.md` (Log, New elements, Revealed, World turns, Combat). Tersely, at scene breaks.
- **Checkpoint** at scene breaks (the end of a scene, combat or location; `continuity.md`): lock revealed facts, and update the threads and the timeline. Batch these edits into as few tool calls as possible.
- **`dm/world.md` and `dm/state.md` wait for close-session.** During play the live log is their record: world turns log themselves (the `world` tool), fights append their log (`combat_end`), and the rest goes into the log at scene breaks. Close-session folds it all into both files.

## Close-session (from `/end-session`)
- Refresh the digest for next time.
- Complete the live log and its "Changes" section. Record the stars & wishes under their own heading, and check any quick "Rulings to check".
- Do a final checkpoint, and fold the live log's World turns, track changes and fired triggers into `dm/world.md`.
- Update `dm/characters/*` Observations (what the player enjoyed, their tactics, how hooks landed), `dm/campaign-plan.md` if the stars & wishes change how to run it, `dm/state.md` (last session, date, location, the exact current scene including a paused combat, PC status, open threads) and `dm/world.md`.
- Work out the XP (defeated encounters by CR plus story awards, divided as session zero says) or the milestone. Tell the player the award and their status.

## Gear, money and shops
Everything the party owns is in `players/inventory.json`, and only the `gear` tool changes it. It logs every change in the live log ("Gear & money"). The player sees the gear in the interface, generated from the inventory: each character's Gear section in the Character tab, and the Party stash tab. The sheets and `party.md` have no gear list; `gear show` tells you who carries what.
- **Loot and rewards:** `gear add` (items) and `gear receive` (coins), into the character who takes them or the stash. Item files must exist: look them up first (`lookup`; the researcher saves `library/<system>/items/<slug>.json`). A campaign's own item (a unique blade, a letter): `dm/items/<slug>.json`.
- **Spending:** `gear pay` for services, rooms, bribes, tolls (with why); `gear use` when a consumable is used up or a wand spends charges.
- **Shops:** when the party visits a shop for the first time, write `dm/shops/<slug>.json`: what it plausibly stocks for the settlement (its base value: items at or below it are 75% likely available; `equipment-economy.md`), the settlement's purchase limit, and what it buys. Then `gear buy` / `gear sell` do the rest: prices, half-price sales, the purchase limit, stock counts. Haggling or a special deal is a DM decision: give the price and why.
- **HP outside a fight:** `character_hp` (+N, -N, =N, with why): healing between fights, a night's rest, a fall, a trap. It updates the sheet's HP line and logs it. In a fight, `combat_hp`; `combat_end` writes the HP back.
- **Moving things:** `gear move` between characters and the stash, money included ("25 gp"). The stash is wherever the campaign says it is (a chest, a packhorse); give it a `where`.

## Combat end
`combat_end` writes the XP summary, puts the PC's HP back on their sheet, appends the combat log to the session log, lists what lies on the ground, and archives the fight. Then put the loot the party takes into the inventory (`gear add`, `gear receive`), log the resources spent (`gear use`), and do a checkpoint.
