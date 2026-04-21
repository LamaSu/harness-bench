"""
pass@1 scorer.

The bread-and-butter agentic-bench scoring primitive: did the harness's
final answer/diff/artifact pass the gold check on the FIRST attempt?
Used as a sub-component of every axis's headline metric.

Spec: docs/04-bench-spec.md §4.1.
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


@scorer(metrics=["accuracy", "stderr"])
def pass_at_1(
    grader: str = "exact",  # "exact" | "fuzzy" | "test_runner" | "judge_llm"
    judge_model: str | None = None,
) -> "Scorer":
    """Score one rollout per sample (k=1).

    Graders:
        - exact:       string equality after normalization
        - fuzzy:       token-set F1 with threshold from sample.metadata
        - test_runner: invoke `python -m pytest <test_file>` in sandbox
        - judge_llm:   single-judge LLM (specify judge_model)

    Notes:
        - For test_runner, sample.target is a path to a test file (or set
          of files) committed under corpus/<dataset>/tests/.
        - For judge_llm, prefer 3-judge ensemble via bisociation_judge
          for any axis that scores subjective output (BS1-BS5).
    """
    raise NotImplementedError(
        "scorers/pass_at_1.py:pass_at_1 — see docs/04-bench-spec.md §4.1"
    )


__all__ = [
    "pass_at_1",
]
