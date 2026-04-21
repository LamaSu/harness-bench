"""
METR time-horizon scorer.

Per METR's "Measuring AI Ability to Complete Long Tasks" methodology:
group samples into difficulty TIERS (1-min, 4-min, 15-min, 1-hr, 4-hr,
... by reference human completion time). Headline metric per harness =
the highest tier at which the harness achieves >=50% pass rate.

Spec: docs/04-bench-spec.md §4.2.
References:
    - METR / Kwa et al. 2025: "Measuring AI Ability to Complete Long Tasks"
    - Time-horizon doubling pattern visible across GPT-4 -> Claude 4.5
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from typing import Any

try:
    from inspect_ai.scorer import Score, Scorer, scorer, Target
    from inspect_ai.solver import TaskState
except ImportError:  # pragma: no cover
    Score = Any  # type: ignore[assignment,misc]
    Scorer = Any  # type: ignore[assignment,misc]
    Target = Any  # type: ignore[assignment,misc]
    TaskState = Any  # type: ignore[assignment,misc]

    def scorer(*_args, **_kwargs):  # type: ignore[no-redef]
        def deco(fn): return fn
        return deco

# Standard tier ladder (seconds of reference human completion time).
# Doubling sequence per spec §4.2.
TIER_LADDER_SECONDS: tuple[int, ...] = (
    60,        # 1 min
    240,       # 4 min
    900,       # 15 min
    3_600,     # 1 hr
    14_400,    # 4 hr
    57_600,    # 16 hr
    230_400,   # 64 hr
)

# Required pass-rate for tier-counts-as-passed.
PASS_THRESHOLD: float = 0.50


@scorer(metrics=["accuracy", "stderr"])
def time_horizon(
    tier_ladder_seconds: tuple[int, ...] = TIER_LADDER_SECONDS,
    pass_threshold: float = PASS_THRESHOLD,
    interpolate: bool = True,
) -> "Scorer":
    """Compute per-sample tier_passed bool, then aggregate to highest tier.

    Each sample.metadata MUST include `reference_human_seconds` (from
    dataset annotation OR from human calibration set). Aggregation:

        tier_pass_rate(t) = mean(passed for sample in tier t)
        headline_seconds  = max(t for t in ladder if tier_pass_rate(t) >= pass_threshold)

    If `interpolate=True`, log-interpolate between adjacent tiers for a
    smoother headline (METR's preferred presentation).
    """
    raise NotImplementedError(
        "scorers/time_horizon.py:time_horizon — see docs/04-bench-spec.md §4.2"
    )


__all__ = [
    "TIER_LADDER_SECONDS",
    "PASS_THRESHOLD",
    "time_horizon",
]
