# The desktop-style app (v1 spec)

A resident Mac app — not a terminal you have to keep open. This is the piece
nobody in open source does natively (Goose's app is Electron and generic).

## Shape

- **Menu-bar item** (always available) + a **main window** (chat + workbench).
- Drag a folder onto the icon → new project session scoped to that folder.
- **Notifications** when a long-running task finishes or needs approval.
- **Global hotkey** (e.g. ⌥Space) → quick task palette: "fix the failing test",
  "what does this repo do?"

## Main window layout

```
┌────────────────────────────────────────────────────────────┐
│ ● ● ●   Anvil — ~/code/myapp                    ⚙ model ▾ │
├───────────────┬────────────────────────────────────────────┤
│ Conversation  │  Workbench                                 │
│               │                                            │
│ user/agent    │  ┌ Plan ────────────────────────────────┐  │
│ turns, incl.  │  │ 1. read failing test        ✓        │  │
│ the agent's   │  │ 2. edit src/parser.py       ⏳ diff  │  │
│ reasoning &   │  │ 3. run tests                pending  │  │
│ clarifying    │  └──────────────────────────────────────┘  │
│ questions     │  ┌ Diff review ─────────────────────────┐  │
│               │  │  - old line          + new line      │  │
│               │  │        [ Approve ]  [ Edit ]  [ ✕ ]  │  │
│               │  └──────────────────────────────────────┘  │
├───────────────┴────────────────────────────────────────────┤
│  task input…                        [plan-first ✓] [send]  │
└────────────────────────────────────────────────────────────┘
```

The three UI primitives that make it "reason with the user":

1. **Plan card** — numbered steps with live status; user can strike a step.
2. **Diff review** — every write is a reviewable diff with Approve/Reject.
3. **Question dialog** — `ask_user` becomes a native sheet, options as buttons.

## Tech choice

| Option | Verdict |
|---|---|
| **Tauri 2 (Rust + web UI)** | **Chosen for v1.** ~10 MB app, native menus/notifications, sidesteps Electron bloat; core stays the Python process (spawned, JSON-RPC over stdio) so CLI and app share one brain. |
| Swift/SwiftUI | The v2 endgame (tightest Keychain/Shortcuts/Spotlight integration), but slower to iterate and locks contributors to Xcode. |
| Electron | No — 250 MB and the Goose path; our differentiator is *native*. |

## Protocol between shell and core

The CLI already speaks turn-based JSON events (`plan`, `tool_call`,
`approval_request`, `diff`, `question`, `final`). The shell subscribes to the
same stream — one core, two frontends, zero drift.

## Mac integration checklist (v1)

- [ ] Keychain for API keys (cloud models optional)
- [ ] `mdfind` powered project-wide instant search
- [ ] Notification Center for run-finished / needs-approval
- [ ] `open -R` reveal-in-Finder from any file mention
- [ ] Login item (optional) + menu-bar quick palette
- [ ] Shortcuts.app actions ("Run Anvil task on clipboard")
- [ ] Model manager: detect Ollama/LM Studio/Rapid-MLX/oMLX, list installed
      models, one-click pull of a recommended coder model
