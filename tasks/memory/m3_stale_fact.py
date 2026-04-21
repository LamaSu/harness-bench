"""
M3 — Stale-Fact Rejection Under Knowledge Updates

When facts change, agent must use the LATEST fact AND recognize when a
stored memory is provably stale. Adversarial variant: surface BOTH old and
new fact in retrieved context.

Spec: docs/04-bench-spec.md §2.1.M3.
Datasets (cited from docs/01-corpus-catalog.md):
    - #9  LongMemEval (knowledge-updates axis, MIT)
    - #16 FreshQA (temporal-rotating Q&A)
    - #17 RealTimeQA (weekly-updated)
    - #54 arXiv metadata (CC0; date-anchored)
    - Construction: harness-bench/M3-stale (synthesized 30-90 day timeline)
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from datetime import date
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]

    def task(fn):  # type: ignore[no-redef]
        return fn


def _generate_versioned_fact_timeline(
    n_facts: int = 7,
    timeline_days: int = 60,
    updates_per_fact_range: tuple[int, int] = (2, 5),
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Build a synthetic 30-90 day timeline of N facts updated 2-5x each.

    Each entry: {fact_id, version, value, effective_date, supersedes}.
    Used to construct M3 sample histories.
    """
    raise NotImplementedError(
        "tasks/memory/m3_stale_fact.py:_generate_versioned_fact_timeline "
        "— see docs/04-bench-spec.md §2.1.M3"
    )


def _build_adversarial_sample(
    timeline: list[dict[str, Any]],
    test_date: date,
    surface_old_too: bool = True,
) -> "Sample":
    """Build one M3 sample.

    If surface_old_too=True, the retrieval context will contain BOTH the
    superseded value and the latest value. Agent should detect contradiction
    AND pick latest.
    """
    raise NotImplementedError(
        "tasks/memory/m3_stale_fact.py:_build_adversarial_sample "
        "— see docs/04-bench-spec.md §2.1.M3"
    )


def _score_m3(
    last_write_accuracy: float,
    contradiction_f1: float,
) -> float:
    """M3_score = 0.6 * last_write_accuracy + 0.4 * contradiction_F1. See spec §2.1.M3."""
    raise NotImplementedError(
        "tasks/memory/m3_stale_fact.py:_score_m3 — see docs/04-bench-spec.md §2.1.M3"
    )


@task
def m3_stale_fact(
    n_samples: int = 50,
    pct_adversarial: float = 0.5,
    include_freshqa: bool = True,
    include_realtimeqa: bool = True,
) -> "Task":
    """Inspect AI Task for axis M3.

    Combines LongMemEval knowledge-updates slice + FreshQA + RealTimeQA +
    constructed timelines. Headline gate: >=90% last-write-wins AND >=80%
    contradiction-flag F1. See spec §2.1.M3.
    """
    raise NotImplementedError(
        "tasks/memory/m3_stale_fact.py:m3_stale_fact — see docs/04-bench-spec.md §2.1.M3"
    )


__all__ = [
    "m3_stale_fact",
]
