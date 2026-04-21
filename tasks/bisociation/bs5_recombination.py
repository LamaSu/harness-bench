"""
BS5 — Solution Recombination (E-MAGIC-style)

Given two existing partial solutions to two SEPARATE problems, agent must
recombine PARTS of each to solve a THIRD problem neither covers alone.
This is the classic "innovation by recombination" capability and the
purest test of bisociation.

Spec: docs/04-bench-spec.md §2.3.BS5.
Datasets (cited from docs/01-corpus-catalog.md):
    - Construction: harness-bench/E-MAGIC (purpose-built, MIT) — 50
      hand-curated triples (problem_A_solution, problem_B_solution,
      problem_C_target) with gold recombination + 3 distractor
      recombinations.
    - #28 PlanBench (planning primitives)
    - #25 AppWorld (multi-tool composition)
    - #5  BigCodeBench (code recombination ground truth)
    - #57 CommitPackFT (MIT; PR refactor patterns as recombination examples)
Notes:
    The "E-MAGIC" name is provisional. No existing public benchmark covers
    this; entire dataset is construction-required.
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]

    def task(fn):  # type: ignore[no-redef]
        return fn

# Recombination difficulty per spec §2.3.BS5.
RECOMBINATION_DIFFICULTY: tuple[str, ...] = (
    "additive",      # bolt parts together; minimal adaptation
    "substitutive",  # swap component X of A for component Y of B
    "transformative",# both halves require non-trivial adaptation to fit
)


@dataclass
class RecombinationProbe:
    """One BS5 sample."""
    probe_id: str
    problem_a_summary: str
    solution_a_artifact: str   # working code/plan/protocol
    problem_b_summary: str
    solution_b_artifact: str
    target_problem_c: str       # the new problem to solve
    gold_recombination: str     # canonical solution drawing from A and B
    distractor_recombinations: list[str]   # plausible-but-wrong (3+)
    difficulty: str


def _grade_recombination(
    agent_solution: str,
    probe: RecombinationProbe,
) -> dict[str, float]:
    """Grade with: structural_overlap_with_gold, executes_correctly_on_C,
    parts_drawn_from_both_A_and_B, novelty_above_distractors.

    `executes_correctly_on_C` requires a sandbox runner for code/plan
    artifacts — see harnesses/base.py::Harness.initialize.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs5_recombination.py:_grade_recombination "
        "— see docs/04-bench-spec.md §2.3.BS5"
    )


def _score_bs5(
    structural_overlap: float,
    executes_correctly: float,
    parts_drawn_from_both: float,
    novelty_above_distractors: float,
) -> float:
    """BS5_score = 0.25 * structural_overlap + 0.40 * executes_correctly
    + 0.20 * parts_drawn_from_both + 0.15 * novelty_above_distractors.
    See spec §2.3.BS5.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs5_recombination.py:_score_bs5 "
        "— see docs/04-bench-spec.md §2.3.BS5"
    )


@task
def bs5_recombination(
    n_samples: int = 50,
    difficulty_mix: dict[str, float] | None = None,
    require_sandbox_execution: bool = True,
) -> "Task":
    """Inspect AI Task for axis BS5.

    Triples (A, B -> C) where C requires recombining parts of A and B.
    Headline gate: executes_correctly >= 50% on additive, >= 30% on
    substitutive, >= 15% on transformative.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs5_recombination.py:bs5_recombination "
        "— see docs/04-bench-spec.md §2.3.BS5"
    )


__all__ = [
    "RECOMBINATION_DIFFICULTY",
    "RecombinationProbe",
    "bs5_recombination",
]
