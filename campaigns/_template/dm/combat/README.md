# Combat (DM ONLY)
- `current.json` is the active encounter state. It is managed by `scripts/combat.py`; never edit it by hand.
- `archive/`: finished encounters.
- `encounters/`: prepared encounters, one file per fight, set up with `combat.py setup <name>` (see its README).
- `maps/`: prepared terrain maps (text files, one character per square; see `python3 scripts/combat.py -h`).
