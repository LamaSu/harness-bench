"""
M1 — Cross-Window Tool-Output Retrieval ("12 contexts ago")

Information surfaced as a tool-call result N context windows ago, plus
information from a research paper read M windows ago, must be combined when
the relevant cue arrives. Distance buckets {1-5, 6-20, 21-100, 100+}; varied
distractor density.

Spec: docs/04-bench-spec.md §2.1.M1.
Datasets (cited from docs/01-corpus-catalog.md):
    - #9  LongMemEval (xiaowu0162/longmemeval-cleaned, MIT)
    - #10 LoCoMo (snap-research/locomo)
    - #12 RULER (NVIDIA/RULER, Apache-2.0) — synthetic distance-graded
    - #26 AssistantBench (Apache-2.0)
    - #6  RepoBench v1.1 (CC-BY-NC-ND-4.0 — eval-only)
Status: STUB — to be implemented by next agent (implementer-* family).
"""
from __future__ import annotations

from typing import Any

# Inspect AI imports — wrapped in try/except so this stub remains importable
# even when inspect_ai isn't yet on PYTHONPATH (CI smoke during scaffold phase).
try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample, hf_dataset
    from inspect_ai.solver import generate
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]

    def task(fn):  # type: ignore[no-redef]
        return fn

# Distance buckets used by the M1 scorer
DISTANCE_BUCKETS: list[tuple[int, int | None]] = [
    (1, 5),
    (6, 20),
    (21, 100),
    (101, None),  # 100+
]

# Bucket weights in the headline M1_score; heavier weight on harder buckets.
def bucket_weight(bucket_size: int) -> float:
    """log2(bucket_size) per spec §2.1.M1."""
    raise NotImplementedError(
        "tasks/memory/m1_cross_window.py:bucket_weight — see docs/04-bench-spec.md §2.1.M1"
    )


def _record_to_sample(record: dict[str, Any]) -> "Sample":
    """Adapt a LongMemEval record into an Inspect AI Sample.

    Inserts a 12-context-window chain by replaying `record["history"]`
    interleaved with N synthetic tool calls (web search / code exec stubs)
    so the answer-relevant tool result lives at the configured distance.
    """
    raise NotImplementedError(
        "tasks/memory/m1_cross_window.py:_record_to_sample — see docs/04-bench-spec.md §2.1.M1"
    )


def _build_distractor_chain(
    base_history: list[dict[str, Any]],
    distance_window: int,
    distractor_density: float = 0.5,
) -> list[dict[str, Any]]:
    """Build the N-window chain that buries the relevant tool result.

    :param base_history: original LongMemEval session history
    :param distance_window: target distance (in context windows) at which
        the answer-relevant tool result should sit
    :param distractor_density: fraction of intervening turns that are
        semantically-similar but irrelevant (default 0.5)
    """
    raise NotImplementedError(
        "tasks/memory/m1_cross_window.py:_build_distractor_chain — see docs/04-bench-spec.md §2.1.M1"
    )


@task
def m1_cross_window(
    distance_buckets: list[tuple[int, int | None]] = DISTANCE_BUCKETS,
    samples_per_bucket: int = 50,
    distractor_density: float = 0.5,
) -> "Task":
    """Inspect AI Task for axis M1.

    Loads LongMemEval, restructures each record into a 12-context-window
    chain, runs the harness, and scores via the M1_score formula
    (bucket-weighted accuracy + retrieval_recall@k + usage_precision +
    final_correctness). See docs/04-bench-spec.md §2.1.M1 for full spec.
    """
    raise NotImplementedError(
        "tasks/memory/m1_cross_window.py:m1_cross_window — see docs/04-bench-spec.md §2.1.M1"
    )


__all__ = [
    "DISTANCE_BUCKETS",
    "bucket_weight",
    "m1_cross_window",
]
