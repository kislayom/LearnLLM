# Roadmap

## v0 — core (✅ this commit)
- [x] Reason-act loop with plan-first + approval gates
- [x] Tolerant tool-call parser + repair loop (the local-model unlock)
- [x] Ollama + OpenAI-compatible adapters (covers LM Studio, llama.cpp, MLX, Rapid-MLX, oMLX, vLLM, cloud)
- [x] Tools: fs, search (rg→grep→python), shell (gated + blocklist), any-language `check_syntax`, mac verbs, ask_user
- [x] Model capability tiers (small/mid/large) with per-tier behavior
- [x] Offline test suite (23 tests, stdlib only)

## v0.5 — make it genuinely good day-to-day
- [ ] Repo map context (paths + signatures) instead of raw listings
- [ ] Git integration: auto-branch per task, commit per approved change, `/undo`
- [ ] Verify loop: detect & run the project's test command after edits, feed failures back
- [ ] History compaction for long tasks (collapse old tool results)
- [ ] Model manager: detect Ollama/LM Studio, recommend + pull a coder model
- [ ] Streaming output in the CLI

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
