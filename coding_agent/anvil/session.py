"""Session persistence: every task, reply, tool call, edit, approval and
verify result is appended to a JSONL transcript under <project>/.anvil/sessions/.

Design goals:
- append-only JSONL → crash-safe, greppable, diffable, trivially parseable
- full fidelity → the transcript alone can reconstruct the conversation
  (`--resume`) and feeds the self-improvement miner (anvil/improve.py)
"""

import json
import os
import time


def sessions_dir(root):
    return os.path.join(os.path.realpath(root), ".anvil", "sessions")


class Session:
    def __init__(self, root, session_id=None, meta=None):
        self.dir = sessions_dir(root)
        os.makedirs(self.dir, exist_ok=True)
        self.id = session_id or time.strftime("%Y%m%d-%H%M%S")
        self.path = os.path.join(self.dir, f"{self.id}.jsonl")
        if meta is not None and not os.path.exists(self.path):
            self._write({"kind": "meta", **meta})

    def _write(self, obj):
        obj.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def log_message(self, role, content):
        """Full-fidelity conversation record (used for resume)."""
        self._write({"kind": "msg", "role": role, "content": content})

    def log_event(self, event, payload):
        """UI/telemetry record (used by the improvement miner)."""
        self._write({"kind": "event", "event": event,
                     "payload": str(payload)[:4000]})


def read(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue   # tolerate a torn final line after a crash
    return out


def list_sessions(root):
    """Session file paths, oldest → newest."""
    d = sessions_dir(root)
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d))
            if f.endswith(".jsonl")]


def load_history(path):
    """Rebuild (meta, messages) from a transcript. The system prompt is NOT
    included — the caller regenerates it fresh (tools/skills may have changed)."""
    meta, msgs = {}, []
    for rec in read(path):
        if rec.get("kind") == "meta":
            meta = rec
        elif rec.get("kind") == "msg" and rec.get("role") != "system":
            msgs.append({"role": rec["role"], "content": rec.get("content", "")})
    return meta, msgs
