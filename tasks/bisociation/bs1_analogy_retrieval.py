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
    - Construction: harness-bench/AnalogyBench (purpose-built, MIT).
      Authored 15 hand-written cross-domain analogies covering
      SE<->immunology, urban-planning<->networks, ML<->evolutionary biology,
      finance<->pricing, UX<->DoE, ops<->stigmergy, robotics<->biomechanics,
      pipelines<->coding-theory, monetary policy<->control theory,
      software<->HAZOP, security<->actuarial-EVT, quantum<->music theory,
      inventory<->caching, ICU<->SRE-alerting, systems-biology<->sparse-ID.
    - #50 Wikipedia dumps (CC-BY-SA; analogy source corpus)

Note on source choice: AnalogyBench was not HF-resident at construction
time (2026-04-21); ConceptARC tests same-rule-grid analogies, which is
within-visual-domain, not the cross-domain-discipline transfer BS-1
needs. Per docs/03 Appendix Axis->Dataset table, the fallback is
harness-bench/AnalogyBench (authored). This file loads it from
corpus/bs/bs1.jsonl.

Status: IMPLEMENTED (v0.2) by impl-india.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample, json_dataset
    from inspect_ai.solver import generate
    from inspect_ai.scorer import model_graded_qa
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]
    json_dataset = None  # type: ignore[assignment]
    generate = None  # type: ignore[assignment]
    model_graded_qa = None  # type: ignore[assignment]

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

# Corpus location — one JSONL row per sample.
CORPUS_PATH: Path = (
    Path(__file__).parent.parent.parent / "corpus" / "bs" / "bs1.jsonl"
)


@dataclass
class AnalogyProbe:
    """One BS1 sample (kept for downstream scorer type-safety)."""

    probe_id: str
    source_problem: str           # in domain A
    source_domain: str
    target_domain: str
    gold_analogy_summary: str     # canonical analogous solution
    structural_features: list[str]  # e.g., ["feedback-loop", "phase-transition"]
    distance_class: str           # "near" | "far"


def _row_to_sample(row: dict[str, Any]) -> "Sample":
    """Adapt one BS-1 JSONL row into an Inspect AI Sample.

    Row schema (see corpus/bs/bs1.jsonl):
        id, axis, prompt, context, target, rubric, difficulty,
        construction_source.

    The `prompt` already encodes the source problem + the instruction to
    retrieve a cross-domain analog. `context` is an optional list of
    framing tags that we splice in only when present (authored samples
    do include them).
    """
    context_lines = row.get("context") or []
    context_block = (
        "\n\nContext:\n- " + "\n- ".join(context_lines)
        if context_lines
        else ""
    )
    prompt = f"{row['prompt']}{context_block}"

    return Sample(
        input=prompt,
        target=str(row["target"]),
        metadata={
            "axis": "BS-1",
            "rubric": row["rubric"],
            "id": row["id"],
            "difficulty": row.get("difficulty"),
            "construction_source": row.get("construction_source"),
            "license_tag": "MIT",
        },
    )


def _score_bs1(
    retrieval_recall: float,
    structural_f1: float,
    novelty_judge: float,
) -> float:
    """BS1_score = 0.3 * retrieval_recall + 0.4 * structural_F1 + 0.3 * novelty_judge.

    Sub-scores are computed downstream by scorers/ from the raw
    model_graded_qa judgment + the rubric text in metadata. This
    helper exists so callers can combine them with a single formula.
    """
    return (
        0.3 * retrieval_recall
        + 0.4 * structural_f1
        + 0.3 * novelty_judge
    )


BS1_JUDGE_INSTRUCTIONS = (
    "You are grading a cross-domain analogy retrieval. Use the rubric in "
    "metadata.rubric verbatim. Award full credit only when ALL rubric "
    "conditions are met; award partial credit when the minimum subset "
    "specified in the rubric is met; otherwise award no credit. Always "
    "explain the mapping you observed in one sentence before grading."
)


@task
def bs1_analogy_retrieval(
    max_samples: int = 15,
) -> "Task":
    """Inspect AI Task for axis BS1.

    Authored cross-domain analogy set — 15 samples spanning near (intra-
    discipline family) and far (cross-discipline) pairs. Headline gate:
    structural_F1 >= 60% on far pairs; novelty_judge agreement
    (Krippendorff alpha) >= 0.6.

    :param max_samples: cap on samples used (corpus has 15).
    """
    if json_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running BS-1 task."
        )

    ds = json_dataset(
        str(CORPUS_PATH),
        sample_fields=_row_to_sample,
        limit=max_samples,
    )

    return Task(
        dataset=ds,
        solver=generate(),
        scorer=model_graded_qa(
            instructions=BS1_JUDGE_INSTRUCTIONS,
            partial_credit=True,
        ),
        metadata={
            "axis": "BS-1",
            "headline_scorer": "model_graded_qa",
            "corpus": str(CORPUS_PATH),
            "n_samples": max_samples,
            "construction_note": (
                "Authored corpus — AnalogyBench not HF-resident at build "
                "time; ConceptARC is within-visual-domain. Samples are "
                "hand-crafted cross-discipline structural analogies."
            ),
        },
    )


__all__ = [
    "DOMAIN_PAIRS_NEAR",
    "DOMAIN_PAIRS_FAR",
    "CORPUS_PATH",
    "AnalogyProbe",
    "bs1_analogy_retrieval",
]
