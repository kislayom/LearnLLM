"""Robust edit application — the #1 real-world agent failure point.

Models (especially local ones) quote `old` text imperfectly: wrong indentation,
trailing spaces, a hallucinated blank line. Naive exact-match editing fails and
the agent burns turns re-reading files. We escalate through match strategies:

    1. exact            — substring match (must be unique)
    2. trailing-ws      — per-line match ignoring trailing whitespace
    3. indent-shift     — per-line match ignoring a *uniform* indentation offset
                          (the replacement is re-indented to match the file)
    4. fuzzy            — best line-window by difflib ratio (>= 0.9, unique)

Every successful edit reports which strategy was used, and callers get a
unified diff for preview/approval.
"""

import difflib


class EditError(ValueError):
    pass


def _find_line_window(file_lines, old_lines, normalize):
    """Return list of start indices where normalized windows match."""
    n = len(old_lines)
    if n == 0 or n > len(file_lines):
        return []
    target = [normalize(l) for l in old_lines]
    hits = []
    for i in range(len(file_lines) - n + 1):
        if [normalize(l) for l in file_lines[i:i + n]] == target:
            hits.append(i)
    return hits


def _common_indent(lines):
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    return min(indents) if indents else 0


def _reindent(new_lines, from_indent, to_indent):
    """Shift new_lines by the same offset that separated old from the file."""
    delta = to_indent - from_indent
    if delta == 0:
        return new_lines
    out = []
    for l in new_lines:
        if not l.strip():
            out.append(l)
        elif delta > 0:
            out.append(" " * delta + l)
        else:
            out.append(l[min(-delta, len(l) - len(l.lstrip())):])
    return out


def apply_edit(text, old, new):
    """Replace `old` with `new` in text. Returns (new_text, strategy).

    Raises EditError with an actionable message on failure.
    """
    if not old:
        raise EditError("`old` must be non-empty; use write_file to create files")

    # 1. exact ---------------------------------------------------------------
    n = text.count(old)
    if n == 1:
        return text.replace(old, new, 1), "exact"
    if n > 1:
        raise EditError(
            f"`old` text appears {n} times; include more surrounding context "
            "to make it unique")

    keepends = text.splitlines(keepends=True)
    file_lines = [l.rstrip("\n") for l in keepends]
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    trailing_nl = text.endswith("\n")

    def rebuild(start, end, replacement):
        merged = file_lines[:start] + replacement + file_lines[end:]
        return "\n".join(merged) + ("\n" if trailing_nl else "")

    # 2. ignore trailing whitespace -------------------------------------------
    hits = _find_line_window(file_lines, old_lines, str.rstrip)
    if len(hits) == 1:
        s = hits[0]
        return rebuild(s, s + len(old_lines), new_lines), "trailing-ws"
    if len(hits) > 1:
        raise EditError(f"`old` matches {len(hits)} locations; add more context")

    # 3. uniform indent shift --------------------------------------------------
    hits = _find_line_window(file_lines, old_lines, str.strip)
    if len(hits) == 1:
        s = hits[0]
        window = file_lines[s:s + len(old_lines)]
        shifted = _reindent(new_lines, _common_indent(old_lines),
                            _common_indent(window))
        return rebuild(s, s + len(old_lines), shifted), "indent-shift"
    if len(hits) > 1:
        raise EditError(f"`old` matches {len(hits)} locations; add more context")

    # 4. fuzzy window ----------------------------------------------------------
    n_win = len(old_lines)
    best_ratio, best_start, ties = 0.0, -1, 0
    old_joined = "\n".join(l.strip() for l in old_lines)
    for i in range(max(1, len(file_lines) - n_win + 1)):
        window = "\n".join(l.strip() for l in file_lines[i:i + n_win])
        r = difflib.SequenceMatcher(None, old_joined, window).ratio()
        if r > best_ratio + 1e-9:
            best_ratio, best_start, ties = r, i, 1
        elif abs(r - best_ratio) <= 1e-9:
            ties += 1
    if best_ratio >= 0.9 and ties == 1:
        s = best_start
        window = file_lines[s:s + n_win]
        shifted = _reindent(new_lines, _common_indent(old_lines),
                            _common_indent(window))
        return rebuild(s, s + n_win, shifted), f"fuzzy({best_ratio:.2f})"

    close = ""
    if best_start >= 0 and best_ratio >= 0.6:
        got = "\n".join(file_lines[best_start:best_start + n_win])
        close = (f"\nClosest match (ratio {best_ratio:.2f}) at line "
                 f"{best_start + 1}:\n{got[:400]}")
    raise EditError(
        "`old` text not found. Read the file and copy the exact text." + close)


def unified_diff(path, before, after, context=3):
    """Human-reviewable diff for approval UIs."""
    diff = difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}", n=context)
    return "".join(diff)
