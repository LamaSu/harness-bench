"""
Pareto frontier collector.

Per harness x axis, collects (capability, dollars, wallclock) triples and
emits the Pareto frontier. Why: a harness that scores 5pp lower at 1/10th
the cost is often the right choice for the workload — single-number
benchmarks hide this.

Spec: docs/04-bench-spec.md §4.3.
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ParetoPoint:
    """One (capability, cost, wallclock) measurement."""
    harness: str
    axis: str
    arm_signature: str    # serialized (layer, arm) tuple list
    capability: float     # axis-headline score in [0, 1]
    dollars: float
    wall_clock_seconds: float
    n_samples: int


def _is_dominated(p: ParetoPoint, others: list[ParetoPoint]) -> bool:
    """Point p is dominated iff some other point is >= on capability AND
    <= on both cost and wallclock, with strict inequality on at least one
    of the three.
    """
    raise NotImplementedError(
        "scorers/pareto.py:_is_dominated — see docs/04-bench-spec.md §4.3"
    )


def compute_frontier(points: list[ParetoPoint]) -> list[ParetoPoint]:
    """Filter `points` to the non-dominated set."""
    raise NotImplementedError(
        "scorers/pareto.py:compute_frontier — see docs/04-bench-spec.md §4.3"
    )


@scorer(metrics=["accuracy", "stderr"])
def pareto_collector(
    output_jsonl_path: str = "results/pareto.jsonl",
) -> "Scorer":
    """Inspect AI scorer that ALSO appends ParetoPoints to a JSONL file.

    The runner reads this JSONL post-sweep to render the per-axis Pareto
    plots and to compute the "best-in-class at $X" leaderboards.

    The scoring side just returns the per-sample capability number (so it
    is composable with the axis's primary scorer). The Pareto collection
    is a side effect via the JSONL appender.
    """
    raise NotImplementedError(
        "scorers/pareto.py:pareto_collector — see docs/04-bench-spec.md §4.3"
    )


__all__ = [
    "ParetoPoint",
    "compute_frontier",
    "pareto_collector",
]
