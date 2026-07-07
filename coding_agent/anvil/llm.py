"""Model backends. Pure stdlib (urllib) — no pip installs on a fresh Mac.

All adapters implement:  complete(messages) -> str
where messages = [{"role": "system"|"user"|"assistant", "content": str}, ...]
"""

import json
import time
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


RETRIES = 2          # transient-failure retries (5xx / connection reset)
BACKOFF = 1.5        # seconds, doubled per retry — remote servers hiccup


def _post_json(url, payload, headers=None, timeout=300):
    data = json.dumps(payload).encode("utf-8")
    last = None
    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            if e.code >= 500 and attempt < RETRIES:
                last = f"HTTP {e.code}"
                time.sleep(BACKOFF * (2 ** attempt))
                continue
            raise LLMError(f"HTTP {e.code} from {url}: {body}") from e
        except urllib.error.URLError as e:
            if attempt < RETRIES:
                last = str(e.reason)
                time.sleep(BACKOFF * (2 ** attempt))
                continue
            raise LLMError(
                f"cannot reach {url} ({e.reason}; retried {RETRIES}x). Is the "
                "model server running? e.g. `ollama serve`, LM Studio's local "
                "server, or your remote endpoint."
            ) from e
    raise LLMError(f"giving up on {url} after retries ({last})")


class OllamaAdapter:
    """Native Ollama API (http://localhost:11434). On Apple Silicon this runs
    on Ollama's MLX engine — currently the mainstream fast path on Macs."""

    def __init__(self, model, url="http://localhost:11434", temperature=0.2):
        self.model = model
        self.url = url.rstrip("/")
        self.temperature = temperature

    def complete(self, messages):
        out = _post_json(f"{self.url}/api/chat", {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        })
        try:
            return out["message"]["content"]
        except (KeyError, TypeError):
            raise LLMError(f"unexpected Ollama response: {str(out)[:300]}")


class OpenAICompatAdapter:
    """Any OpenAI-compatible endpoint: LM Studio (:1234), llama.cpp server,
    mlx-lm, Rapid-MLX, oMLX, vLLM — or a cloud provider if you want one."""

    def __init__(self, model, url="http://localhost:1234/v1", api_key=None,
                 temperature=0.2):
        self.model = model
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature

    def complete(self, messages):
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        out = _post_json(f"{self.url}/chat/completions", {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }, headers=headers)
        try:
            return out["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"unexpected response: {str(out)[:300]}")


class ScriptedAdapter:
    """Deterministic fake model for tests: replays a list of replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []  # message lists it was invoked with

    def complete(self, messages):
        self.calls.append(messages)
        if not self.replies:
            raise LLMError("ScriptedAdapter ran out of replies")
        return self.replies.pop(0)


def make_adapter(backend, model, url=None, api_key=None):
    if backend == "ollama":
        return OllamaAdapter(model, url or "http://localhost:11434")
    if backend == "openai":
        return OpenAICompatAdapter(model, url or "http://localhost:1234/v1",
                                   api_key=api_key)
    raise ValueError(f"unknown backend: {backend!r} (use 'ollama' or 'openai')")
