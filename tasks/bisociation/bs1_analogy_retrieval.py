"""
BS1 — Cross-Domain Analogy Retrieval

Given a problem in domain A, retrieve a structurally analogous solution
from domain B (Koestler's "bisociation" — two unrelated matrices of
thought intersecting). Existing benchmarks test within-domain analogy
(IQ-test type); BS1 measures CROSS-domain transfer.

Spec: docs/04-bench-spec.md §2.3.BS1.
Datasets (cited from docs/01-corpus-catalog.md):
    - #29 ConceptARC (Apache-2.0; abstract analogies)
    - #30 FOLIO (logic primitives)
    - Construction: harness-bench/AnalogyBench (purpose-built, MIT) —
      100 hand-authored cross-domain analogies (biology->engineering,
      music->architecture, finance->ecology, etc.) with structural
      matches scored by 3-judge LLM panel + human calibration set.
    - #50 Wikipedia dumps (CC-BY-SA; analogy source corpus)
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

# Analogy distance categories per spec §2.3.BS1.
DOMAIN_PAIRS_NEAR: tuple[tuple[str, str], ...] = (
    ("software-engineering", "civil-engineering"),
    ("biology", "ecology"),
)
DOMAIN_PAIRS_FAR: tuple[tuple[str, str], ...] = (
    ("biology", "software-architecture"),
    ("music-composition", "urban-planning"),
    ("finance", "epidemiology"),
)


@dataclass
class AnalogyProbe:
    """One BS1 sample."""
    probe_id: str
    source_problem: str           # in domain A
    source_domain: str
    target_domain: str
    gold_analogy_summary: str     # canonical analogous solution
    structural_features: list[str]  # e.g., ["feedback-loop", "phase-transition"]
    distance_class: str           # "near" | "far"


def _retrieve_and_score(
    probe: AnalogyProbe,
    agent_response: str,
) -> dict[str, float]:
    """Score one agent response on BS1.

    Sub-scores:
        retrieval_recall   — did agent surface a candidate from target_domain?
        structural_F1      — overlap of structural_features in agent's mapping
        novelty_judge      — LLM-panel score in [0, 1] for non-trivial mapping
    """
    raise NotImplementedError(
        "tasks/bisociation/bs1_analogy_retrieval.py:_retrieve_and_score "
        "— see docs/04-bench-spec.md §2.3.BS1"
    )


def _score_bs1(
    retrieval_recall: float,
    structural_f1: float,
    novelty_judge: float,
) -> float:
    """BS1_score = 0.3 * retrieval_recall + 0.4 * structural_F1 + 0.3 * novelty_judge.
    See spec §2.3.BS1.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs1_analogy_retrieval.py:_score_bs1 "
        "— see docs/04-bench-spec.md §2.3.BS1"
    )


@task
def bs1_analogy_retrieval(
    n_samples: int = 100,
    near_to_far_ratio: float = 0.4,
    include_concept_arc: bool = True,
) -> "Task":
    """Inspect AI Task for axis BS1.

    Mix of near (intra-discipline) and far (cross-discipline) analogies.
    Headline gate: structural_F1 >= 60% on far pairs; novelty_judge agreement
    (Krippendorff alpha) >= 0.6.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs1_analogy_retrieval.py:bs1_analogy_retrieval "
        "— see docs/04-bench-spec.md §2.3.BS1"
    )


__all__ = [
    "DOMAIN_PAIRS_NEAR",
    "DOMAIN_PAIRS_FAR",
    "AnalogyProbe",
    "bs1_analogy_retrieval",
]
