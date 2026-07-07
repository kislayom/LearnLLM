# Anvil — a Mac‑native coding agent (working name)

**Goal:** the best coding agent *for the Mac you already own* — desktop‑style app,
any programming language, deeply aware of macOS commands and conventions, and
designed **local‑model‑first** (Ollama / MLX / LM Studio / llama.cpp) so it works
brilliantly even with a 7B model and no internet.

> Status: v0 — working agent core (CLI) + architecture & research docs.
> The desktop shell (menu‑bar app) is specced in `docs/DESKTOP.md` and comes next.

## Why another coding agent?

The open‑source field is crowded (see [`docs/RESEARCH.md`](docs/RESEARCH.md)) but
almost everyone optimizes for *frontier cloud models* and *terminal/editor* UX.
The gaps we target:

1. **Local models are second‑class everywhere.** Most agents assume a model that
   emits perfect JSON tool calls. Small local models don't. Anvil's tool‑call
   protocol is designed for 7B–32B models: tolerant parsing, automatic repair
   loops, tiny prompts, capability tiers per model.
2. **Nobody is Mac‑native.** `mdfind`, `pbcopy`, `open -a`, `osascript`, `brew`,
   `launchctl`, `xcodebuild`, code‑signing — a Mac developer's real toolbox.
   Anvil treats macOS as a first‑class tool surface, not "generic POSIX".
3. **Agents act; they rarely *reason with you*.** Anvil defaults to
   plan‑→‑approve‑→‑act, asks a clarifying question when the request is
   ambiguous, and explains *why* before touching your files.
4. **Desktop‑style, not terminal‑only.** A resident app (menu bar + window):
   drag a folder in, see the plan, watch diffs, approve with a click.

## What works today (v0 core)

A zero‑dependency Python agent core you can run on any Mac (or Linux):

```bash
cd coding_agent
python3 -m anvil.cli --backend ollama --model qwen2.5-coder:7b
# or any OpenAI-compatible server (LM Studio, llama.cpp, MLX, vLLM):
python3 -m anvil.cli --backend openai --url http://localhost:1234/v1 --model local
```

- **Reason‑act loop** with plan‑first mode and user approval gates.
- **Tolerant tool calling** (`anvil/parser.py`): extracts tool calls from messy
  local‑model output (fenced blocks, prose around JSON, single quotes…), and
  sends repair feedback instead of crashing.
- **Tools:** read/write/edit files, list, search (ripgrep→grep→python fallback),
  shell (with approval), `check_syntax` (picks the right checker per language),
  `mac` helpers (mdfind/open/pbcopy…), `ask_user`.
- **Backends:** Ollama native API, any OpenAI‑compatible endpoint. No pip installs.

Run the tests (no dependencies needed):

```bash
python3 -m unittest discover -s coding_agent/tests -v
```

## Layout

```
coding_agent/
├── README.md            ← you are here
├── ROADMAP.md           ← v0 → v1 desktop app → v2 beyond
├── docs/
│   ├── RESEARCH.md      ← open-source landscape & what we take/skip
│   ├── ARCHITECTURE.md  ← agent core design (the important doc)
│   └── DESKTOP.md       ← the Mac desktop-style app spec
├── anvil/               ← the working core (pure stdlib Python)
│   ├── agent.py         ← reason-act loop
│   ├── parser.py        ← tolerant tool-call extraction + repair
│   ├── llm.py           ← Ollama / OpenAI-compatible adapters
│   ├── tools.py         ← file/search/shell/syntax/mac tools
│   ├── prompts.py       ← small prompts tuned for local models
│   ├── config.py        ← settings & safety defaults
│   └── cli.py           ← chat REPL
└── tests/               ← unittest suite (runs offline, fake model)
```

## Design principles

- **Local‑first, cloud‑optional.** Everything must work offline with a 7B model;
  a frontier model just makes it better.
- **Ask before acting.** Writes and shell commands are gated by approval unless
  the user opts into auto mode.
- **Small prompts win.** Local models degrade with long system prompts; tool
  docs are one line each and only included when relevant.
- **The Mac is the platform.** Ship as a real app; use the OS (Spotlight,
  clipboard, notifications, Keychain), don't fight it.
