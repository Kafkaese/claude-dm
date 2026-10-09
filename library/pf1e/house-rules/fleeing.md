# Fleeing the battlefield (house rule)
**Table rule**, not in the CRB: PF1e has no action for leaving a fight for good, so a fleeing creature would otherwise just move away round after round, and the fight turns into a chase. `scripts/combat.py` implements it (`flee`, the `combat_flee` tool).

- **A full-round action**, declared on the creature's turn (it takes no other action that turn).
- **Only from the map edge:** the creature has to stand at the edge of the battle map (any part of its space on the outermost row or column). A creature in the middle of the map moves there first. The PCs see where it's heading.
- **Not while threatened:** a creature that an enemy threatens can't flee. It has to get clear first, e.g. with a withdraw, and flee on a later turn.
- **It takes effect on its next turn:** at the start of the creature's next turn it leaves the battlefield and is removed from the fight. It gets no turn then.
- **It can be stopped, like a spell being cast:** a hit (any damage, even if damage reduction absorbs all of it) or a grapple before then stops the flight. A miss doesn't. A stopped creature stays in the fight and may try again on a later turn.
- **It applies to everyone:** PCs, allies and enemies.

Moving away from a fight without fleeing (a withdraw, a run) works as normal. A creature that fled isn't defeated: whether it counts for XP is the GM's call (overcome or not).

## Changelog
- 2026-10-09: added.
