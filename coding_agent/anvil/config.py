"""Agent configuration and model capability tiers."""

import sys
from dataclasses import dataclass, field


# name-substring -> tier; used to trim behavior for small models
TIER_HINTS = {
    "small": ("7b", "8b", "3b", "1.5b", "mini", "phi"),
    "large": ("70b", "405b", "claude", "gpt-4", "gpt-5", "deepseek-v3",
              "o3", "opus", "sonnet"),
}


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

    @classmethod
    def for_model(cls, model_name, **overrides):
        tier = guess_tier(model_name)
        cfg = cls(tier=tier)
        if tier == "small":
            cfg.max_steps = 15       # keep loops short; small models wander
            cfg.repair_attempts = 4  # ...but forgive more formatting slips
        for k, v in overrides.items():
            setattr(cfg, k, v)
        return cfg
