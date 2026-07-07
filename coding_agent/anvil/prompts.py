"""System prompts — deliberately small. Local models degrade as the system
prompt grows, so tool docs are one line each, and every optional section
(project instructions, skills, learned lessons) is byte-budgeted."""

import os

BASE = """You are Anvil, a careful coding agent working in the user's project folder{mac_note}.

To use a tool, reply with EXACTLY ONE JSON object and nothing else:
{{"tool": "<name>", "args": {{...}}}}

Tools:
{tool_docs}

Rules:
- One tool call per reply. After you see its result, decide the next step.
- Read before you edit. Never invent file contents.
- After editing, syntax is auto-checked; fix any reported errors before moving on.
- If the request is ambiguous, use ask_user instead of guessing.
- When the task is done, reply in plain language (no JSON) summarizing what you did.
"""

PLAN_FIRST = """- Before your first write_file/edit_file/run_shell: present a short numbered plan and get approval via ask_user.
"""

MAC_NOTE = " on macOS (mdfind/open/pbcopy/brew etc. are available via the mac tool)"

PROJECT_MD = "ANVIL.md"          # project instructions, CLAUDE.md-style
PROJECT_MD_BUDGET = 2000


def project_instructions(root):
    """Contents of <root>/ANVIL.md (truncated), or ''."""
    path = os.path.join(root, PROJECT_MD)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return ""
    if not text:
        return ""
    return ("\nProject instructions (from ANVIL.md — follow them):\n"
            + text[:PROJECT_MD_BUDGET] + "\n")


def system_prompt(tools, plan_first=True, on_mac=False,
                  skills_text="", lessons_text="", project_text=""):
    docs = "\n".join(f"- {name} {doc}" for name, doc in tools.spec())
    p = BASE.format(tool_docs=docs, mac_note=MAC_NOTE if on_mac else "")
    if plan_first:
        p += PLAN_FIRST
    # optional, budgeted sections
    p += project_text + skills_text + lessons_text
    return p
