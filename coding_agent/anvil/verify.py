"""Verification loop: detect the project's test command, run it, and feed
failures back to the model. This closes the act→verify loop that separates
"made an edit" from "did the job".
"""

import json
import os
import re
import shutil
import subprocess

TAIL = 3000  # chars of test output the model sees


def detect(root):
    """Best-guess test command for this project, or None."""
    def has(*parts):
        return os.path.exists(os.path.join(root, *parts))

    # explicit override wins
    if has(".anvil-test"):
        with open(os.path.join(root, ".anvil-test"), "r", encoding="utf-8") as f:
            cmd = f.read().strip()
            return cmd or None

    if has("package.json"):
        try:
            with open(os.path.join(root, "package.json"), "r",
                      encoding="utf-8") as f:
                pkg = json.load(f)
            script = (pkg.get("scripts") or {}).get("test", "")
            if script and "no test specified" not in script:
                return "npm test --silent"
        except (OSError, json.JSONDecodeError):
            pass
    if has("Cargo.toml"):
        return "cargo test --quiet"
    if has("go.mod"):
        return "go test ./..."
    if has("Makefile"):
        try:
            with open(os.path.join(root, "Makefile"), "r",
                      encoding="utf-8", errors="ignore") as f:
                if re.search(r"^test\s*:", f.read(), re.MULTILINE):
                    return "make test"
        except OSError:
            pass
    # python last: most repos have *some* .py files
    if has("pytest.ini") or has("setup.cfg") or has("pyproject.toml"):
        if shutil.which("pytest"):
            return "pytest -q"
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules",
                                                "__pycache__", ".venv",
                                                ".anvil")]
        if any(f.startswith("test_") and f.endswith(".py") for f in files):
            if shutil.which("pytest"):
                return "pytest -q"
            return "python3 -m unittest discover -s . -p 'test_*.py'"
    return None


def run(root, cmd, timeout=300):
    """Run the test command. Returns (ok: bool, report: str)."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"$ {cmd}\nTIMED OUT after {timeout}s"
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    if len(out) > TAIL:
        out = "...\n" + out[-TAIL:]
    ok = r.returncode == 0
    return ok, f"$ {cmd}\nexit={r.returncode}\n{out or '(no output)'}"
