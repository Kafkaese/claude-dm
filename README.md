# Claude DM
A setup for running Pathfinder campaigns with Claude as the Dungeon Master. See CLAUDE.md for the layout and rules.

## Playing
```
python3 play.py              # new session, then e.g. /new-campaign or /start-session <campaign>
python3 play.py --resume     # continue the last session
python3 play.py --debug      # show tool calls and subagents too (for testing)
python3 play.py --effort high # think harder (slower); default is medium, :effort switches mid-game
```
`play.py` shows only the DM's words. Dice, notes and prep stay behind the screen. During fights it prints the map after each turn, and in iTerm2 it also shows the map image inline. In-game commands: `:map`, `:debug`, `:help`, `:quit`. End a line with `\` to write several lines.

It uses your normal Claude Code login. With `ANTHROPIC_API_KEY` set, it bills the API instead.
