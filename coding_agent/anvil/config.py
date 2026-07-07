"""Agent configuration, model capability tiers, and endpoint profiles."""

import json
import os
import sys
from dataclasses import dataclass, field


# name-substring -> tier; used to trim behavior for small models
TIER_HINTS = {
    "small": ("7b", "8b", "3b", "1.5b", "mini", "phi"),
    "large": ("70b", "405b", "claude", "gpt-4", "gpt-5", "deepseek-v3",
              "o3", "opus", "sonnet"),
}

# context budget (approx tokens) the loop keeps history under, per tier
CONTEXT_BUDGET = {"small": 6000, "mid": 16000, "large": 48000}


def guess_tier(model_name):
    n = (model_name or "").lower()
    for hint in TIER_HINTS["small"]:
        if hint in n:
            return "small"
    for hint in TIER_HINTS["large"]:
        if hint in n:
            return "large"
    return "mid"


@dataclass
class AgentConfig:
    max_steps: int = 25            # tool-loop budget per task
    plan_first: bool = True        # present a plan + get approval before writes
    auto_approve: bool = False     # True = don't gate writes/shell (dangerous)
    repair_attempts: int = 3       # malformed-tool-call repair round-trips
    shell_timeout: int = 60
    tier: str = "mid"
    on_mac: bool = field(default_factory=lambda: sys.platform == "darwin")

    # context engine
    use_repo_map: bool = True
    repo_map_chars: int = 3000
    context_tokens: int = 16000    # history compaction budget

    # act -> verify loop
    auto_verify: bool = True
    max_verify_rounds: int = 2

    # safety
    git_checkpoints: bool = True

    @classmethod
    def for_model(cls, model_name, **overrides):
        tier = guess_tier(model_name)
        cfg = cls(tier=tier, context_tokens=CONTEXT_BUDGET[tier])
        if tier == "small":
            cfg.max_steps = 15       # keep loops short; small models wander
            cfg.repair_attempts = 4  # ...but forgive more formatting slips
            cfg.repo_map_chars = 1500
        for k, v in overrides.items():
            setattr(cfg, k, v)
        return cfg


# ---------------------------------------------------------------- profiles
# Named LLM endpoints so remote servers are first-class:
#   ~/.anvil/config.json  and  <project>/.anvil/config.json  (project wins)
# {
#   "profiles": {
#     "studio":  {"backend": "openai", "model": "qwen3-coder-32b",
#                 "url": "http://mac-studio.local:1234/v1"},
#     "cloud":   {"backend": "openai", "model": "some-model",
#                 "url": "https://api.example.com/v1",
#                 "api_key_env": "MY_API_KEY"}
#   },
#   "default_profile": "studio"
# }
# API keys are NEVER stored in the file — only the env-var name that holds one.

def config_paths(root):
    return [os.path.expanduser("~/.anvil/config.json"),
            os.path.join(os.path.realpath(root), ".anvil", "config.json")]


def load_profiles(root, paths=None):
    """Returns (profiles: dict, default_name: str|None). Malformed files are
    skipped rather than fatal — config must never brick the agent."""
    profiles, default = {}, None
    for p in (paths if paths is not None else config_paths(root)):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        profiles.update(data.get("profiles") or {})
        default = data.get("default_profile", default)
    return profiles, default


def resolve_profile(profile, root, paths=None):
    """profile name -> {backend, model, url, api_key} (api_key from env)."""
    profiles, default = load_profiles(root, paths)
    name = profile or default
    if not name:
        return None
    if name not in profiles:
        raise ValueError(f"unknown profile '{name}'; available: "
                         + (", ".join(sorted(profiles)) or "(none)"))
    p = dict(profiles[name])
    key_env = p.pop("api_key_env", None)
    p["api_key"] = os.environ.get(key_env) if key_env else None
    p.setdefault("backend", "openai")
    return p
