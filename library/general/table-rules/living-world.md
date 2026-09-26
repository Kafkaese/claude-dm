# Living World

The world doesn't wait for the players. NPCs pursue their goals, enemies react to the PCs, roads are dangerous and the law notices crimes. Things happen **to** the PCs, not only because of them. This guide is how.

Every proactive event comes from prepared material: agendas, clocks, triggers, floating clues and event tables. That keeps a lively world consistent with `continuity.md`. Record every event.

## 1. Don't just arrive
Longer transitions are opportunities. When the player says "we go to A", don't jump to "You arrive at A. What do you do?". Run a **world turn** first (section 2). Its size depends on the kind of transition, and most short hops stay uneventful (section 5). Then narrate one of these:
- **Something happens on the way:** an ambush, a stranger in need, a storm, pursuers.
- **Something stops them before they leave:** a messenger, the city watch, an old enemy at the door.
- **They arrive with the scene already in motion:** a brawl, an argument, a body, a festival, someone waiting for them.
- **They arrive quietly, when that's what the world turn says:** calm stretches are part of the rhythm. Summarize travel briefly.

In every case, stop at the character's next decision (see "Player agency" in `running-the-game.md`). The world acts; the player decides how the character responds and how they approach the place.

## 2. The world turn
During play, the gm-screen agent runs it (`world-turn`), so the checks and rolls stay hidden. Run it whenever one of these happens:
- the PCs move somewhere, or rest
- time passes: downtime, waiting, a time skip
- the PCs do something notable (see section 3)
- there are stuck signals (see section 4)

Its size depends on the **transition class** (section 5). For a hop, only steps 2–4 apply, and only for things that are **due now**. That's a quick check, not a roll.

The procedure:
1. **Advance time** in `dm/state.md` if the in-game time changed.
2. **Scheduled events:** check `dm/world.md` for anything that happens now or has already happened.
3. **Clocks:** does any clock in `dm/world.md` or `dm/threads.md` advance or fire?
4. **Reaction triggers:** did anything the PCs did match a trigger in `dm/world.md`? Check the awareness and heat tracks too.
5. **Random event:** only if the transition class allows it and the cooldown and budget permit (section 5). Roll the chance with `roll.py -H "Event check (N%): d%"`. On a result ≤ N, roll on the region's table:
   `python3 scripts/roll.py -c <campaign> -H --table campaigns/<campaign>/dm/tables/<region>.md`
6. **Stuck?** If so, apply the stall response (section 4).
7. **Pick at most one or two interruptions** per transition, and on a hop at most one. If several fire, prioritize the main plot's clocks and the reactions to the PCs, and queue the rest as scheduled events.
8. **Narrate it and record it** in the live log's "World turns", and update `dm/world.md`.

## 3. Reactions: awareness and heat
The world notices what the PCs do. Both tracks live in `dm/world.md`. They rise only because of concrete PC actions, and each rise is logged with its cause.

**Awareness** (per antagonist or faction): how much they know about the PCs and how threatened they feel.

| Level | Stance | Typical moves |
|---|---|---|
| 0 | Unaware | none |
| 1 | Curious | Watchers, a tail, questions asked about the PCs |
| 2 | Concerned | A warning, a bribe, misdirection, pressure on the PCs' allies |
| 3 | Threatened | An ambush, assassins, framing the PCs, destroying evidence |
| 4 | All-out | Direct assault, hostages, the antagonist's endgame accelerates |

It rises when the PCs get close to the truth: questioning key witnesses, finding major clues, interfering with plans, being seen at the wrong place.

**Heat** (per authority, e.g. a city watch, a church or a noble house): how much trouble the PCs are in.

| Level | Stance | Typical moves |
|---|---|---|
| 0 | Clean | none |
| 1 | Noticed | Wary looks, doors close, rumors about the PCs |
| 2 | Wanted for questioning | Guards approach and ask questions; there are fines |
| 3 | Warrant | Arrest attempt, a court case, confiscated gear |
| 4 | Outlaws | Bounty hunters, rewards posted, banishment |

It rises with crimes that have witnesses or evidence: murder, theft, trespassing, blasphemy, public violence, forbidden magic. How strict this is depends on the local law and the session zero tone. Heat also cools down over time, and allies, bribes or good deeds can lower it.

**Reaction triggers** are "if → then" entries in `dm/world.md` that you prepare in advance, e.g. "If the PCs question the dockmaster → Awareness (Cult) +1, the dockmaster reports to Brother Aldo that night." They make reactions consistent and pre-decided, instead of made up on the spot.

## 4. When the player is stuck
**Stuck signals:**
- two or more scenes with no progress on any thread
- revisiting the same places
- "what now?" or "I don't know what to do"
- visible frustration

**Response ladder:** move to the next step only if the previous one didn't help.
1. **The world acts.** Fire a clock or trigger that moves the situation, e.g. the villain makes a move that reveals something.
2. **A floating clue arrives.** Deliver one of the thread's prepared floating clues (`dm/threads.md`) through an outside actor: an NPC seeks the PCs out, a letter arrives, a rival shows up, a witness comes forward. Only use clues that already exist, and don't invent new ones.
3. **OOC help.** Offer, briefly, to recap the leads the characters know about (from `players/party.md` and the recaps). Don't solve it for them.

Stuck isn't the same as exploring. If the player is happily exploring or roleplaying, let them. Only stuck plus frustration calls for this ladder.

## 5. Frequency
The goal is a world that feels alive **without discouraging movement**. Walking to the market or making the rounds between NPCs should never feel like running a gauntlet. Four things together set the frequency.

### a) World pressure (session zero)
| Pressure | Base chance | Session budget | Feel |
|---|---|---|---|
| Calm | 10% | ~1 | The world moves mostly off-screen, and interruptions are rare |
| Lively | 20% | ~2 | Regular events, and enemies react to progress |
| Relentless | 35% | ~3 | Constant pressure, little safe downtime |

### b) Transition class
Classify each transition by **in-game time and distance**, not by how many times the player moves.

| Class | Examples | Random event roll |
|---|---|---|
| **Hop** | Minutes. Within a neighborhood, next door, back to a place already visited today | **None.** Only check what's due now. |
| **Trip** | About an hour or more. Across a city, to its outskirts, into an unfamiliar or dangerous district | Base ÷ 2 + region modifier |
| **Journey leg** | Each day of travel between settlements, or through wilderness or dungeons | Base + region modifier, once per day |
| **Night** | A night of rest | In safe lodging: base ÷ 2 − 10. Camping in the open: base + region modifier. |
| **Time skip** | Downtime, waiting, weeks passing | Base, once per week of skipped time, plus all scheduled events and clocks that come due |

Region modifiers: safe roads or settlements −10%, wilderness +10%, hostile territory +20%. The minimum chance is 0%.

### c) Settlement cooldown
- **In a settlement, at most one random event per in-game day.** Relentless pressure allows two.
- **Repeated routes never roll.** Once the PCs have made a trip safely, doing it again the same day counts as a hop.
- **Making the rounds:** when the player shuttles between known NPCs, compress it. Narrate the moves in a line and cut to the conversations. Don't make every leg a scene.

This covers "running around between the same NPCs": a dozen errands in town cost the same as one day in town.

### d) Session budget
Count proactive interruptions in the live log header: random events plus planned events from agendas and clocks.
- **Below the budget:** roll normally.
- **Budget reached:** halve all random chances.
- **Twice the budget:** no more random rolls, except for journey legs and nights in the open.
- **Consequences the PCs earned** (reaction triggers, heat, awareness) and main-plot clocks **don't need budget.** They always happen, because the world reacting to the PCs is the point. But if the budget is already spent, prefer delivering them **at the destination or at a natural pause** rather than as an interruption on the way. The guards are waiting at the inn instead of ambushing the PCs in the street.

This balances sessions of different shapes. A journey session spends its budget on the road. A session of city errands spends it on one or two well-placed moments. Both end up with a similar total.

### e) Minimum
Independent of random rolls, **every session should include at least one proactive event** that comes from an agenda, clock or trigger. The world is never entirely passive. An event isn't always combat: regional tables mix threats, social encounters, omens, faction agents and clue carriers.

## 6. Keeping it consistent
- Agents, assassins and patrols come from existing factions and NPCs with agendas in `dm/world.md` or `dm/factions/`. Give them whereabouts that fit `dm/timeline.md`.
- A random event that turns out to have plot weight goes through the improvisation protocol in `continuity.md`.
- Record every world-turn outcome that matters: in the live log, in `dm/world.md` (track changes, fired triggers, completed events), and in the timeline if it's a fact.
