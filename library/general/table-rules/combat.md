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
3. **Open the fight** without resolving any turn yet, and without `next`, so the pointer starts before the first actor. (Exceptions: if the PC acts first, run `next` so the pointer is on them. Unnoticed enemies who act before the first visible actor are resolved silently.) Give the initiative order (only combatants the PC knows about), say who acts first, then stop. The player's "next" (or their declarations, if they're first) starts the first step. Include the map (in `play.py` the interface prints it), and a one-line reminder of the turn convention: *"(Declare your actions, and say **end turn** when you're done.)"* Give the reminder at every fight in the first sessions, and later only when it helps.
4. **Surprise:** if the enemies strike first from hiding, it's fine to narrate the ambush and then ask for initiative in the same message.

## Solo and small parties
Balance is the hardest part of solo play, and challenge ratings underestimate how dangerous enemies are to a lone character. Use the system's solo guideline (for PF1e: `library/pf1e/house-rules/solo-play.md`), plus these principles:
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

**The script knows the rules, so don't do the math yourself.** Profiles, modifiers, durations, areas, saves and dying checks are deterministic code (`scripts/combat_rules.py`). Your job is the decisions (what each creature does) and the narration. Don't add modifiers by hand, and don't track durations in your head.

**Combat profiles.** Every combatant gets its numbers from a ` ```combat-profile ` JSON block in its stat block (`library/<system>/bestiary/…`, a campaign NPC file) or character sheet (`players/characters/…`):
```combat-profile
{"init": 6, "hp": 6, "ac": 16, "touch": 13, "ff": 14, "cmb": 1, "cmd": 13,
 "saves": {"fort": 3, "ref": 2, "will": -1}, "speed": 30, "size": 1, "reach": 5, "dr": 0,
 "con": 12, "dex": 15, "feats": ["Improved Initiative"], "uncanny_dodge": false,
 "attacks": {"short sword": {"bonus": 2, "damage": "1d4", "crit": 19, "mult": 2, "type": "melee"},
             "shortbow": {"bonus": 4, "damage": "1d4", "crit": 20, "mult": 3, "type": "ranged", "range": 60}},
 "full_attack": ["short sword"]}
```
Iterative attacks use a list: `"bonus": [10, 5]`. Natural attacks go in `full_attack`, e.g. `["bite", "claw", "claw"]`. A PC's profile only needs the defensive numbers (AC, touch, flat-footed, saves, Con, init), because the player rolls their own attacks. **If a stat block has no profile yet, add one before the fight,** taken exactly from the stat block. That's a one-time cost that makes every attack after it cheaper and error-free.

**Setup:**
- Use a prepared map from `dm/combat/maps/` if the prep has one, or write a quick map file. Otherwise use `--blank WxH`.
- `add TOKEN NAME --pos D4 --ref <stat block or sheet> --init roll` (the PC gets the player's rolled initiative instead: `--init 17`). Add `--hidden` for enemies the PC hasn't noticed, and `reveal` them when they're spotted.

**Attacks:** `attack g1 C --with "short sword"` (add `--full` for a full attack, `--charge`, `--touch`, `--aoo`). For a PC: `attack C g1 --total 17 --damage 9` (plus `--nat 20 --confirm 18` for crits, `--ranged` for ranged attacks). The script applies what it can see:
- **flanking**
- **conditions** (shaken, sickened, prone, entangled, grappled, fighting defensively, …)
- **charge**
- **flat-footed AC** before a creature's first turn (unless it has uncanny dodge), and **touch AC**
- **range increments**
- **firing into melee**, unless the attacker has Precise Shot
- **cover** from walls, and **soft cover** from creatures for ranged attacks
- **concealment**, with the miss chance rolled

It confirms crits, rolls damage only on a hit, applies DR, and writes the **combat log**, the player-safe record the interface shows. For PC attacks it applies the target side, and lists attacker-side modifiers as reminders so you can check the player included them. Never roll attacks with `roll.py`. Use `log "…"` for anything else the player should see in the log.

**Conditions and effects:** `cond g1 add shaken --rounds 1`, `cond C add bless --atk 1 --rounds 30`, `cond g1 add bleeding --ongoing 1d4`. Known conditions carry their modifiers. Timed ones end by themselves, and ongoing damage is rolled at the start of the creature's turn.

**Areas and saves:**
- `area burst 10 --at D4 --save ref --dc 13 --dmg 2d6 --half --name "burning hands"`, or `area cone 15 --from C --toward E5 …`, or `line`. The damage is rolled once, and NPC saves come from their profiles.
- A PC's save becomes a pending question. Resolve it with `save C --total 17` when the player answers.
- A single save: `save g1 will --dc 14`.

**Movement:** `move g1 D4`, or `move C C4 --step` for a 5-foot step. The script tracks feet per turn.
- **Leaving a threatened square:** NPCs' attacks of opportunity are rolled automatically, and the mover stops if they drop it (use `--no-aoo` only for a deliberate exception). A PC's chance to take an AoO opens a question, unless its standing order says otherwise (`order C aoo never|always|ask`).

**`next`** moves the pointer at the **start** of each step (see "Flow"), and handles the start of that creature's turn:
- ends expiring conditions and applies ongoing damage
- resets its AoOs and movement
- makes a dying NPC's stabilization check
- for a dying PC, opens a question asking for their check. Resolve it with `stabilize C --total N`

**Also:** `dist` for ranges, `threat` for who threatens or flanks, and `hp` for healing and other HP changes. **`end`** writes the XP, puts the PC's HP back on their sheet, and appends the combat log to the session log.

**The two views:**
- `show` is the **player view**. Paste it verbatim in a code block. It hides hidden tokens and shows enemy health as words.
- `show --dm` is **for you only**. Never paste it.
- Script output marks hidden tokens `[HIDDEN]`. Never mention those tokens to the player.

**Image view (optional):** if the table uses it (see "Combat display" in session zero), run `image on` right after setup. From then on, every change re-renders `players/combat-map.png`, the player view as a picture. The player keeps it open in a VS Code tab, where it refreshes by itself. The first time, offer to open it with `code campaigns/<campaign>/players/combat-map.png`. Keep pasting the ASCII view unless the player says the image is enough. Hidden tokens never appear in the image.

**Map symbols:** each PC uses the uppercase first letter of their name (Corin → `C`; pick another letter if two PCs share one), allies and enemies are lowercase plus a number (`g1`, `o1`), and `x` marks fallen enemies. Coordinates work like chess: columns A…, rows 1…. The player can use them ("I move to D4 and attack g2").

## Flow: one actor per step
Combat runs **one actor at a time**. Each non-PC actor's turn is its own reply, and the player gives a short go signal before the next one. The map, initiative and combat log update after every step, and the player can react between actors.

**The turn pointer** (the current turn in `combat.py`) always marks the actor who is **acting now, or acted last**. Every step starts by moving it forward with `next`. The UI reads the pointer to label its button: "End turn" while it's on the PC, otherwise "Next: <the next visible actor>".

**The signals** (the web UI has a button for both; in the terminal an empty Enter sends "next"):
- **"next":** play the next actor's turn.
- **"end turn":** the PC is done. Play the next actor's turn.

**One step (one non-PC actor), ideally ONE `combat.py do` call:**
1. `next`, which moves the pointer to the actor who plays now.
2. **Hidden actors don't get their own step.** A "next" that reveals nothing would give them away. If the pointer lands on a creature the PC hasn't noticed and it stays unnoticed, resolve it silently and `next` again, in the same call, until the pointer is on a visible actor.
3. Resolve exactly that actor's turn: movement, attacks (`combat.py attack`), conditions.
4. **If the actor after it is the PC,** add one more `next` at the end, so the pointer rests on the PC and the UI shows "End turn".
   Example: `combat.py do "next" "move g1 D4" "attack g1 C --roll '1d20+4' --dmg '1d6+1' --name spear" "next"`, where the last `next` is only there because Corin is next.
5. Narrate that actor in a line or a few (see Narration), then **stop**. If it's the PC's turn now, say so in one line ("Your turn, Corin.") and wait for their declarations. Otherwise, no question at the end: the player sends the next signal.
6. **If the player must decide something mid-round** (an attack of opportunity without a standing order, a readied or immediate action, a stabilization check), ask. Also run `combat.py ask "…"` so the UI pauses auto-combat. The next state-changing command clears it.

**The PC's turn** stays open until the player says "end turn". That's the default convention; session zero can set a different phrase.
- Never assume that a declared action is the whole turn. "I attack, 20 to hit, 5 damage" resolves the attack, and then the player may still want to move, take a 5-foot step, draw a weapon, use a swift action or speak.
- After resolving what they declared, say briefly which actions remain and wait, e.g. *"Hit, 5 damage; the goblin staggers. You still have a move and a swift action."*
- Only a full-round action, or the player saying "end turn" (or "done", "that's it"), ends the turn. **When in doubt, ask.**
- A whole turn declared at once ("Move to D4, attack g2, 17 to hit, 9 damage. End turn.") is resolved, and then the next actor plays right away in the same step (the "end turn" is also the go signal). Resolving the PC's own actions never moves the pointer; it's already on the PC.
- Delaying and readying are declared the same way. Free actions like speaking are fine outside the PC's turn when the rules allow them.

**Standing orders** avoid pauses. The player can set them any time, e.g. "always take AoOs", "Feather Fall if anyone falls", or "hold the door". Record them in the live log and apply them without asking.

**Surprise round:** only aware combatants act, with one standard or move action each, and each one is still its own step.

**In the Claude Code UI** (gm-screen mode), send one `enemy-turns` call per step, asking for exactly one actor.

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
