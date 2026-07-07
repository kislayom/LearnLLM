"""Tolerant tool-call extraction.

Local models emit almost-JSON: prose around the object, ```json fences, single
quotes, trailing commas, `None/True/False`. This module accepts all of that.
The contract with the model is: one JSON object per turn shaped like

    {"tool": "<name>", "args": {...}}

Returns:
    (call, error) where exactly one is non-None.
    call  = {"tool": str, "args": dict}
    error = human-readable string to feed back to the model for self-repair.
    (None, None) means "no tool call present" → the reply is a final answer.
"""

import json
import re

_FENCE_RE = re.compile(r"```(?:json|tool|tool_call)?\s*(.*?)```", re.DOTALL)


def _json_candidates(text):
    """Yield substrings most likely to be the tool-call object, best first."""
    # 1. fenced blocks
    for m in _FENCE_RE.finditer(text):
        yield m.group(1).strip()
    # 2. brace-balanced spans that contain a "tool" key
    for start in [m.start() for m in re.finditer(r"\{", text)]:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    span = text[start:i + 1]
                    if re.search(r"['\"]tool['\"]", span):
                        yield span
                    break


def _repair(s):
    """Fix the classic local-model JSON mistakes."""
    s = s.strip()
    # python literals
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "null", s)
    # trailing commas
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s


def _repair_quotes(s):
    """Last resort: single-quoted keys/strings -> double quotes (careful-ish)."""
    if '"' in s:
        return s
    return re.sub(r"'", '"', s)


def extract_tool_call(text):
    """Extract one tool call from a model reply. See module docstring."""
    if not text:
        return None, None

    mentions_tool = re.search(r"['\"]tool['\"]\s*:", text)
    if not mentions_tool:
        return None, None  # final answer

    last_err = None
    for cand in _json_candidates(text):
        for attempt in (cand, _repair(cand), _repair_quotes(_repair(cand))):
            try:
                obj = json.loads(attempt)
            except (json.JSONDecodeError, ValueError) as e:
                last_err = str(e)
                continue
            if not isinstance(obj, dict):
                continue
            if "tool" not in obj:
                continue
            name = obj.get("tool")
            args = obj.get("args", obj.get("arguments", {})) or {}
            if not isinstance(name, str) or not name.strip():
                return None, "the \"tool\" field must be a non-empty string"
            if not isinstance(args, dict):
                return None, "\"args\" must be a JSON object"
            return {"tool": name.strip(), "args": args}, None

    return None, (
        "could not parse your tool call as JSON"
        + (f" ({last_err})" if last_err else "")
    )


def repair_hint(error):
    """One-line correction message sent back to the model."""
    return (
        f"TOOL_ERROR: {error}. Reply with exactly one JSON object like "
        '{"tool": "<name>", "args": {...}} and nothing else, '
        "or give your final answer with no JSON."
    )
