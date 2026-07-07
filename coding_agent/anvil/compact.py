"""History compaction so long tasks fit small local-model contexts.

Strategy: the system prompt, the original task, and the most recent exchanges
stay verbatim; older TOOL_RESULT messages collapse to their first line plus a
marker. The model keeps the *narrative* of what it did without paying for
every byte of old file dumps.
"""

KEEP_RECENT = 6          # last N messages never compacted
MIN_COMPACT_LEN = 300    # short messages aren't worth touching


def estimate_tokens(messages):
    """Cheap heuristic: ~4 chars/token."""
    return sum(len(m.get("content", "")) for m in messages) // 4


def compact(history, budget_tokens):
    """Return history, compacted in place if over budget."""
    if estimate_tokens(history) <= budget_tokens:
        return history

    # candidates: everything except system(0), task(1), and the recent tail
    for i in range(2, max(2, len(history) - KEEP_RECENT)):
        m = history[i]
        content = m.get("content", "")
        if len(content) < MIN_COMPACT_LEN:
            continue
        if m["role"] == "user" and content.startswith("TOOL_RESULT"):
            first = content.splitlines()[0]
            m["content"] = f"{first}\n[... output compacted; re-run the tool if needed]"
        elif m["role"] == "assistant" and len(content) > 800:
            m["content"] = content[:400] + "\n[... reasoning compacted]"
        if estimate_tokens(history) <= budget_tokens:
            break
    return history
