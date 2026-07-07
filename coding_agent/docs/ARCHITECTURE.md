# Architecture

The core is a small, dependency-free Python package (`anvil/`) that a desktop
shell wraps later. Everything is designed around one constraint: **it must work
well with a 7B local model**, and simply get better with bigger ones.

```
┌───────────────────────────── Desktop shell (v1, docs/DESKTOP.md) ─────────┐
│  menu-bar app · chat window · plan & diff review · approvals · settings   │
└──────────────────────────────▲────────────────────────────────────────────┘
                               │ JSON-RPC over stdio (same protocol as CLI)
┌──────────────────────────────┴────────────────────────────────────────────┐
│                            AGENT CORE (anvil/)                            │
│                                                                           │
│  agent.py    reason-act loop: plan → clarify → approve → act → verify     │
│  parser.py   tolerant tool-call extraction + repair feedback              │
│  prompts.py  minimal system prompt, per-tier variants                     │
│  tools.py    registry: fs / search / shell / syntax / mac / ask_user      │
│  llm.py      OllamaAdapter · OpenAICompatAdapter (LM Studio, llama.cpp,   │
│              MLX, vLLM, or any cloud) · ScriptedAdapter (tests)           │
│  config.py   safety defaults, approval policy, model tiers                │
└───────────────────────────────────────────────────────────────────────────┘
```

## 1. The loop (`agent.py`)

Classic reason-act, with two Anvil-specific twists:

```
history = [system, user_task]
repeat up to max_steps:
    reply = model(history)
    call  = parser.extract_tool_call(reply)
    if call is None:            → final answer; stop
    if call is malformed:       → append repair hint; continue   # twist 1
    if tool needs approval:     → ask user (UI callback)          # twist 2
    result = tools.run(call)
    append (reply, tool result) to history
```

**Twist 1 — repair, don't crash.** Local models emit almost-JSON: single quotes,
prose around the object, wrong fences, trailing commas. `parser.py` accepts all
of that; when even it fails, the agent sends back a one-line correction
("Your tool call was invalid: <err>. Reply with exactly one JSON object …")
instead of erroring out. Empirically this rescues most 7B failures.

**Twist 2 — reason with the user.** Config `plan_first=True` (default) makes the
model present a numbered plan and call `ask_user` for approval before its first
write/shell action. `ask_user` is also how the model resolves ambiguity — the
prompt explicitly rewards asking over guessing.

## 2. Tool protocol (`parser.py`, `prompts.py`)

One tool call per turn, as a single JSON object — the simplest thing a small
model can do reliably:

```json
{"tool": "read_file", "args": {"path": "src/main.py"}}
```

- Accepted forms: raw JSON anywhere in the reply, ```json / ```tool fences,
  single-quoted "JSON", the first `{…}` block containing a `"tool"` key.
- Exactly one call per turn → no partial-parallel state to corrupt.
- Tool docs are one line each in the system prompt; schemas stay tiny.
- **Why not native/OpenAI function-calling?** It's a per-server/per-model
  lottery locally (each runtime parses tool tokens differently — Rapid-MLX
  ships 17 parsers for a reason). A text protocol we control works on
  *everything*, including bare `llama.cpp`. When a backend advertises reliable
  native tool calling we can upgrade per-model (see tiers).

## 3. Model tiers (`config.py`)

The same agent, three trims — set per model, auto-detected later:

| Tier | Typical models | Behavior changes |
|---|---|---|
| `small` (≤8B) | qwen2.5-coder:7b, llama3.x-8b | shortest prompt, 1 tool/turn, aggressive repair, plan capped at 3 steps, syntax-check after *every* edit |
| `mid` (9–34B) | qwen3-coder:32b, devstral | fuller prompt, repo-map context, multi-file plans |
| `large` (70B+/cloud) | deepseek-v3, claude, gpt | native tool calling if available, long-horizon plans, parallel exploration |

## 4. Tools (`tools.py`)

| Tool | Notes |
|---|---|
| `read_file`, `write_file`, `edit_file` | `edit_file` is exact-match replace → safe, diffable; writes gated by approval |
| `list_dir`, `search` | search prefers `rg`, falls back to `grep`, then pure Python — works on a stock Mac |
| `run_shell` | approval-gated; cwd-scoped; timeout; output truncated to protect small contexts |
| `check_syntax` | **the any-language guardrail**: picks a checker by extension — `python -m py_compile`, `node --check`, `swiftc -parse`, `go vet`, `cargo check`, `tsc`, `ruby -c`, `php -l`, `bash -n`, `javac`… degrades gracefully when a toolchain isn't installed |
| `mac` | curated macOS verbs: `mdfind` (Spotlight search — instant, index-backed), `open`/`open -a`, `pbcopy`/`pbpaste`, `osascript`, `brew`, `xcodebuild`, `launchctl`, notifications |
| `ask_user` | the clarify/approve channel; surfaces as a dialog in the desktop shell |

Every edit is followed by an automatic `check_syntax` on the touched file
(small models make syntax slips; catching them locally costs one subprocess,
not a model round-trip).

## 5. Safety model

- Two write gates: config `auto_approve=False` (default) and per-call user
  approval with the exact command/diff shown.
- Shell runs are cwd-scoped with a timeout; obviously destructive patterns
  (`rm -rf /`, `sudo`, disk utilities) are hard-blocked in v0.
- The desktop shell adds macOS sandbox-style scoping per project folder.
- Secrets live in Keychain (shell) / env (CLI) — never in config files.

## 6. Context strategy (local models have small windows)

- Tool outputs truncated with head+tail sampling and a byte budget.
- A **repo map** (paths + signatures, tree-sitter later) instead of file dumps.
- History compaction: older tool results collapse to one-line summaries once
  the loop moves on.

## 7. Roadmap hooks (v1+)

- Tree-sitter grammars for symbol-level context and precise edits any-language.
- MCP client support → inherit the whole MCP tool ecosystem.
- Git integration: auto-branch per task, commit-per-approved-change (Aider-style).
- Verification loop: run the project's tests after edits, feed failures back.
- Model router: small model for navigation/search turns, big model for design
  turns — cuts local latency dramatically.
