# Running Combat

How combat runs at the table. The system's rules come from `library/<system>/rules/`, and session zero and the table conventions override this guide.

## Stat blocks
Always use real stat blocks, never numbers made up in the moment. Stop at the first option that works:
1. **Official stat block,** found with `lookup` from the allowed sources.
2. **Official stat block plus official adjustments:** templates, class levels, extra Hit Dice.
3. **Reskin / proxy:** a mechanically identical official creature with new flavor. For example, a flying seahorse is a giant eagle with bludgeoning damage and a swim speed.
4. **Homebrew,** built and checked against the system's monster creation guidelines (for PF1e: `library/pf1e/rules/monster-creation.md`).

For an **unexpected fight,** take a moment and prefer options 1–3; they're fast and balanced. Save every stat block you use to the library, so the next fight is faster. Size encounters with `library/<system>/rules/encounter-building.md`.

## Grid or theater of the mind?
- **Grid** when position matters: terrain, cover, several enemies, reach, flanking, area spells, or a boss fight.
- **Theater of the mind** for quick, simple fights, like two thugs in an alley or a single animal. Describe positions in words and keep the tracker in the live log.
- The player can always ask for either with [brackets].

## The combat script
Never draw the map by hand, and never count squares in your head. `scripts/combat.py` holds the battle state and does the geometry (run it with `-h` for commands).

**Setup:**
- Use a prepared map from `dm/combat/maps/` if the prep has one, or write a quick map file. Otherwise use `--blank WxH`.
- Add every combatant with its real initiative roll (from `roll.py`), HP, AC, CR, size, reach and speed.
- Add enemies the PCs can't see yet with `--hidden`, and `reveal` them when they're spotted.

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

**Map symbols:** PCs are uppercase letters (`V`), allies and enemies are lowercase plus a number (`g1`, `o1`), and `x` marks fallen enemies. Coordinates work like chess: columns A…, rows 1…. The player can use them ("I move to D4 and attack g2").

## Flow
After each message you wait for the player, so a message per enemy turn would make the player type "continue" constantly. Instead:
1. **Resolve every consecutive non-PC turn in one message.** Give each one a line or two, with the key rolls, e.g. *g1 charges Valeros: 17 vs AC 16, hit, 6 damage.* Hidden rolls stay hidden.
2. **End with the player view** (map plus tracker) **and whose turn it is.** Show the map when positions changed since the last one; the tracker always shows. Then say "Valeros, your turn."
3. **Pause mid-batch only when the player could react,** e.g. a readied action, an immediate action, or a choice they must make, such as an attack of opportunity they haven't set a standing order for. Ask, then continue the batch after the answer.
4. **Standing orders** avoid pauses. The player can set them any time, e.g. "always take AoOs", "Feather Fall if anyone falls", or "hold the door". Record them in the live log and apply them without asking.
5. **On the player's turn,** accept a full turn in one message, e.g. "Move to D4, attack g2, rolled 17, 9 damage". Resolve it, update the script, then run the next batch.
6. **Step mode:** if the player asks for `[step mode]`, e.g. for a boss fight, resolve one actor per message instead.
7. **In a surprise round,** only aware combatants act, with one standard or move action each.

## Narration
**The default is one line per action,** with the key rolls: *g1 charges Valeros: 17 vs AC 16, hit, 6 damage.* Quick and readable, so combat keeps moving.

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

## Honesty and tactics
- **Enemies act by their nature and knowledge,** not by what you know as DM. A goblin doesn't know the wizard is out of spells. Intelligent enemies do use tactics: focus fire, flanking, retreating, surrendering, fleeing.
- **Report rolls truthfully** and apply the session-zero mercy policy only as agreed.
- **Morale:** most creatures flee or surrender when the fight is clearly lost. Use the morale entry in the stat block, if it has one.

## After combat
Run `end`. It prints a summary with the XP from defeated enemies, and archives the state. Copy the relevant results to the live log (XP, loot, HP, consequences), then run a checkpoint (`continuity.md`).
