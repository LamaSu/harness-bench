"""
BS3 — Cross-Paper Synthesis (research-to-engineering bridge)

Two papers from different fields (e.g., a neuroscience paper on attention
dynamics + a systems paper on cache eviction) describe related mechanisms.
Agent must read both, identify the shared structure, and propose a
synthesis (e.g., "neural attention's eviction policy is analogous to
LRU; both fail under burst patterns; here's a unified eviction signal").

Spec: docs/04-bench-spec.md §2.3.BS3.
Datasets (cited from docs/01-corpus-catalog.md):
    - #54 arXiv metadata (CC0; cross-discipline pair sampling)
    - #55 PubMed Central OA (CC-BY; biomedical corpus)
    - #50 Wikipedia (CC-BY-SA; concept definitions)
    - #14 MMLongBench-Doc (research-only; figure+caption synthesis primitives)
    - Construction: harness-bench/BS3-cross-paper (purpose-built, MIT) —
      60 paired-paper samples with gold synthesis curated by domain experts.
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

# Field pairs sampled per spec §2.3.BS3 (one paper from each side).
DEFAULT_FIELD_PAIRS: tuple[tuple[str, str], ...] = (
    ("cs.AI", "q-bio.NC"),       # ML <-> neuroscience
    ("cs.OS", "cs.NE"),          # systems <-> neural
    ("q-fin.TR", "q-bio.PE"),    # markets <-> ecology
    ("cs.DC", "physics.bio-ph"), # distributed <-> biophysics
    ("cs.CR", "math.PR"),        # security <-> probability
)


@dataclass
class CrossPaperProbe:
    """One BS3 sample."""
    probe_id: str
    paper_a_arxiv_id: str
    paper_b_arxiv_id: str
    field_pair: tuple[str, str]
    gold_shared_structure: str         # canonical 1-2 sentence shared mechanism
    gold_synthesis_bullets: list[str]  # 3-5 expected synthesis points
    distractor_paper_ids: list[str]    # plausible-but-unrelated papers in context


def _select_paper_pair(
    field_pair: tuple[str, str],
    arxiv_metadata_path: str,
    seed: int = 0,
) -> tuple[str, str]:
    """Sample one paper from each field, with distance constraints.

    Constraint: papers must be from same year +/- 2; cited together in
    < 5 papers (forces novel synthesis, not lookup of an existing review).
    """
    raise NotImplementedError(
        "tasks/bisociation/bs3_cross_paper.py:_select_paper_pair "
        "— see docs/04-bench-spec.md §2.3.BS3"
    )


def _score_synthesis(
    agent_synthesis: str,
    probe: CrossPaperProbe,
) -> dict[str, float]:
    """3-judge LLM panel scores: structural_match, novelty, factual_grounding.

    Each judge in {opus, sonnet, gpt-5}; report Krippendorff alpha alongside.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs3_cross_paper.py:_score_synthesis "
        "— see docs/04-bench-spec.md §2.3.BS3"
    )


def _score_bs3(
    structural_match: float,
    novelty: float,
    factual_grounding: float,
) -> float:
    """BS3_score = 0.4 * structural_match + 0.3 * novelty + 0.3 * factual_grounding.
    See spec §2.3.BS3.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs3_cross_paper.py:_score_bs3 "
        "— see docs/04-bench-spec.md §2.3.BS3"
    )


@task
def bs3_cross_paper(
    n_samples: int = 60,
    field_pairs: tuple[tuple[str, str], ...] = DEFAULT_FIELD_PAIRS,
    n_distractor_papers: int = 5,
) -> "Task":
    """Inspect AI Task for axis BS3.

    Two papers (different fields) + N distractors. Agent produces a
    synthesis. Headline gate: structural_match >= 60%; factual_grounding
    >= 80%; judge agreement Krippendorff alpha >= 0.6.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs3_cross_paper.py:bs3_cross_paper "
        "— see docs/04-bench-spec.md §2.3.BS3"
    )


__all__ = [
    "DEFAULT_FIELD_PAIRS",
    "CrossPaperProbe",
    "bs3_cross_paper",
]
