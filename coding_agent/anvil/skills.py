"""Skills: reusable markdown instruction packs, Claude-Code style.

A skill is a .md file. Optional front-matter names and describes it:

    ---
    name: release
    description: how to cut a release of this project
    ---
    1. bump the version in pyproject.toml
    2. ...

Search order (later wins, so project overrides global):
    ~/.anvil/skills/*.md         — personal, all projects
    <project>/.anvil/skills/*.md — project-specific
    <project>/skills/*.md        — conventional location, if it holds .md files

Skill names+descriptions are listed in the system prompt (one line each);
the model loads a body on demand via the `skill` tool, and the user can
inject one with `/skill <name>` in the REPL.
"""

import os
import re

_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
MAX_SKILL_CHARS = 6000
MAX_LISTED = 12


def parse_skill(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    name = os.path.splitext(os.path.basename(path))[0]
    desc, body = "", text
    m = _FRONT.match(text)
    if m:
        header, body = m.groups()
        for line in header.splitlines():
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.strip()
            if k == "name" and v:
                name = v
            elif k == "description" and v:
                desc = v
    else:
        first = text.strip().splitlines()[0] if text.strip() else ""
        if first.startswith("#"):
            desc = first.lstrip("# ").strip()
    return {"name": name, "description": desc or name,
            "body": body.strip()[:MAX_SKILL_CHARS], "path": path}


def skill_dirs(root):
    return [
        os.path.expanduser("~/.anvil/skills"),
        os.path.join(os.path.realpath(root), ".anvil", "skills"),
        os.path.join(os.path.realpath(root), "skills"),
    ]


def load_skills(root):
    """name -> skill dict; later directories override earlier ones."""
    out = {}
    for d in skill_dirs(root):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".md"):
                s = parse_skill(os.path.join(d, fn))
                if s:
                    out[s["name"]] = s
    return out


def prompt_lines(skills):
    """Compact listing for the system prompt."""
    if not skills:
        return ""
    lines = [f"- {s['name']}: {s['description'][:80]}"
             for s in list(skills.values())[:MAX_LISTED]]
    return ("\nSkills (load one with the skill tool when relevant):\n"
            + "\n".join(lines) + "\n")
