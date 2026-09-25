# Published Adventures & Spoilers

Official settings like Golarion come with a large body of published adventures: Adventure Paths (APs), modules and scenarios. Reference sites mix those adventures' secrets into ordinary lore and stat blocks. A campaign should never spoil an adventure the player might still want to play, and it shouldn't be built from another adventure's plot.

This applies to **everything you use**: web results, library entries, and **your own memory** of published adventures.

## What counts as published-adventure content
Anything whose source is an AP volume, a module, a scenario, or a chapter of a bigger adventure. See "Detecting it" below for how each site shows this.

## The default policy
When the player hasn't played that adventure:

| Kind | Rule |
|---|---|
| **Named NPCs** from an adventure: villains, allies, quest givers, anyone with a plot role | **Avoid.** Invent your own NPCs. |
| **Unique monsters and creatures** (one-of-a-kind, named, or signature to an adventure) | **Avoid.** |
| **Named or unique items and artifacts** from an adventure | **Avoid.** |
| **Plots, twists, schemes, dungeon contents, secrets** | **Avoid.** Don't borrow them, even disguised. |
| **Events that happen during or after an adventure** | **Avoid.** At the default PF1e era (about 4707 AR), most AP events haven't happened yet. |
| **Generic creatures, items and spells first printed in an adventure volume** | **Allowed if they're truly generic** (a creature type, a common item, a spell) and not a plot reveal. If the only source is an adventure and it's tied to that adventure's story, treat it as avoided. Prefer versions from core Bestiaries and rulebooks. |
| **General lore:** geography, cultures, religions, public history, rulers and famous public figures, what a city is like | **Allowed,** even if some of it was first described in an AP. Use the general, public-knowledge parts, and skip the adventure-specific secrets. |
| **Pages with a spoiler warning** | **Skip the page.** Get the general information from a broader page instead, e.g. the region or city article. |

Prefer lore that cites **campaign setting books and player companions** (e.g. world guides and regional guides) over lore that cites adventure volumes.

Some places are home to famous adventures, e.g. a well-known starting town. Using the place itself is fine; its public description is setting material. Keep its adventure-specific secrets, NPC roles and events out.

When in doubt, invent your own. A campaign's own NPCs, villains and mysteries are better anyway.

## Adventures the player has played
Session zero records **published adventures the player has played or read** (the "Published adventures" section of `players/session-zero.md`). Standing information about this across campaigns is kept in `library/general/player-profile.md`.

For adventures on that list:
- **Spoilers are fine.** Its NPCs, items, events and places may be used.
- **Connection level,** as chosen in session zero:
  - **None:** treat it like any other lore, with no deliberate references.
  - **Easter eggs:** familiar places, cameos, rumors, recognizable echoes.
  - **Connected:** that adventure's consequences matter, and its NPCs can return.
  - **Sequel:** the campaign builds directly on that adventure's aftermath.
- **Whose outcome?** Canon, or the player's own table? If the player's group had a different ending, their version is what happened in this campaign's world. Record their summary in session zero; it's locked.
- **Era:** a connected campaign has to be set after that adventure's events, so adjust the campaign's era to match.

## Saving to the library
Every library entry records its adventure source (see the entry format in the `lookup` skill):
- `Published adventure: none`, or `Published adventure: <AP or module name> (spoiler)`
- Lore files mark paragraphs taken from an adventure with `[AP: <name>]`.

Entries marked as adventure content can only be used in campaigns whose session zero lists that adventure as played.

## Detecting it
See the site-specific signals in each `sources.md`. The general signals are:
- The **source line or citation** names an Adventure Path volume, a module or a scenario rather than a rulebook, bestiary or setting book.
- The page has a **spoiler warning**.
- The subject is **unique or named** (an individual, not a type) and its only sources are adventures.
