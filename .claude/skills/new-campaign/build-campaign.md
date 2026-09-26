# Build a Campaign (spec for dm-scribe)

The interview is done. `players/session-zero.md` and the basic `campaign.md` are written. Your job is to build everything else, behind the screen. Follow `CLAUDE.md`, `library/general/table-rules/continuity.md`, `living-world.md` and `published-content.md`.

## 1. Setting
Settings live in `library/settings/<slug>/` and can be reused across campaigns (see `library/settings/README.md`). Research the setting yourself using the allowed sources.
- **Golarion (default):** use canonical lore, filtered through `published-content.md`, and respect the "Published adventures" section of session zero. The default era is about 4707 AR unless session zero says otherwise. Make sure the starting region has a file in `library/settings/golarion/regions/`. Save what you learn, with its sources.
- **Claude-made setting:** build only as much as the scope needs. A one-shot needs a town and its surroundings. An epic needs a continent overview, major powers and a pantheon. PF1e clerics need deities with domains, so either define domains or reskin Golarion deities. Write `overview.md`, then add files as needed.
- **Homebrew from the user's material** (already saved to `source/` by the main session): write `overview.md`. List gaps and contradictions in your report as questions the main session can ask the player. They're about the player's own material, so they aren't spoilers. Fill minor gaps yourself and mark them `[Claude invention]`.

## 2. Campaign files
Fill in the template files in `campaigns/<slug>/`:
- `campaign.md`: complete the player-safe pitch and the campaign-specific house rules
- `players/character-creation.md`: build rules, plus the roles and skills that will be useful and hooks for backstories
- `players/setting-primer.md`: one page of common knowledge about the world and the starting region
- `dm/campaign-plan.md`: premise, antagonists and what they do if unopposed, arcs, themes, hooks
- `dm/adventures/<first-adventure>/`: the opening adventure, detailed enough to run session 1
- `dm/npcs/` and `dm/locations/`: the key people and places for the opening, using `_npc-template.md` and `_location-template.md`. Only the most important ones need files; don't over-build.
- `dm/state.md`: the starting situation
- `dm/timeline.md`: the true chronology leading up to the campaign. Tag everything `[flex]`, except facts already stated in the pitch or setting primer, which are `[locked S00]`.
- `dm/threads.md`: T01 for the main plot (truth, clues available, clock, 1–3 floating clues) and any planned side threads, each with its connection to the main plot. Set the side-thread budget from session zero.
- `dm/world.md`: world pressure and base event chance, scheduled events, awareness and heat tracks (all at 0), reaction triggers for the opening adventure, and agendas in motion
- `dm/factions/`: a file for each antagonist group with an agenda (`_faction-template.md`), with its next moves and its reactions at each awareness level
- `dm/tables/<starting-region>.md`: a random event table for the starting region (`_region-template.md`)
- **Companion** (if session zero has one and the DM builds it): an official NPC stat block, or a build at the PC's level minus 1, filling a role the PC lacks (e.g. a healer or a front-liner for a caster). Give it a personality, voice and wants of its own. The sheet goes in `players/characters/<companion>.md`, marked as a companion. It's visible to the player, since it's an ally. Any secrets or hooks go in `dm/characters/<companion>.md`. If the player builds it, leave a note for `/add-character` instead.
- Stat blocks for the opening encounters: save them to the library, following the stat block order in `library/general/table-rules/combat.md`

## 3. Design principles
- **Addressable files.** Give every scene, room, handout, encounter and NPC section its own heading (`###`), with an ID where it helps (e.g. `### H2. Tally-stele`). Agents read files section by section, so clear headings make every call during play faster and cheaper. Prefer several focused files over one huge one.
- **Original content.** Invent the campaign's NPCs, villains and mysteries yourself. Use published-adventure material only as far as the "Published adventures" section of session zero allows, e.g. easter eggs or connections to adventures the player has played.
- **Balanced fights:** build every encounter with the solo and small-party rules in `library/<system>/rules/encounter-building.md` and `combat.md`: effective APL, the solo checks, worst-case allies, and an exit ramp.
- **Robust mystery.** Every important conclusion needs several clues, so the plot survives improvisation.
- **Match the structure the table chose:**
  - **Sandbox:** factions with goals, locations, rumors and clocks rather than plot.
  - **Story-driven:** arcs and key beats.
  - **Either way:** plan in detail only up to the first adventure. Keep later arcs loose, since the players will change them.
- **Variant and house rules:**
  - Campaign-only rules go in `campaign.md`.
  - Rules the user wants at every table go in `library/<system>/house-rules/`.
  - For an official or third-party variant system, check whether `library/<system>/rules/` already has a summary with its source. If not, write one.

## Report
Keep it spoiler-free: files created (counts), setting files added, homebrew questions (if any), and any published-adventure content you excluded (a count only).
