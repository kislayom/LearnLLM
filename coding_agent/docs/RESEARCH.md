# Research: the open-source coding-agent landscape (mid-2026)

What exists, what each does best, and where Anvil goes beyond. Sources at the
bottom; figures are approximate as of July 2026.

## The players

| Project | Form | Stars | License | Local models | Take-away |
|---|---|---|---|---|---|
| **OpenCode** | terminal TUI | ~165k | MIT | strong (provider-agnostic) | Best TUI polish; dropped Claude Pro/Max login after an Anthropic dispute — a reminder to never depend on one vendor. |
| **OpenAI Codex CLI** | terminal | ~85k | Apache-2.0 | partial | Clean sandboxing story; OpenAI-centric. |
| **OpenHands** (ex-OpenDevin) | headless + web UI | ~75k | MIT | via LiteLLM (100+ providers incl. Ollama, llama.cpp, vLLM, MLX) | Strongest *autonomous* story: sandboxed runtime that browses, executes, edits end-to-end. Heavy; Docker-first; not Mac-native. |
| **Cline** | VS Code extension | ~62k | Apache-2.0 | 30+ providers incl. Ollama & LM Studio | Best editor-embedded agent; plan/act modes (validated our plan-first instinct). Tied to VS Code. |
| **Goose** (Block → Linux Foundation 2026) | CLI + desktop app | large | Apache-2.0 | good | Closest to our shape: *has a desktop app* and MCP extensions. But general automation focus, Electron shell, not Mac-specific, local models are supported rather than *designed for*. |
| **Aider** | terminal | large | Apache-2.0 | good | Git-native surgical edits; the diff/patch UX gold standard. Terminal-only, single-file mindset. |
| **Continue** | IDE extension | large | Apache-2.0 | good | Config-driven, good local support; autocomplete-centric. |
| **Crush** (Charm) | terminal TUI | mid | MIT | good | Beautiful terminal craft. |
| **Roo Code** | VS Code fork of Cline | ~24k | — | good | **Archived May 2026** — forks without a distinct thesis die. |

Also relevant: **Claude Code / Gemini CLI** (closed; Gemini CLI retiring June 2026
for a closed successor), **Cursor/Windsurf** (closed editors), **gptme**, **Plandex**,
**Forge**, **Pi**.

## The Mac local-inference stack (what we ride on)

- **Ollama 0.19+** (Mar 2026): Apple-Silicon inference now runs on **MLX**
  (Apple's array framework) instead of llama.cpp's Metal backend — big speedups;
  Macs are now arguably the best consumer local-LLM hardware.
- **Rapid-MLX**: MLX engine claiming ~4× Ollama speed, 0.08s cached TTFT, 17
  tool-call parsers, OpenAI-compatible. Ships a one-click Mac app.
- **oMLX**: native macOS inference server with **SSD-paged KV cache** (long-context
  TTFT from 30–90s down to <5s), continuous batching, drop-in API.
- **LM Studio**, **llama.cpp server**, **mlx-lm** — all speak the OpenAI API.

**Implication:** one `OpenAICompatAdapter` + one `OllamaAdapter` covers the whole
Mac local ecosystem. Models to target: Qwen2.5/3-Coder (7B–32B), DeepSeek-Coder,
Devstral, Codestral, Llama-3.x.

## What we take from each

- **Aider** → diff-first editing, git-aware commits, repo-map context.
- **Cline** → explicit **Plan / Act** modes with approval gates.
- **OpenHands** → the value of a real execution sandbox for autonomous runs.
- **Goose** → desktop-app distribution; extension system (MCP).
- **OpenCode** → provider-agnosticism as a survival trait; UI polish matters.
- **Rapid-MLX** → tolerant, multi-format tool-call parsing is *the* local-model
  unlock (they ship 17 parsers for a reason).

## The gaps = our thesis

1. **Local-model-first agent design.** Everyone *supports* local models; nobody
   *designs* for them. Tool protocols assume frontier-grade JSON discipline. We
   design the loop for 7B-class models: tolerant parsing + repair loops, tiny
   prompts, per-model capability tiers, context budgeting.
2. **True Mac-native desktop agent.** Goose's desktop app is Electron and
   platform-generic. Nobody does: menu-bar residency, Spotlight (`mdfind`) for
   instant repo search, Keychain for secrets, AppleScript/Shortcuts automation,
   notifications for long runs, drag-a-folder-in onboarding.
3. **Any-language syntax awareness, offline.** Tree-sitter grammars + per-language
   syntax checkers (`py_compile`, `node --check`, `swiftc -parse`, `go build`,
   `cargo check`, `tsc --noEmit`…) verify every edit *before* it lands — cheap
   guardrails matter twice as much when the model is small.
4. **Reason-with-the-user UX.** Plan → clarify → approve → act → verify, with
   diffs and rationale as first-class UI, not scrollback.

## Anti-goals (lessons from the graveyard)

- Not a VS Code fork (Roo Code died; the fork tax is real).
- Not vendor-locked (OpenCode/Anthropic dispute; Gemini CLI retirement).
- Not Docker-required on a laptop (OpenHands friction).
- Not another generic TUI — the differentiator is the *Mac app + local-first core*.

## Sources

- [Pinggy — Best open-source CLI coding agents (2026)](https://pinggy.io/blog/best_open_source_cli_coding_agents/)
- [Morph — open-source assistants ranked by stars/license/local support](https://www.morphllm.com/ai-coding-assistant-open-source)
- [Frontman — Cline / Roo Code / OpenHands / Kilo compared](https://frontman.sh/blog/best-open-source-ai-coding-tools-2026/)
- [awesome-cli-coding-agents directory](https://github.com/bradAGI/awesome-cli-coding-agents)
- [XDA — Ollama's new MLX engine on Mac](https://www.xda-developers.com/ollama-new-mlx-engine-local-llm-mac-twice-fast/)
- [Gingter — Ollama goes MLX (Apr 2026)](https://gingter.org/2026/04/23/ollama-goes-mlx/)
- [Rapid-MLX](https://github.com/raullenchai/Rapid-MLX) · [oMLX](https://omlx.ai/)
- [The New Stack — Ollama taps Apple's MLX](https://thenewstack.io/ollama-taps-apples-mlx/)
