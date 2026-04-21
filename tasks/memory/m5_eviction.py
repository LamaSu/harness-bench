"""
M5 — Working-Memory Eviction Under Budget Pressure

Real agents have token caps. When working memory exceeds budget, the agent
must intelligently evict — keep what's needed for the current task, drop
what's not. Almost no benchmark scores eviction-decision quality.

Spec: docs/04-bench-spec.md §2.1.M5.
Datasets (cited from docs/01-corpus-catalog.md):
    - #11 BABILong (lengths 0K -> 10M tokens; permissive PG19+bAbI)
    - #12 RULER (Apache-2.0; configurable length)
    - #13 InfiniteBench (12 tasks at 100K+; research-only)
    - #6  RepoBench v1.1 (CC-BY-NC-ND-4.0 — eval-only)
    - #7  Long Code Arena (mixed permissive)
    - #5  BigCodeBench (Apache-2.0; extended-context experiments)
    - #14 MMLongBench-Doc / #15 MileBench (research-only)
    - #1  SWE-bench Verified / #2 SWE-bench Pro (large repos)
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]

    def task(fn):  # type: ignore[no-redef]
        return fn

# Budgets per spec §2.1.M5
DEFAULT_BUDGETS_TOKENS: tuple[int, ...] = (
    32_000,
    128_000,
    512_000,
    1_000_000,
    # `inf` represented as -1 sentinel; runner picks model max
    -1,
)


def _plant_critical_facts(
    base_context: str,
    n_facts: int = 5,
    placement: str = "prelude",
) -> tuple[str, list[dict[str, Any]]]:
    """Plant N critical facts into the prelude that must survive eviction.

    :param placement: "prelude" | "midstream" | "scattered"
    :returns: (modified_context, list_of_planted_facts)
    """
    raise NotImplementedError(
        "tasks/memory/m5_eviction.py:_plant_critical_facts — see docs/04-bench-spec.md §2.1.M5"
    )


def _inject_distractor_traffic(
    context: str,
    target_size_tokens: int,
    distractor_density: float = 0.7,
) -> str:
    """Inflate context with distractor traffic to force eviction events.

    Used to stress the harness's compaction/eviction policy.
    """
    raise NotImplementedError(
        "tasks/memory/m5_eviction.py:_inject_distractor_traffic — see docs/04-bench-spec.md §2.1.M5"
    )


def _score_m5_curve(
    fact_preservation_per_budget: dict[int, float],
    eviction_decision_accuracy: float,
) -> dict[str, float]:
    """Compute M5 curve + AUC + eviction-decision accuracy. See spec §2.1.M5."""
    raise NotImplementedError(
        "tasks/memory/m5_eviction.py:_score_m5_curve — see docs/04-bench-spec.md §2.1.M5"
    )


@task
def m5_eviction(
    budgets_tokens: tuple[int, ...] = DEFAULT_BUDGETS_TOKENS,
    n_critical_facts: int = 5,
    samples_per_budget: int = 30,
    include_babilong: bool = True,
    include_ruler: bool = True,
) -> "Task":
    """Inspect AI Task for axis M5.

    Long task at controlled token budgets B. Plant 5 critical facts in
    early context. Inject distractor traffic to force eviction. Score:
    % critical facts preserved per B (curve over B values).

    Headline gate: at B=128K, >=80% critical facts preserved; degradation
    curve flatter than -10% per budget halving.
    """
    raise NotImplementedError(
        "tasks/memory/m5_eviction.py:m5_eviction — see docs/04-bench-spec.md §2.1.M5"
    )


__all__ = [
    "DEFAULT_BUDGETS_TOKENS",
    "m5_eviction",
]
