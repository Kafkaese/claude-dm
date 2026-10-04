# Claude DM
A setup for running Pathfinder campaigns with Claude as the Dungeon Master. See CLAUDE.md for the layout and rules.

## Playing
Play happens in the browser:
```
python3 web.py                   # opens http://127.0.0.1:8765 on the campaign picker
python3 web.py --effort high     # think harder (slower); default is medium
python3 web.py --debug           # also show tool calls and subagents (for testing)
```
The page opens on a campaign picker: continue a campaign's last conversation, start its next session, or create a new campaign. Each session is locked to its campaign, so nothing crosses over between campaigns.

It's a local chat page that follows your system's light or dark mode. It shows only the DM's words, with a status line while the DM works behind the screen. During a fight, a side panel shows the map, the initiative order and the combat log. The header opens your character sheet, the party notes and handouts. The settings menu switches campaigns, changes the thinking effort or turns on debug mode.

It runs Claude Code headless through `dm_engine.py` and uses your normal Claude Code login. With `ANTHROPIC_API_KEY` set, it bills the API instead.
