# Running Combat

How combat runs at the table. The system's rules come from `library/<system>/rules/`, and session zero and the table conventions override this guide.

## Stat blocks
Always use real stat blocks, never numbers made up in the moment. Stop at the first option that works:
1. **Official stat block,** found with `lookup`. It delegates to the `dm-researcher` agent, so the player never sees which creature you looked up. Skip unique creatures and named NPCs from published adventures (`published-content.md`).
2. **Official stat block plus official adjustments:** templates, class levels, extra Hit Dice.
3. **Reskin / proxy:** a mechanically identical official creature with new flavor. For example, a flying seahorse is a giant eagle with bludgeoning damage and a swim speed.
4. **Homebrew,** built and checked against the system's monster creation guidelines (for PF1e: `library/pf1e/rules/monster-creation.md`).

For an **unexpected fight,** take a moment and prefer options 1–3; they're fast and balanced. Save every stat block you use to the library, so the next fight is faster. Size encounters with `library/<system>/rules/encounter-building.md`.

## Starting a fight
Setting up a fight takes a moment. Use it: give the player something to do while you prepare, so the fight doesn't start with a silent wait.

1. **Call it and stop.** In one short message, with **no tool calls** before it: narrate the moment violence breaks out (only what the PC perceives), then ask the player to **roll initiative** (give their modifier from the sheet) and to get their attack and damage dice ready. Example: *"Steel clears leather. **Roll initiative** (d20+5), and get your dice ready."* End the message there.
2. **Set up while they roll.** When the answer comes in, do the whole setup in as few calls as possible: one `roll.py` call for all enemy initiatives and surprise checks, then one `combat.py do "new …" "add …" "add …" "show"` call. Hidden enemies get `--hidden`.
3. **Open the fight:** give the initiative order (only combatants the PC knows about), the map (in `play.py` the interface prints it), and a one-line reminder of the turn convention: *"(Declare your actions, and say **end turn** when you're done.)"* Give the reminder at every fight in the first sessions, and later only when it helps.
4. **Surprise:** if the enemies strike first from hiding, it's fine to narrate the ambush and then ask for initiative in the same message.

## Solo and small parties
Balance is the hardest part of solo play, and challenge ratings underestimate how dangerous enemies are to a lone character. Use the system's solo guideline (for PF1e: section 5 of `library/pf1e/rules/encounter-building.md`), plus these principles:
- **Every fight either has an ally or is easy.** Give the PC help (a companion, a temporary ally like a turned henchman, a guard who joins in, a summoned creature, or terrain that works like an ally) or keep the encounter at the easy end of the scale. A challenging or hard solo fight without any help is only for a climax, and only if session zero's lethality allows it.
- **Build for the worst plausible case,** e.g. an ally who might not join, or reinforcements who might arrive.
- **Plan an exit ramp for every serious fight:** morale, surrender, bargaining, escape routes, or capture instead of death. Know it before the fight starts, not only once the PC is dying.
- **Spread the threat across rounds:** waves, enemies at a distance, a boss who talks before fighting. That beats everything happening at once.
- **Companions:** a companion played by the player takes PC turns (with its own "end turn"). One played by the DM is resolved by gm-screen along with the other non-PC turns. It acts in character with its own judgment, not as a perfect optimizer, and the player can give it simple instructions like "stay back and heal".
- **Listen to feedback.** If stars & wishes say fights feel too hard (or too easy), adjust the campaign's effective APL in session zero, and tell the scribe.

## Grid or theater of the mind?
- **Grid** when position matters: terrain, cover, several enemies, reach, flanking, area spells, or a boss fight.
- **Theater of the mind** for quick, simple fights, like two thugs in an alley or a single animal. Describe positions in words and keep the tracker in the live log.
- The player can always ask for either with [brackets].

## The combat script
Never draw the map by hand, and never count squares in your head. `scripts/combat.py` holds the battle state and does the geometry (run it with `-h` for commands).

**In `play.py` mode,** run the script yourself. The interface prints the player view and the image after each turn, so don't paste them. **In the Claude Code UI, the gm-screen agent runs the script.** The narrator only pastes the player view it returns (see "Behind the screen" in `running-the-game.md`). Combat commands reveal stats (`add … --ac 17`) and hidden tokens, so they never run in the main session.

**Setup:**
- Use a prepared map from `dm/combat/maps/` if the prep has one, or write a quick map file. Otherwise use `--blank WxH`.
- Add every combatant with its real initiative roll (from `roll.py`), HP, AC, CR, size, reach, speed, and `--ref` pointing to its stat block file.
- Add enemies the PCs can't see yet with `--hidden`, and `reveal` them when they're spotted.

**Attacks go through the script:** `combat.py attack`. It rolls NPC attacks (`--roll "1d20+9" --dmg "1d8+5" --crit 19 --mult 2`), or takes the player's numbers for PC attacks (`--total 17 --damage 9`, plus `--nat 20 --confirm 18` for crits). It confirms criticals, rolls damage only on a hit, applies hardness or DR (`add … --dr 5`), updates HP and writes the **combat log**, the player-safe record of every attack, hit, miss and damage number. Never roll attacks with `roll.py` during a grid fight. Use `log "…"` for anything else the player should see in the log (a spell's effect, a surrender). Give PCs and allies `--con` so the log shows "dead" correctly.

**During play:**
- `move` for every movement. It finds the cheapest legal path, reports the feet used, and warns about leaving threatened squares (AoO).
- `dist` for ranges.
- `threat` for flanking and threatened squares.
- `hp` and `cond` after every hit, heal or condition.
- `next` to advance the turn.

**The two views:**
- `show` is the **player view**. Paste it verbatim in a code block. It hides hidden tokens and shows enemy health as words.
- `show --dm` is **for you only**. Never paste it.
- Script output marks hidden tokens `[HIDDEN]`. Never mention those tokens to the player.

**Image view (optional):** if the table uses it (see "Combat display" in session zero), run `image on` right after setup. From then on, every change re-renders `players/combat-map.png`, the player view as a picture. The player keeps it open in a VS Code tab, where it refreshes by itself. The first time, offer to open it with `code campaigns/<campaign>/players/combat-map.png`. Keep pasting the ASCII view unless the player says the image is enough. Hidden tokens never appear in the image.

**Map symbols:** each PC uses the uppercase first letter of their name (Corin → `C`; pick another letter if two PCs share one), allies and enemies are lowercase plus a number (`g1`, `o1`), and `x` marks fallen enemies. Coordinates work like chess: columns A…, rows 1…. The player can use them ("I move to D4 and attack g2").

## Flow
After each message you wait for the player, so a message per enemy turn would make the player type "continue" constantly. Instead:
1. **Resolve every consecutive non-PC turn in one gm-screen call** (`enemy-turns`) **and one message.** Give each one a line or two from the PLAYER-SAFE report, e.g. *g1 charges Valeros: 17 vs your AC 16, hit, 6 damage.* Never state enemy AC, bonuses or HP numbers.
2. **End with the player view** (map plus tracker) **and whose turn it is.** Show the map when positions changed since the last one; the tracker always shows. Then say "Valeros, your turn."
3. **Pause mid-batch only when the player could react,** e.g. a readied action, an immediate action, or a choice they must make, such as an attack of opportunity they haven't set a standing order for. gm-screen stops and reports NEEDS PLAYER INPUT. Ask, then continue the batch with the answer.
4. **Standing orders** avoid pauses. The player can set them any time, e.g. "always take AoOs", "Feather Fall if anyone falls", or "hold the door". Record them in the live log and apply them without asking.
5. **The player's turn is open until they say "end turn".** That's the default convention; session zero can set a different phrase.
   - Never assume that a declared action is the whole turn. "I attack, 20 to hit, 5 damage" resolves the attack, and then the player may still want to move, take a 5-foot step, draw a weapon, use a swift action or speak.
   - After resolving what they declared, say briefly which actions remain and wait, e.g. *"Hit, 5 damage; the goblin staggers. You still have a move and a swift action."*
   - Only a full-round action, or the player saying "end turn" (or "done", "that's it"), ends the turn. **When in doubt, ask.**
   - The player can declare a whole turn at once, e.g. "Move to D4, attack g2, 17 to hit, 9 damage. End turn." Send it to gm-screen as `resolve`, including the movement, and ask for `enemy-turns` in the same call, so a round costs one wait.
   - Without "end turn", send only `resolve` for the declared actions, report what remains, and wait.
   - Delaying and readying are declared the same way.
   - Free actions like speaking or dropping an item are fine outside the PC's turn when the rules allow them.
6. **Step mode:** if the player asks for `[step mode]`, e.g. for a boss fight, resolve one actor per message instead.
7. **In a surprise round,** only aware combatants act, with one standard or move action each.

## Narration
**The default is one line per action,** with the key rolls: *The bandit leader charges you: 17 vs your AC 16, hit, **6 damage**.* Quick and readable, so combat keeps moving.
- **Every creature's turn gets its own line,** at least, including companions and allies. Never merge several creatures into one sentence ("the three of them close in and one clips you"). The player needs to see who did what. Narrate **every** attack in the combat log. The log and the narration must match.
- **Numbers the player always gets:** each attack against the PC as its total against the PC's AC (hit or miss), and **damage taken as a number, per attacker**. The same goes for saves the PC is forced to make (the DC only if the characters would know it). They show the player which enemy is most dangerous. Enemy AC, bonuses and HP stay hidden, as always.
- **Hidden creatures:** a creature the PC hasn't perceived doesn't appear in the narration, the initiative order or the map. If it acts without being noticed (moving, readying), say nothing. If its action reveals it (an attack, a noise, stepping into view), narrate the reveal from the PC's point of view as a surprise (*"Something low and fast bursts from under the cart: a dog, jaws first."*), then `reveal` it.

**Some moments get more:** 2–4 vivid sentences instead of one line. Use this for:
- **A new enemy is revealed:** what the PCs see, hear or smell as it appears. Give details that hint at what it is without handing over its stat block.
- **An enemy uses a special ability or spell for the first time:** describe what it looks and feels like, so the player can recognize it next time. Repeat uses go back to one line.
- **Unique enemies and bosses show personality:** sometimes a bit of banter, a taunt, emotion or an unusual tactic. *The bandit leader curses his men as another one falls, and throws himself at you with renewed fury.* Let it reflect how the fight is going: confident, frustrated, desperate, cornered.
- **An enemy is dispatched in a memorable way,** e.g. with a crit, a clever tactic, a spectacular spell, or an environmental kill. Describe the result the PC earned.
- **Turning points:** morale breaks (enemies fleeing, surrendering or begging), an ally falls, or the tide clearly turns.

Keep the rolls visible alongside the narration, and follow session zero's narration style and the lines and veils. Gore, for example, can be veiled.

### "How do you want to do this?"
When a **unique, powerful or boss** enemy drops to 0 HP or below from the PC's attack, stop before describing it and ask: **"How do you want to do this?"** The player describes the finishing move, and you narrate it to match, as vividly as their description deserves.
- Ask only for enemies that matter, not for every goblin. Also ask when the final enemy of a hard fight falls to a PC.
- If the player says "just finish it" or doesn't want to describe it, narrate a fitting finish yourself.
- The finish has to fit the fiction and the character's abilities, and the DM has the final say. Within that, be generous: this is the player's moment.
- If the player wants to spare, capture or interrogate the enemy, that's a valid answer too.

## When the PC goes down
- **The player rolls** their stabilization checks while dying (Constitution, per the system's rules). Ask for the roll each turn.
- **Resolve the end of the fight in the same reply, step by step:** what the enemies do (per the exit ramp prepared for this fight), what the companion does, what happens to the PC. Never "keep rolling it forward and report back later".
- **Apply the session-zero mercy policy and lethality openly,** as agreed.

## Honesty and tactics
- **Enemies act by their nature and knowledge,** not by what you know as DM. A goblin doesn't know the wizard is out of spells. Intelligent enemies do use tactics: focus fire, flanking, retreating, surrendering, fleeing.
- **Report rolls truthfully** and apply the session-zero mercy policy only as agreed.
- **Morale:** most creatures flee or surrender when the fight is clearly lost. Use the morale entry in the stat block, if it has one.

## After combat
Ask gm-screen for `combat-end`. It runs `end`, logs XP, loot, HP and consequences, and does a checkpoint. Narrate the aftermath from its PLAYER-SAFE report.
