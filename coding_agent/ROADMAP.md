# Roadmap

## v0 — core (✅ this commit)
- [x] Reason-act loop with plan-first + approval gates
- [x] Tolerant tool-call parser + repair loop (the local-model unlock)
- [x] Ollama + OpenAI-compatible adapters (covers LM Studio, llama.cpp, MLX, Rapid-MLX, oMLX, vLLM, cloud)
- [x] Tools: fs, search (rg→grep→python), shell (gated + blocklist), any-language `check_syntax`, mac verbs, ask_user
- [x] Model capability tiers (small/mid/large) with per-tier behavior
- [x] Offline test suite (23 tests, stdlib only)

## v0.5 — the engine (✅ this commit)
- [x] Robust edit application: exact → trailing-ws → indent-shift → fuzzy, with diff previews
- [x] Repo map context (symbols per language, task-relevance ranked, byte-budgeted)
- [x] Verify loop: detect & run the project's test command; feed failures back until green
- [x] Git safety: checkpoint before first mutation, `anvil undo` (refuses user commits)
- [x] History compaction for long tasks (collapse old tool results)
- [x] Eval harness: 6 graded tasks in sandboxed dirs, pass-rate table per model
- [ ] Model manager: detect Ollama/LM Studio, recommend + pull a coder model
- [ ] Streaming output in the CLI
- [ ] Grow evals to 25+ tasks; run nightly across 3 local models; tune prompts per tier against the numbers

## v1 — the desktop app (docs/DESKTOP.md)
- [ ] Tauri 2 shell wrapping the core over JSON-RPC (stdio)
- [ ] Plan card / diff review / question sheet UI primitives
- [ ] Menu-bar residency, drag-a-folder onboarding, notifications
- [ ] Keychain secrets; per-project folder scoping
- [ ] `mdfind`-backed instant project search

## v2 — beyond the field
- [ ] Tree-sitter: symbol-level context packs and precise any-language edits
- [ ] MCP client → inherit the MCP tool ecosystem
- [ ] Model router: small model for navigation turns, big model for design turns
- [ ] Multi-step background tasks with notification-based approvals
- [ ] Shortcuts.app + Services integration ("Anvil this selection")
- [ ] Swift/SwiftUI native shell (v2 endgame)
