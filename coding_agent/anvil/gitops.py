"""Git safety layer: checkpoint before the agent mutates, undo with one command.

Anvil's contract with the user: *nothing the agent does is more than one
`undo` away from being reverted.* Checkpoints are ordinary commits prefixed
with [anvil] so they're visible, bisectable, and squashable.
"""

import subprocess

PREFIX = "[anvil]"


def _git(root, *args, check=False):
    r = subprocess.run(["git", "-C", root, *args],
                       capture_output=True, text=True, timeout=30)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r


def is_repo(root):
    try:
        r = _git(root, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def status(root):
    return _git(root, "status", "--porcelain").stdout


def head(root):
    return _git(root, "rev-parse", "--short", "HEAD").stdout.strip()


def last_message(root):
    return _git(root, "log", "-1", "--pretty=%s").stdout.strip()


def checkpoint(root, label):
    """Commit all current changes as an [anvil] checkpoint.

    Returns the short hash, or None if there was nothing to commit / not a
    repo. Never raises on a dirty-but-unmergeable tree — safety must not
    block the agent, only wrap it.
    """
    if not is_repo(root) or not status(root).strip():
        return None
    _git(root, "add", "-A")
    r = _git(root, "-c", "user.name=anvil", "-c", "user.email=anvil@local",
             "commit", "-m", f"{PREFIX} {label}")
    if r.returncode != 0:
        return None
    return head(root)


def undo_last(root):
    """Revert the most recent [anvil] checkpoint. Refuses to touch user commits."""
    if not is_repo(root):
        return "not a git repository"
    if not last_message(root).startswith(PREFIX):
        return ("last commit is not an anvil checkpoint "
                f"({last_message(root)!r}); refusing to reset")
    if status(root).strip():
        return "working tree has uncommitted changes; commit or stash them first"
    _git(root, "reset", "--hard", "HEAD~1", check=True)
    return f"reverted; HEAD is now {head(root)} ({last_message(root)!r})"


def diff_stat(root):
    return _git(root, "diff", "--stat", "HEAD").stdout or "(no changes)"
