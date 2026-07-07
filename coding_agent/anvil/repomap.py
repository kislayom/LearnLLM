"""Repo map: give the model a codebase overview that fits a small context.

Instead of dumping files, we extract symbols (functions/classes/types) per
language with lightweight patterns and emit a compact tree:

    src/parser.py
      12: class Parser
      88: def parse_block
    src/cli.js
      4: function main

When a task is provided, files are ranked by keyword relevance so the map
spends its byte budget on what matters. (Tree-sitter replaces the regexes in
v2; the interface stays the same.)
"""

import os
import re

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", "target", ".next", ".cache", "vendor", ".tox", "eggs"}

CODE_EXTS = {
    ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".php",
    ".swift", ".m", ".java", ".kt", ".c", ".h", ".cpp", ".hpp", ".cs", ".sh",
    ".lua", ".pl", ".scala", ".ex", ".exs", ".zig",
}

# extension -> regex whose group 1 (or whole match) names a symbol
SYMBOL_PATTERNS = {
    ".py":    re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)"),
    ".rb":    re.compile(r"^\s*(?:def|class|module)\s+([\w.]+)"),
    ".go":    re.compile(r"^func\s+(?:\([^)]+\)\s*)?(\w+)|^type\s+(\w+)"),
    ".rs":    re.compile(r"^\s*(?:pub\s+)?(?:fn|struct|enum|trait|impl)\s+(\w+)"),
    ".swift": re.compile(r"^\s*(?:public\s+|private\s+|internal\s+)?(?:func|class|struct|enum|protocol|extension)\s+(\w+)"),
    ".java":  re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:class|interface|enum)\s+(\w+)|^\s*(?:public|private|protected)[\w<>\[\] ]+\s+(\w+)\s*\("),
    ".kt":    re.compile(r"^\s*(?:fun|class|object|interface)\s+(\w+)"),
    ".c":     re.compile(r"^[\w*]+\s+\**(\w+)\s*\([^;]*$"),
    ".sh":    re.compile(r"^\s*(?:function\s+)?(\w+)\s*\(\)\s*\{"),
    ".lua":   re.compile(r"^\s*(?:local\s+)?function\s+([\w.:]+)"),
    ".php":   re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|static\s+)*(?:function|class)\s+(\w+)"),
}
_JS = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+(\w+)|class\s+(\w+)"
    r"|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\(|function))")
for _e in (".js", ".mjs", ".ts", ".tsx", ".jsx"):
    SYMBOL_PATTERNS[_e] = _JS
for _e in (".cpp", ".hpp", ".h", ".cs", ".m", ".scala", ".ex", ".exs", ".zig"):
    SYMBOL_PATTERNS.setdefault(_e, SYMBOL_PATTERNS[".c"])

_WORD = re.compile(r"[a-zA-Z_]{3,}")


def _symbols(path, ext, max_lines=4000, max_syms=40):
    pat = SYMBOL_PATTERNS.get(ext)
    if not pat:
        return []
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if i > max_lines or len(out) >= max_syms:
                    break
                m = pat.match(line)
                if m:
                    name = next((g for g in m.groups() if g), None)
                    if name:
                        out.append((i, name))
    except OSError:
        return []
    return out


def scan(root, max_files=400):
    """Walk the tree -> [(relpath, size, [(line, symbol), ...]), ...]"""
    found = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and not d.startswith("."))
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            if ext not in CODE_EXTS:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            found.append((rel, size, _symbols(full, ext)))
            if len(found) >= max_files:
                return found
    return found


def _score(task_words, rel, syms):
    hay = (rel + " " + " ".join(s for _, s in syms)).lower()
    hits = sum(1 for w in task_words if w in hay)
    return hits + (0.2 if syms else 0)   # tiny bias toward files with symbols


def build_map(root, task=None, budget_chars=4000, max_files=400):
    """Compact, relevance-ranked repo overview string (may be empty)."""
    files = scan(root, max_files=max_files)
    if not files:
        return ""
    if task:
        words = {w.lower() for w in _WORD.findall(task)}
        files.sort(key=lambda t: -_score(words, t[0], t[2]))

    lines, used = [], 0
    for rel, size, syms in files:
        entry = [rel if not syms else f"{rel}:"]
        entry += [f"  {ln}: {name}" for ln, name in syms[:12]]
        block = "\n".join(entry) + "\n"
        if used + len(block) > budget_chars:
            lines.append(f"... (+{len(files) - len(lines)} more files)")
            break
        lines.append(block.rstrip())
        used += len(block)
    return "\n".join(lines)
