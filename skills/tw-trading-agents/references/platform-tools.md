# Per-platform sub-agent dispatch mapping

This skill uses a **fan-out / fan-in** pattern: each phase dispatches multiple
sub-agents in parallel; each analyzes its slice independently and **returns its
report as its final output** to the orchestrator, which collects them and moves
to the next phase.

Sub-agents never talk to each other, so no message bus, shared config file, or
manual shutdown is needed. This lets the skill run on any CLI that supports
sub-agents, and fall back to sequential execution on those that don't.

## Dispatch mechanism

| Platform | Dispatch sub-agents | Parallel | Result delivery |
|---|---|---|---|
| **Claude Code** | `Task` tool (multiple calls in **one message** run in parallel) | ✅ true parallel | sub-agent's final response is the return value |
| **Codex CLI** | `spawn_agent` (needs `features.multi_agent=true`) + `wait_agent` to collect | ✅ true parallel (up to 6–8) | collected via `wait_agent` |
| **Gemini CLI** | `@generalist`, or sub-agents under `.gemini/agents/` | ⚠️ mostly sequential | sub-agent reports back |
| **Copilot CLI / no sub-agents** | none → the main model **plays each role in turn** in a single context | ❌ | produces each role's intermediate output directly |

## Principles

1. **Parallel when possible**: Claude Code and Codex dispatch all sub-agents of a
   phase at once.
2. **Sequential when not**: on Gemini / Copilot etc., the main model plays each
   role in turn, producing the **same structured** intermediate output, then
   proceeds to the next phase. Analytical quality is unchanged (same `slice`
   call, same prompt) — only slower.
3. **Return as output**: on every platform, sub-agents return their report as
   the "final response"; the orchestrator collects it directly — no
   `SendMessage` or message bus.
4. **No team state**: no `TeamCreate`, no reading a `config.json`, no
   `TaskCreate`/`TaskUpdate` claiming, no shutdown — these are Claude Code Agent
   Teams rituals this skill does not depend on.

## Other tool-name mapping (if a prompt needs to mention one)

| Purpose | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| Run shell | `Bash` | native shell | `run_shell_command` |
| Task tracking (optional) | `TodoWrite` | `update_plan` | `write_todos` |
| Fetch a web page's body (news analyst reads article text) | `WebFetch` | native web fetch | `web_fetch` |
| Web search (news analyst supplements recent news) | `WebSearch` | native web search | built-in search |
