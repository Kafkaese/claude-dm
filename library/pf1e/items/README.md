# Items
Magic items, gear, consumables: one JSON file per item, `<slug>.json` (the slug is the name in lowercase with dashes: `potion-of-cure-light-wounds.json`), following `library/pf1e/item.schema.json`. `scripts/gear.py` reads them for prices, sale values, weights and what a shop buys.

- **Base items only.** Masterwork, enhancement (+1…+5), size and broken are modifiers on an inventory or shop entry; the script prices them by the rules (`library/pf1e/rules/equipment-economy.md`). A *+1 longsword* is `longsword.json` with `"enhancement": 1`.
- **Price and weight** are for the Medium version, per `unit` (arrows: 1 gp and 3 lbs for 20).
- **`source`:** the allowed site's URL the numbers come from (`library/pf1e/sources.md`).
- A campaign's own item (a unique heirloom, a letter, a key) goes in that campaign's `dm/items/<slug>.json` instead.
- Older Markdown item notes (`*.md`) here are reference text; the script only reads the JSON files.
