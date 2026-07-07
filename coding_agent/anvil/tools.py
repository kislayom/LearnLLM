"""Tool registry: filesystem, search, shell, per-language syntax check, and
curated macOS helpers. Every tool returns a plain string (what the model sees).

Safety: tools that mutate state or run commands are marked needs_approval; the
agent routes those through the user's approval callback first.
"""

import os
import shutil
import subprocess
import sys

from .edits import EditError, apply_edit, unified_diff

# Output fed back to a (small-context) model is budgeted.
MAX_TOOL_OUTPUT = 8000


def _truncate(s, limit=MAX_TOOL_OUTPUT):
    if len(s) <= limit:
        return s
    head, tail = s[: limit // 2], s[-limit // 4:]
    return f"{head}\n... [{len(s) - len(head) - len(tail)} chars omitted] ...\n{tail}"


def _within(root, path):
    """Resolve path inside root; refuse escapes."""
    full = os.path.realpath(os.path.join(root, os.path.expanduser(path)))
    if not (full == os.path.realpath(root)
            or full.startswith(os.path.realpath(root) + os.sep)):
        raise ValueError(f"path escapes the project folder: {path}")
    return full


# --------------------------------------------------------------------------
# per-language syntax checkers: extension -> command template ({f} = file)
# picked so most need only a stock toolchain; missing tools degrade gracefully
SYNTAX_CHECKERS = {
    ".py":    [sys.executable, "-m", "py_compile", "{f}"],
    ".js":    ["node", "--check", "{f}"],
    ".mjs":   ["node", "--check", "{f}"],
    ".ts":    ["npx", "--no-install", "tsc", "--noEmit", "{f}"],
    ".json":  [sys.executable, "-m", "json.tool", "{f}"],
    ".sh":    ["bash", "-n", "{f}"],
    ".bash":  ["bash", "-n", "{f}"],
    ".zsh":   ["zsh", "-n", "{f}"],
    ".rb":    ["ruby", "-c", "{f}"],
    ".php":   ["php", "-l", "{f}"],
    ".swift": ["swiftc", "-parse", "{f}"],
    ".go":    ["gofmt", "-e", "{f}"],
    ".rs":    ["rustc", "--emit=metadata", "--edition", "2021", "-o",
               os.devnull, "{f}"],
    ".java":  ["javac", "-d", "/tmp", "{f}"],
    ".c":     ["cc", "-fsyntax-only", "{f}"],
    ".cpp":   ["c++", "-fsyntax-only", "{f}"],
    # .yaml/.yml are handled specially in t_check_syntax (needs PyYAML)
    ".lua":   ["luac", "-p", "{f}"],
    ".pl":    ["perl", "-c", "{f}"],
}

# commands whose *prefix* is hard-blocked in run_shell (v0 blunt safety)
BLOCKED_SHELL = ("sudo", "rm -rf /", "mkfs", "diskutil erase", "dd if=",
                 "shutdown", "reboot", "launchctl bootout system")

# curated mac verbs -> real commands ({q} = query/argument)
MAC_VERBS = {
    "spotlight":  "mdfind {q}",                   # instant index-backed search
    "open":       "open {q}",                     # file/url/app
    "open_app":   "open -a {q}",
    "reveal":     "open -R {q}",                  # show in Finder
    "copy":       "pbcopy",                       # stdin -> clipboard
    "paste":      "pbpaste",
    "notify":     'osascript -e \'display notification "{q}" with title "Anvil"\'',
    "brew_search": "brew search {q}",
    "brew_install": "brew install {q}",           # needs approval like any shell
    "sysinfo":    "sw_vers",
}


class Tools:
    def __init__(self, root=".", approve=None, shell_timeout=60, skills=None):
        """approve(description) -> bool; None means auto-deny mutations."""
        self.root = os.path.realpath(root)
        self.approve = approve
        self.shell_timeout = shell_timeout
        self.skills = skills or {}

    # ---- registry ---------------------------------------------------------
    def spec(self):
        """One-line docs per tool — kept tiny on purpose for small models."""
        return [
            ("read_file", '{"path"} -> file contents (with line numbers)'),
            ("write_file", '{"path","content"} -> create/overwrite file [approval]'),
            ("edit_file", '{"path","old","new"} -> replace exact text once [approval]'),
            ("list_dir", '{"path"?} -> entries in a directory'),
            ("search", '{"pattern","path"?} -> matching lines in files'),
            ("run_shell", '{"cmd"} -> run a shell command in the project [approval]'),
            ("check_syntax", '{"path"} -> syntax-check a file (auto-detect language)'),
            ("run_tests", '{} -> detect and run the project\'s test suite'),
            ("mac", '{"verb","arg"?} -> macOS helper; verbs: ' + ", ".join(MAC_VERBS)),
            ("ask_user", '{"question"} -> ask the user; use when unsure or for plan approval'),
        ] + ([("skill", '{"name"} -> load a skill\'s full instructions')]
             if self.skills else [])

    def needs_approval(self, name, args):
        if name in ("write_file", "edit_file", "run_shell"):
            return True
        if name == "mac" and args.get("verb") in ("brew_install", "open_app"):
            return True
        return False

    def run(self, name, args):
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return f"ERROR: unknown tool '{name}'. Available: " + \
                   ", ".join(n for n, _ in self.spec())
        try:
            return _truncate(fn(**args))
        except TypeError as e:
            return f"ERROR: bad arguments for {name}: {e}"
        except ValueError as e:
            return f"ERROR: {e}"
        except OSError as e:
            return f"ERROR: {e}"

    # ---- filesystem -------------------------------------------------------
    def t_read_file(self, path):
        full = _within(self.root, path)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(f"{i+1:5d}| {l}" for i, l in enumerate(lines)) or "(empty file)"

    def t_write_file(self, path, content):
        full = _within(self.root, path)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        note = self._auto_syntax(full)
        return f"wrote {len(content)} chars to {path}" + note

    def t_edit_file(self, path, old, new):
        full = _within(self.root, path)
        with open(full, "r", encoding="utf-8") as f:
            text = f.read()
        try:
            new_text, strategy = apply_edit(text, old, new)
        except EditError as e:
            return f"ERROR: {e}"
        with open(full, "w", encoding="utf-8") as f:
            f.write(new_text)
        diff = unified_diff(path, text, new_text)
        note = self._auto_syntax(full)
        return f"edited {path} (match: {strategy})\n{diff}" + note

    def t_list_dir(self, path="."):
        full = _within(self.root, path)
        entries = sorted(os.listdir(full))
        out = []
        for e in entries:
            if e in (".git", "node_modules", "__pycache__", ".venv", ".anvil"):
                out.append(f"{e}/ (skipped)")
                continue
            p = os.path.join(full, e)
            out.append(e + "/" if os.path.isdir(p) else e)
        return "\n".join(out) or "(empty)"

    # ---- search: rg -> grep -> python ------------------------------------
    def t_search(self, pattern, path="."):
        full = _within(self.root, path)
        if shutil.which("rg"):
            cmd = ["rg", "-n", "--no-heading", "-m", "50", pattern, full]
        elif shutil.which("grep"):
            cmd = ["grep", "-rn", "-m", "50", pattern, full]
        else:
            return self._py_search(pattern, full)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode > 1:
            return f"ERROR: {r.stderr.strip()}"
        hits = r.stdout.replace(self.root + os.sep, "")
        return hits or "no matches"

    def _py_search(self, pattern, full):
        hits = []
        for dirpath, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules",
                                                    "__pycache__", ".venv",
                                                    ".anvil")]
            for fn in files:
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if pattern in line:
                                rel = os.path.relpath(p, self.root)
                                hits.append(f"{rel}:{i}:{line.rstrip()}")
                                if len(hits) >= 50:
                                    return "\n".join(hits)
                except OSError:
                    continue
        return "\n".join(hits) or "no matches"

    # ---- shell ------------------------------------------------------------
    def t_run_shell(self, cmd):
        low = cmd.strip().lower()
        for bad in BLOCKED_SHELL:
            if low.startswith(bad) or f" {bad}" in f" {low}":
                return f"ERROR: blocked for safety: contains '{bad}'"
        r = subprocess.run(cmd, shell=True, cwd=self.root, capture_output=True,
                           text=True, timeout=self.shell_timeout)
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return f"exit={r.returncode}\n{out.strip() or '(no output)'}"

    # ---- syntax -----------------------------------------------------------
    def t_check_syntax(self, path):
        full = _within(self.root, path)
        ext = os.path.splitext(full)[1].lower()
        if ext in (".yaml", ".yml"):
            return self._check_yaml(full)
        tmpl = SYNTAX_CHECKERS.get(ext)
        if not tmpl:
            return f"no syntax checker registered for '{ext}' — skipped"
        cmd = [c.replace("{f}", full) for c in tmpl]
        if not shutil.which(cmd[0]) and not os.path.exists(cmd[0]):
            return f"checker '{cmd[0]}' not installed — skipped"
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return f"syntax OK ({os.path.basename(cmd[0])})"
        return f"SYNTAX ERRORS:\n{(r.stderr or r.stdout).strip()}"

    def _check_yaml(self, full):
        try:
            import yaml  # optional; PyYAML ships with many toolchains
        except ImportError:
            return "PyYAML not installed — skipped"
        try:
            with open(full, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
            return "syntax OK (yaml)"
        except yaml.YAMLError as e:
            return f"SYNTAX ERRORS:\n{e}"

    def _auto_syntax(self, full):
        res = self.t_check_syntax(os.path.relpath(full, self.root))
        return "" if res.startswith(("syntax OK", "no syntax checker",
                                     "checker", "PyYAML")) else f"\n{res}"

    # ---- tests ------------------------------------------------------------
    def t_run_tests(self):
        from . import verify
        cmd = verify.detect(self.root)
        if not cmd:
            return ("no test command detected (looked for package.json, "
                    "Cargo.toml, go.mod, Makefile, pytest/test_*.py, or a "
                    ".anvil-test override file)")
        ok, report = verify.run(self.root, cmd,
                                timeout=self.shell_timeout * 5)
        return ("PASS\n" if ok else "FAIL\n") + report

    # ---- mac helpers ------------------------------------------------------
    def t_mac(self, verb, arg=""):
        if sys.platform != "darwin":
            return f"ERROR: mac tool requires macOS (this is {sys.platform})"
        tmpl = MAC_VERBS.get(verb)
        if not tmpl:
            return "ERROR: unknown verb. Available: " + ", ".join(MAC_VERBS)
        cmd = tmpl.replace("{q}", arg)
        return self.t_run_shell(cmd)

    # ---- skills -----------------------------------------------------------
    def t_skill(self, name):
        s = self.skills.get(name)
        if not s:
            return ("ERROR: unknown skill '" + str(name) + "'. Available: "
                    + (", ".join(sorted(self.skills)) or "(none)"))
        return f"SKILL[{s['name']}] — follow these instructions:\n{s['body']}"

    # ---- user channel ------------------------------------------------------
    def t_ask_user(self, question):
        if self.approve is None:
            return "(no user available; proceed with your best judgment and say what you assumed)"
        return self.approve(f"QUESTION: {question}", question_mode=True)
