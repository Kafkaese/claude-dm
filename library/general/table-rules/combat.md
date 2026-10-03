# Running Combat

How combat runs at the table. The system's rules come from `library/<system>/rules/`, and session zero and the table conventions override this guide. **The rules math is code** (`scripts/combat.py`, `combat_rules.py`, `vision.py`). You use it through the game tools: a command shown here as `combat.py setup …` is the `combat_setup` tool, `combat.py do "…" "…"` is one `combat_batch` call, and so on (the tools' descriptions list the options). This guide covers what you decide and how you narrate.

## Stat blocks
Always use real stat blocks, never numbers made up in the moment. Stop at the first option that works:
1. **Official stat block,** found with `lookup`. It delegates to the `dm-researcher` agent, so the player never sees which creature you looked up. Skip unique creatures and named NPCs from published adventures (`published-content.md`).
2. **Official stat block plus official adjustments:** templates, class levels, extra Hit Dice.
3. **Reskin / proxy:** a mechanically identical official creature with new flavor. For example, a flying seahorse is a giant eagle with bludgeoning damage and a swim speed.
4. **Homebrew,** built and checked against the system's monster creation guidelines (for PF1e: `library/pf1e/rules/monster-creation.md`).

For an **unexpected fight,** take a moment and prefer options 1–3; they're fast and balanced. Save every stat block you use to the library, so the next fight is faster. Size encounters with `library/<system>/rules/encounter-building.md`.

**Combat profiles:** every combatant needs a ` ```combat-profile ` block. Creatures: in the stat block, following `library/<system>/combat-profile-guide.md` and `combat-profile.schema.json`. If a stat block has none yet, add one before the fight, taken exactly from the stat block, and check it with `combat.py profile check <file>`. PCs: in the character sheet, following `combat-profile-pc.schema.json`. `add` refuses a PC whose block is incomplete; fill in what the sheet shows and ask the player for the rest.

## Starting a fight
Setting up a fight takes a moment. Use it: give the player something to do while you prepare, so the fight doesn't start with a silent wait.

1. **Call it and stop.** In one short message, with **no tool calls** before it: narrate the moment violence breaks out (only what the PC perceives), then ask the player to **roll initiative** (give their modifier from the sheet) and to get their attack and damage dice ready. Example: *"Steel clears leather. **Roll initiative** (d20+5), and get your dice ready."* End the message there.
2. **Set up while they roll.** **A prepared encounter** (`dm/combat/encounters/`, see `combat.py encounter list`) is one call once the player's roll is in: `combat.py setup <name> --init C=17` (add `--place C=E5` if the PC arrives elsewhere). It builds the map, lighting and every combatant, rolls NPC initiative, and shows you the tactics, morale and exit ramp. **Otherwise,** in as few calls as possible: one `dice_roll` call for surprise checks, then one `combat_batch` call (new, add, light):
   - **Map: never an empty grid.** Use a prepared map from `dm/combat/maps/`, or generate one that fits where and how the fight happens: `combat_map` with a template (forest-road, forest, clearing, field, river, village, tavern, cave, ruins, camp, swamp), the density of the vegetation, and the time of day (`start: true` begins the encounter on it, light sources included). A roadside ambush gets a road through trees and brush; a tavern brawl gets tables and the bar. A blank grid is only for a place that really is featureless.
   - **Place the combatants by the map:** the PCs where the generator says the party is (or where the narration puts them), and creatures lying in wait on the ambush spots it lists (cover or concealment near the party's path; in undergrowth they can hide). Terrain matters to the rules: trees give partial cover, undergrowth concealment, low walls cover, boulders block sight (`library/<system>/house-rules/terrain.md`).
   - **Tokens:** `add g1 Goblin --pos D4 --ref <stat block> --init roll`; the PC with `--ref <sheet> --init <their roll>`. Enemies the PC hasn't noticed get `--hidden`.
   - **Lighting is part of the encounter design:** the ambient light (`new … --light dim`, or `ambient:` in the map file), darker or brighter zones, and every light source, including what each creature carries (`light add torch --on C`). Without it, everything is in normal light.
3. **Open the fight** without resolving any turn: give the initiative order (only combatants the PC knows about), say who acts first, then stop. Never run `next`: the interface starts the turns right after your reply, so an enemy that's first plays at once, and if the PC is first it's simply their turn. If the player declares actions before their turn has come, tell them who acts first; their turn follows. Don't paste the map (the interface shows it). Add a one-line reminder of the turn convention: *"(Declare your actions, and say **end turn** when you're done.)"* Give the reminder at every fight in the first sessions, and later only when it helps.
4. **Surprise:** if the enemies strike first from hiding, it's fine to narrate the ambush and then ask for initiative in the same message. In a surprise round, only aware combatants act (one standard or move action each), each in its own step.

## Solo and small parties
Balance is the hardest part of solo play, and challenge ratings underestimate how dangerous enemies are to a lone character. Use the system's solo guideline (for PF1e: `library/pf1e/house-rules/solo-play.md`), plus these principles:
- **Every fight either has an ally or is easy.** Give the PC help (a companion, a temporary ally like a turned henchman, a guard who joins in, a summoned creature, or terrain that works like an ally) or keep the encounter at the easy end of the scale. A challenging or hard solo fight without any help is only for a climax, and only if session zero's lethality allows it.
- **Build for the worst plausible case,** e.g. an ally who might not join, or reinforcements who might arrive.
- **Plan an exit ramp for every serious fight:** morale, surrender, bargaining, escape routes, or capture instead of death. Know it before the fight starts, not only once the PC is dying.
- **Spread the threat across rounds:** waves, enemies at a distance, a boss who talks before fighting. That beats everything happening at once.
- **Companions:** a companion played by the player takes PC turns (with its own "end turn"). One played by the DM gets its own steps like the other non-PC actors. It acts in character with its own judgment, not as a perfect optimizer, and the player can give it simple instructions like "stay back and heal".
- **Listen to feedback.** If stars & wishes say fights feel too hard (or too easy), adjust the campaign's effective APL in session zero, and tell the scribe.

## Grid or theater of the mind?
- **Grid** when position matters: terrain, cover, several enemies, reach, flanking, area spells, or a boss fight.
- **Theater of the mind** for quick, simple fights, like two thugs in an alley or a single animal. Describe positions in words and keep the tracker in the live log.
- The player can always ask for either with [brackets].

## Working with the script
**Never draw the map, count squares, add modifiers, or track durations yourself.** The script resolves attacks (flanking, conditions, cover, concealment, light, range, crits, DR), maneuvers and grapples, areas and saves, movement and attacks of opportunity, spellcasting (slots, provoking, concentration), conditions with durations, dying, lighting and vision, and writes the player-safe combat log. Your job is the decisions and the narration.

What the script can't decide for you:
- **NPC spells and SLAs always go through `cast` / `sla`,** with the effect in the same command (`--area "cone 15" --toward C4 --save ref --dmg 1d4 --half`, `--target C --save will`, `--target b1 --heal 1d8+3` for cure spells, or `--light-at D4` for light and darkness spells). A targeted spell given no effect only spends the slot, and the script says so. That spends the slot. Rays and touch spells: `cast`, then an `attack … --touch` in the same `do` call. **Conditions** go in the same command: `--cond asleep --cond-rounds 5` lands on every target that fails its save (or on the target when there's no save), and a PC's pending save carries it until the player rolls. Use the script's condition names (helpless, asleep, stunned, dazed, shaken, frightened, entangled, …); an unknown name is tracked by name only, and the script says so. The player's log only says "casts a spell"; whether the PC identifies it is a Spellcraft matter.
- **The PC's numbers are the player's rolls:** `attack C g1 --total 17 --damage 9`, `maneuver C g1 trip --total 18`, `save C --total 15`. If the player gave only the attack, `attack C g1 --total 17` resolves hit or miss, and a hit waits for their damage (`damage C 9`). **Never roll or invent a PC's number**, damage and healing included, also not after a tool error.
- **Declared actions go to the script as declared.** Don't judge yourself whether a move is a legal 5-foot step or whether an action is used up; the script does, and the bracketed "Now: …" line says whose turn it is and what's left. If the script refuses, tell the player why and ask what they do instead. Never swap in another action for them.
- **Ammunition** with `ammo` in the profile (or the PC's `ammo` map) is counted, and an empty one is refused. After the fight: half the missed arrows and bolts can be recovered (hits are destroyed); thrown weapons lie where they landed (CRB). Update PC sheets.
- **Total defense** (`act C standard "total defense"`) is a standard action: the script adds the +4 dodge AC and the no-AoO effect until the creature's next turn.
- **Creatures that can't act** (dying, unconscious, helpless, stunned, dazed) get no step: the interface rolls what the script rolls (stabilization) and moves on. The dead leave the initiative order. The script lists attacker-side modifiers as reminders; check the player included them. A PC casting in melee: `provoke C --reason "casting a spell"`.
- **Questions:** when a result needs the player (an attack of opportunity, a save, a stabilization check, a concentration check), the script sets the question and names the command to resolve it. Ask the player, then run it. For your own mid-round questions (a readied action, a reaction), run `combat.py ask "…"`, so auto-combat pauses.
- **Hiding:** `hide` a creature only after a successful Stealth check; the script refuses it while the PC sees the creature clearly, and reveals hidden creatures that end up in plain view. When an unnoticed creature reveals itself (an attack, a noise), narrate it from the PC's point of view, and `reveal` it.
- **Two views:** the interface shows the player view. `show --dm`, `sight` and anything marked `[HIDDEN]` are for you only; never paste or mention them.
- **Map symbols:** each PC uses the uppercase first letter of their name (Corin → `C`), allies and enemies lowercase plus a number (`g1`, `o1`), and `x` marks fallen enemies. Coordinates work like chess: columns A…, rows 1…. The player can use them ("I move to D4 and attack g2").

## Flow: one actor per step
Combat runs **one actor at a time**. Each non-PC actor's turn is its own reply, and the player gives a short go signal ("next", or "end turn" on their own turn; the web UI has a button for it) before the next one. The map, initiative and combat log update after every step, so the player can react between actors. The script's **actor lock** only lets the creature whose turn it is act (exempt: `attack … --aoo`, and `--out-of-turn` for readied or immediate actions, forced movement and setup).

**The interface runs the turn order.** You never run `next`. On a go signal, it sends you a bracketed **combat step** message naming the one actor to play, with what happened at the start of its turn and what it can see. Resolve exactly that actor in one `combat_batch` call, narrate only that actor, and stop. If the message says the PC's turn comes right after, say so in one short line. A **hidden** actor's step works the same, but your reply is only shown if it gets revealed; if it stays unnoticed, reply "…".

**The combat runner** plays most of those steps: a separate, lean process that gets only what one creature's turn needs (the briefing, the encounter's tactics and morale, the table's tone and lines, the last few narrations). It cuts the cost of a fight by an order of magnitude. You get a recap of what it narrated with the player's next message. Bosses and story NPCs with plans or dialogue stay with you: mark them `"dm_plays": true` in the encounter (or `add … --main-dm`).


**The PC's turn** stays open until the player says "end turn" (or the phrase session zero set).
- Never assume that a declared action is the whole turn. "I attack, 20 to hit, 5 damage" resolves the attack, and then the player may still want to move, take a 5-foot step, draw a weapon, use a swift action or speak.
- **The script tracks the action economy** (standard, move, full-round, swift, 5-foot step) for every creature: each action command charges the actor and reports what's left, and it refuses what the rules don't allow. Actions without their own command (drawing a weapon, standing up, a potion, total defense) go through `act`; charges, runs and withdrawals are `move … --as charge`; a feat that changes the rules (Spring Attack, Quick Draw) takes `--override`, and nothing else does. **A corrected roll** (the player forgot flanking and gives the new total): `undo`, then enter it again. Undo takes back only the player's last command (HP, log and actions restored, a correction line in the log); NPC rolls stand. Surprise rounds: `surprise on` (or `"surprise": true` in the encounter).
- After resolving what they declared, say briefly which actions remain (from the script's report) and wait, e.g. *"Hit, 5 damage; the goblin staggers. You still have a move and a swift action."*
- Only a full-round action, or the player ending the turn, ends it. **When in doubt, ask.** When the player ends their turn in other words ("done", "that's it") or in the same message as their actions ("Move to D4, attack g2, 17 to hit. End turn."), resolve the actions and add `combat_endturn`; the next actor plays right after.
- Delaying and readying are declared the same way. Free actions like speaking are fine outside the PC's turn when the rules allow them.

**Standing orders** avoid pauses. The player can set them any time, e.g. "always take AoOs" (`combat.py order C aoo always`), "Feather Fall if anyone falls", or "hold the door". Record them in the live log and apply them without asking.

## Tactics
- **Enemies act by their nature and knowledge,** not by what you know as DM. A goblin doesn't know the wizard is out of spells. Intelligent enemies do use tactics: focus fire, flanking, retreating, surrendering, fleeing.
- **Use the tactical options** (`combat_options`; they come with every combat step). They start with **turn plans** ranked by rough expected value: the damage a plan deals (sneak attack, spells and abilities with effect data included), the support it gives (flanking for an ally, buffs, heals), the AoOs it risks and what the creature takes next round where it ends up. Below that, per target: the squares that threaten it and the d20 roll needed there (flanking, cover, light included), what provokes, charge lanes, ranged positions and retreat squares; `--area "burst 20" --range 100` adds the best placements of an area effect. The numbers do the arithmetic; you decide what this creature, with its nature and knowledge, would actually do (a cowardly kobold takes the safest square, a berserker charges, a caster opens with its best spell).
- **Personality and morale in numbers:** a profile's or encounter's `tactics` adds weights to the turn plans (a coward prefers ranged and retreats when bloodied, a berserker never defends). Broken morale shows in the plans' header. It still takes your judgment: the weights tilt the plans, they don't decide.
- **What creatures know:** the plans and the sight report assume the opponents have normal vision until their darkvision or low-light vision shows (they hit something only those senses could see). Play the creature with that knowledge (house rule: `library/pf1e/house-rules/vision-and-light.md`).
- **Spells and abilities resolve from the profile.** Each spell's effect lives once in the library (`library/<system>/spells/<name>.md`, worked out at the caster's level when it joins the fight), so `cast`/`sla` fill in the area, save, damage, healing, buff and condition; special abilities (bardic performance, channel energy, breath weapons) are `combat.py ability`. Sneak attack is added to NPC attacks automatically; for a PC, the script reminds when it applies.
- **Play every creature by what it can see** (the `sight` report in each step):
  - Creatures with darkvision fight from the dark, and go for the enemy's light: snuff the torch, sunder the lantern, grab the sunrod, cast *darkness*.
  - Creatures without darkvision stay in the light or bring their own, and don't wander into darkness they can't see in.
  - Hiders move to squares where they're unseen.
  - Creatures with light sensitivity avoid bright light.
- **Morale:** most creatures flee or surrender when the fight is clearly lost. Use the morale entry in the stat block, if it has one.
- **Report rolls truthfully** and apply the session-zero mercy policy only as agreed.

## Narration
**The default is one line per action,** with the key rolls: *The bandit leader charges you: 17 vs your AC 16, hit, **6 damage**.* Quick and readable, so combat keeps moving.
- **Every creature's turn gets its own line,** at least, including companions and allies. Never merge several creatures into one sentence ("the three of them close in and one clips you"). The player needs to see who did what. Narrate **every** attack in the combat log. The log and the narration must match.
- **Numbers the player always gets:** each attack against the PC as its total against the PC's AC (hit or miss), and **damage taken as a number, per attacker**. The same goes for saves the PC is forced to make (the DC only if the characters would know it). They show the player which enemy is most dangerous. Enemy AC, bonuses and HP stay hidden, as always.
- **Hidden creatures** don't appear in the narration, the initiative order or the map until their action reveals them. Then narrate the reveal as a surprise from the PC's point of view (*"Something low and fast bursts from under the cart: a dog, jaws first."*).

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
- **The player rolls** their stabilization checks while dying (Constitution, per the system's rules). The script asks for one at the start of each of their turns.
- **Resolve the end of the fight in the same reply, step by step:** what the enemies do (per the exit ramp prepared for this fight), what the companion does, what happens to the PC. Never "keep rolling it forward and report back later".
- **Apply the session-zero mercy policy and lethality openly,** as agreed.

## After combat
**When no enemy is left standing and nobody is dying, the interface ends the fight itself** (hidden enemies still count) and sends you its report. Otherwise (a surrender, a flight, a parley), you end it with `combat_end`. Either way, `combat_end` writes the XP, puts the PC's HP back on their sheet, and appends the combat log to the session log. Then log the loot and consequences, do a checkpoint (`dm-procedures.md`, "Combat end"), and narrate the aftermath.
