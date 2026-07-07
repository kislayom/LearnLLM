"""Self-improvement: mine the session transcripts for recurring failure
patterns and distill them into lessons that get injected into future system
prompts.

Safety model: the agent never rewrites its own code on a schedule. What
mutates is *guidance* — `.anvil/learned.md` — which is bounded, dated,
human-readable, and reviewable. Two modes:

    deterministic (default) — offline pattern counters → threshold lessons
    --reflect               — additionally ask the configured model to distill
                              lessons from failure excerpts

Run manually (`anvil improve`) or on a schedule (`anvil improve --schedule`
writes a launchd plist on macOS / prints a cron line elsewhere).
"""

import os
import re
import time

from . import session

LEARNED = "learned.md"
MAX_LESSONS = 15
MAX_EXCERPTS = 30


# ---------------------------------------------------------------- mining
def mine(root):
    """Aggregate failure signals across all transcripts for a project."""
    stats = {
        "sessions": 0, "tasks": 0, "repairs": 0, "edit_misses": 0,
        "denials": 0, "verify_fails": 0, "syntax_errors": 0,
        "unknown_tools": 0, "max_steps": 0, "tool_calls": 0,
    }
    excerpts = []

    def note(kind, text):
        if len(excerpts) < MAX_EXCERPTS:
            excerpts.append(f"[{kind}] {text[:200]}")

    for path in session.list_sessions(root):
        stats["sessions"] += 1
        for rec in session.read(path):
            kind = rec.get("kind")
            if kind == "msg":
                c = rec.get("content", "")
                if rec.get("role") == "user" and not c.startswith(
                        ("TOOL_RESULT", "TOOL_ERROR", "VERIFY FAILED")):
                    stats["tasks"] += 1
                if c.startswith("TOOL_ERROR"):
                    stats["repairs"] += 1
                    note("malformed-tool-call", c)
                if c.startswith("VERIFY FAILED"):
                    stats["verify_fails"] += 1
                    note("verify-fail", c)
                if "ERROR: `old` text" in c:
                    stats["edit_misses"] += 1
                    note("edit-miss", c)
                if "DENIED by user" in c:
                    stats["denials"] += 1
                    note("denied", c)
                if "SYNTAX ERRORS" in c:
                    stats["syntax_errors"] += 1
                    note("syntax", c)
                if "unknown tool" in c:
                    stats["unknown_tools"] += 1
            elif kind == "event":
                if rec.get("event") == "tool_call":
                    stats["tool_calls"] += 1
                if rec.get("event") == "error" and \
                        "max_steps" in str(rec.get("payload", "")):
                    stats["max_steps"] += 1
    return stats, excerpts


# ------------------------------------------------------------- distilling
def lessons_from_stats(stats):
    """Deterministic, threshold-based lessons. Boring on purpose: they fire
    only on repeated evidence and read as direct instructions."""
    out = []
    if stats["repairs"] >= 3:
        out.append("Emit tool calls as ONE clean JSON object with double "
                   "quotes and no surrounding prose — malformed calls have "
                   f"needed repair {stats['repairs']} times.")
    if stats["edit_misses"] >= 3:
        out.append("Before edit_file, always read_file first and copy the "
                   "`old` text exactly, including indentation — "
                   f"{stats['edit_misses']} edits missed their target.")
    if stats["verify_fails"] >= 2:
        out.append("Run run_tests BEFORE declaring a task complete — "
                   f"verification failed {stats['verify_fails']} times after "
                   "premature completion claims.")
    if stats["denials"] >= 2:
        out.append("Users denied risky actions "
                   f"{stats['denials']} times: prefer smaller diffs, and use "
                   "ask_user to explain intent before large writes or shell "
                   "commands.")
    if stats["syntax_errors"] >= 2:
        out.append("Edits introduced syntax errors "
                   f"{stats['syntax_errors']} times: re-check brackets and "
                   "indentation, and fix reported errors immediately.")
    if stats["max_steps"] >= 2:
        out.append("Several tasks hit the step limit: make a shorter plan, "
                   "avoid re-reading unchanged files, and finish decisively.")
    if stats["unknown_tools"] >= 2:
        out.append("Only call tools listed in the system prompt — invented "
                   "tool names fail.")
    return out


REFLECT_PROMPT = """You are reviewing failure excerpts from past coding-agent \
sessions. Write at most 5 short, imperative lessons (one line each, starting \
with "- ") that would prevent these failures in future sessions. Be specific \
and practical; no praise, no fluff.

Excerpts:
{excerpts}
"""


def reflect_with_llm(llm, excerpts):
    if not excerpts:
        return []
    reply = llm.complete([{"role": "user", "content":
                           REFLECT_PROMPT.format(excerpts="\n".join(excerpts))}])
    lessons = [l.lstrip("- ").strip() for l in reply.splitlines()
               if l.strip().startswith("- ")]
    return [l for l in lessons if 15 <= len(l) <= 300][:5]


# ---------------------------------------------------------------- storage
def learned_path(root):
    return os.path.join(os.path.realpath(root), ".anvil", LEARNED)


def _parse_learned(path):
    if not os.path.exists(path):
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^- (?:\((\d{4}-\d{2}-\d{2})\) )?(.+)$", line.strip())
            if m:
                items.append((m.group(1) or "", m.group(2).strip()))
    return items


def update_learned(root, lessons, cap=MAX_LESSONS):
    """Merge new lessons into learned.md (dedup, newest last, bounded).
    Returns the number of genuinely new lessons added."""
    path = learned_path(root)
    existing = _parse_learned(path)
    seen = {text.lower() for _, text in existing}
    today = time.strftime("%Y-%m-%d")
    added = 0
    for l in lessons:
        if l.lower() not in seen:
            existing.append((today, l))
            seen.add(l.lower())
            added += 1
    existing = existing[-cap:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Learned lessons (auto-maintained by `anvil improve`)\n"
                "# Review freely — this file is injected into the system "
                "prompt.\n\n")
        for date, text in existing:
            f.write(f"- ({date}) {text}\n" if date else f"- {text}\n")
    return added


def learned_lessons(root, budget_chars=1200):
    """Lessons text for prompt injection ('' if none)."""
    texts = [t for _, t in _parse_learned(learned_path(root))]
    if not texts:
        return ""
    out, used = [], 0
    for t in reversed(texts):          # newest lessons win the budget
        if used + len(t) > budget_chars:
            break
        out.append(f"- {t}")
        used += len(t)
    return ("\nLessons from previous sessions (follow them):\n"
            + "\n".join(reversed(out)) + "\n")


# -------------------------------------------------------------- scheduling
PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>dev.anvil.improve</string>
  <key>ProgramArguments</key><array>
    <string>{python}</string><string>-m</string><string>anvil.cli</string>
    <string>improve</string><string>--dir</string><string>{workdir}</string>
  </array>
  <key>WorkingDirectory</key><string>{pkgdir}</string>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>{hour}</integer>
    <key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/anvil-improve.log</string>
  <key>StandardErrorPath</key><string>/tmp/anvil-improve.log</string>
</dict></plist>
"""


def gen_plist(python, workdir, pkgdir, hour=3):
    return PLIST.format(python=python, workdir=workdir, pkgdir=pkgdir,
                        hour=hour)


def install_schedule(python, workdir, pkgdir, hour=3, platform=None):
    """Install the nightly job. Returns a human-readable status message."""
    import sys as _sys
    platform = platform or _sys.platform
    if platform == "darwin":
        dest = os.path.expanduser(
            "~/Library/LaunchAgents/dev.anvil.improve.plist")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(gen_plist(python, workdir, pkgdir, hour))
        return (f"wrote {dest}\nactivate with:  launchctl load {dest}\n"
                f"(runs daily at {hour:02d}:30; logs to /tmp/anvil-improve.log)")
    line = (f"30 {hour} * * * cd {pkgdir} && {python} -m anvil.cli improve "
            f"--dir {workdir}")
    return f"not macOS — add this cron line yourself:\n{line}"
