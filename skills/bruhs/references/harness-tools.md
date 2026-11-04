# Harness tools

The commands name Claude Code's tools, because that is where they are run most.
On any other agent (Codex, Grok CLI, Cursor, Gemini CLI, VS Code, Windsurf and
others), do the same thing with the closest tool that agent has. What matters is
the behavior each step describes, not the tool name. When an agent has no
equivalent at all, use the fallback in the last column and say so in your reply.

## Tools

| In the commands | What it does | On another agent | No equivalent |
|---|---|---|---|
| `AskUserQuestion({ questions })` | Asks the user to pick from 2–4 options and waits | Ask in a message: the question, then the options as a numbered list with one line each, then stop and wait. Use a structured question tool if the agent has one (Codex: `request_user_input`) | Same message. Never pick for the user when the step says to ask |
| `ToolSearch("select:<tool>")` | Loads a deferred tool's schema before calling it | Nothing to load. Call the tool directly | If the tool isn't there, the server isn't installed: take the step's "not configured" path |
| `Agent({ subagent_type, prompt })`, "the Task tool" | Runs a brief in a fresh-context subagent, often several in parallel | The agent's own subagent tool (Codex: `spawn_agent`, then wait for it) | Run each brief yourself, one at a time, keeping to its scope as if you had no other context |
| `Skill("<name>")` | Loads another installed skill | The agent's way of loading a skill by name, or read that skill's `SKILL.md` if it is on disk | Skip it and say which skill was missing. bruhs never depends on another skill to finish a step |
| `Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep` | Shell and file access | The agent's shell and file tools | — |
| `WebFetch`, `WebSearch` | Reads a URL, searches the web | The agent's web tools, or `curl` for a known URL | Say what you couldn't check |
| `mcp__<server>__<tool>` | An MCP tool, in Claude Code's naming | The same tool on the same server, under that agent's naming. Match on server name plus tool name (`linear-perdix` + `linear_get_issue`) | The server isn't installed: take the step's "not configured" path |
| `/bruhs:<command>` | A slash command | Ask for it by name: "bruhs cook PERDIX-145". `SKILL.md` routes to `commands/<command>.md` | — |

### Question blocks

Steps that say "ask the user" are followed by a block written as Claude Code's
`AskUserQuestion` call. On Claude Code, make that call. Anywhere else, read the
block as the spec of the question:

- `question` is what to ask, and `header` is a short label you can drop.
- Each option's `label` is a choice and its `description` the one line under it.
  List them in that order, numbered, and keep any "(Recommended)" marker.
- `multiSelect: true` means the user may pick several. Say so ("pick any").
- Several entries in `questions` are separate questions in one message.
- Comments and `${...}` values in the block are filled in from the step, as in
  any other code block.

Then stop and wait for the answer. The 4-option limit is Claude Code's; keep it
anyway so the lists stay short.

## Subagents

Some steps hand a brief to a subagent with a role. Use the first option your
agent has:

| Role | Claude Code | Other agents | No subagents |
|---|---|---|---|
| **explorer** (map code, patterns, dependencies) | `feature-dev:code-explorer` if that plugin is installed, else `Explore`, else `general-purpose` | The subagent tool, with the brief as written | Do the exploration inline |
| **reviewer** (`REVIEWER` in `peep`; bugs, security, logic, performance) | `feature-dev:code-reviewer` if that plugin is installed, else `general-purpose` | The subagent tool, with the brief as written | Review inline, one file at a time, with the same brief |

The brief carries everything the role needs, so a general-purpose subagent gets
the same result as a specialised one. Don't fail a step because a named agent
type is missing.

## MCP config files

`scripts/detect_mcp_servers.py` reads all of these. Point users at the one their
agent uses when a step says to add a server.

| Agent | User level | Project level | Shape |
|---|---|---|---|
| Claude Code | `~/.claude.json` | `.mcp.json` | JSON `mcpServers` |
| Codex | `~/.codex/config.toml` (`$CODEX_HOME`) | `.codex/config.toml` | TOML `[mcp_servers.<name>]` |
| Grok CLI | `~/.grok/config.toml` | `.grok/config.toml` | TOML `[mcp_servers.<name>]` |
| Cursor | `~/.cursor/mcp.json` | `.cursor/mcp.json` | JSON `mcpServers` |
| Gemini CLI | `~/.gemini/settings.json` | `.gemini/settings.json` | JSON `mcpServers` |
| VS Code | — | `.vscode/mcp.json` | JSON `servers` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | — | JSON `mcpServers` |

## Project files

`CLAUDE.md` and `AGENTS.md` carry the same `bruhs:state` and `bruhs:rules`
blocks, so agents that read either file see the same config. `.claude/bruhs.json`
(legacy) and `.claude/.peep-history/` are plain files that any agent can read and
write. The `.claude/` name is historical.
