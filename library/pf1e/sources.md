# PF1e Sources

Where to look things up for PF1e, in order: the library first, then these sites. Save anything useful you find to the matching library folder with a link to the source.

| Purpose | Source | Notes |
|---|---|---|
| Rules, classes, feats, spells, items, monsters | d20pfsrd.com | Primary. Mixes Paizo and third-party (3pp) content; 3pp content is labeled with its publisher. |
| Cross-checking, official wording | aonprd.com | Archives of Nethys. Official Paizo content only. |

## Third-party content
On d20pfsrd, check whether content is Paizo or third-party. Use third-party content only if the campaign's session-zero allowed sources include that publisher. When saving to the library, note the publisher.

## Conflicts
If d20pfsrd and aonprd disagree, aonprd's wording wins for Paizo content. Note any errata you find.

## Published-adventure spoilers
Apply `library/general/table-rules/published-content.md`. Signals checked 2026-09-25:

**Archives of Nethys**
- **Source line:** `Source <Book> pg. NN`, with several sources separated by commas.
  - Core: `Pathfinder RPG Bestiary pg. NN`, `Bestiary 2 pg. NN`, …
  - Adventure volume: `Pathfinder #NN: <title> pg. NN`
  - Hardcover AP reprint: `<AP name> Anniversary Edition pg. NN`
- If **all** sources match `Pathfinder #\d+:` or `Anniversary Edition`, it's adventure content. If a core book is also listed, prefer that version.
- **Unique creatures** aren't marked on their own page. They're listed at `Monsters.aspx?Letter=Unique`, so treat anything that appears there as unique.

**d20pfsrd**
- There's usually no source line. The source is in the **Section 15** copyright block at the bottom of the page, e.g. `Pathfinder N: <title>. Copyright YYYY, Paizo…` or `Pathfinder Adventure Path: <AP name>…`. Paizo plus "Pathfinder" plus an issue number, or "Adventure Path", means it's adventure content.
- A URL containing `/unique-monsters/` means a unique NPC or monster. The adventure isn't named, so treat it as adventure content.
- **Third-party:** a URL or breadcrumb containing `3rd-party`, or a non-Paizo copyright holder in Section 15.

## Allowed domains
The web allowlist hook reads this list (subdomains are included).
- d20pfsrd.com
- aonprd.com
