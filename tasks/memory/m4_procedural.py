"""
M4 — Procedural Memory & Skill Reuse

Agent learns a skill in Session N (e.g., "to deploy this user's PCC
project, push to `lamasu` not `origin` because origin is suspended") and
must REAPPLY it in Session N+M without being re-taught.

Spec: docs/04-bench-spec.md §2.1.M4.
Datasets (cited from docs/01-corpus-catalog.md):
    - #25 AppWorld (Apache-2.0; 750 multi-step workflows across 9 apps)
    - #20 TAU-bench (MIT)
    - #21 tau2-bench (MIT)
    - #22 OSWorld (MIT/Apache-2.0)
    - #23 WebArena (MIT)
    - #24 VisualWebArena (MIT)
    - #27 ToolBench (Apache-2.0)
    - #28 PlanBench
    - #8  SWE-Lancer (#36 MLE-bench for ML pipelines)
    - Real-trace: #52 GH Archive, #57 CommitPackFT (MIT)
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


def _build_session_pair(
    training_task: dict[str, Any],
    recall_task: dict[str, Any],
    distractor_skills: list[dict[str, Any]] | None = None,
) -> tuple["Sample", "Sample"]:
    """Construct a (training, recall) Sample pair.

    Training Sample requires discovering a non-obvious procedure.
    Recall Sample (>=1 day OR >=1000 turns later) tests whether the agent
    INVOKES the saved procedure.
    """
    raise NotImplementedError(
        "tasks/memory/m4_procedural.py:_build_session_pair — see docs/04-bench-spec.md §2.1.M4"
    )


def _score_skill_reuse(
    first_time_seconds: float,
    repeat_time_seconds: float,
    invocation_observed: bool,
    correct_skill_picked: bool,
) -> float:
    """M4_score = 1 - (repeat_time / first_time). See spec §2.1.M4."""
    raise NotImplementedError(
        "tasks/memory/m4_procedural.py:_score_skill_reuse — see docs/04-bench-spec.md §2.1.M4"
    )


@task
def m4_procedural(
    n_samples: int = 50,
    distractor_count: int = 5,
    session_gap_turns: int = 1000,
    include_appworld: bool = True,
    include_tau_bench: bool = True,
) -> "Task":
    """Inspect AI Task for axis M4.

    Two-phase: Phase A trains the skill, Phase B (after gap) tests reuse.
    Headline gate: first-time-vs-repeat performance gap <= 2x.
    """
    raise NotImplementedError(
        "tasks/memory/m4_procedural.py:m4_procedural — see docs/04-bench-spec.md §2.1.M4"
    )


__all__ = [
    "m4_procedural",
]
