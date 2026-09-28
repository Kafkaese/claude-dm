# Claude DM
A setup for running Pathfinder campaigns with Claude as the Dungeon Master. See CLAUDE.md for the layout and rules.

## Playing
**In the browser (recommended):**
```
python3 web.py               # new session; opens http://127.0.0.1:8765
python3 web.py --resume      # continue the last session, with its chat history
python3 web.py --effort high # think harder (slower); default is medium
```
A local chat page that follows your system's light or dark mode. It shows only the DM's words, with a status line while the DM works behind the screen. During a fight, a side panel shows the map, the initiative order and the combat log. The header opens your character sheet, the party notes and handouts, and the settings menu changes the thinking effort or turns on debug mode.

**In the terminal:**
```
python3 play.py              # then e.g. /new-campaign or /start-session <campaign>
python3 play.py --resume     # continue the last session
python3 play.py --debug      # show tool calls and subagents too (for testing)
```
In iTerm2, the map image is shown inline. In-game commands: `:map`, `:debug`, `:effort low|medium|high`, `:help`, `:quit`.

Both run Claude Code headless through `dm_engine.py` and use your normal Claude Code login. With `ANTHROPIC_API_KEY` set, they bill the API instead.
