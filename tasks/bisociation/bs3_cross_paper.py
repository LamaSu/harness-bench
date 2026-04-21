"""
BS3 — Cross-Paper Synthesis (research-to-engineering bridge)

Two papers from different fields (e.g., a neuroscience paper on attention
dynamics + a systems paper on cache eviction) describe related mechanisms.
Agent must read both, identify the shared structure, and propose a
synthesis (e.g., "neural attention's eviction policy is analogous to
LRU; both fail under burst patterns; here's a unified eviction signal").

BS-3 measures whether an agent can derive a non-obvious joint implication
that neither paper states and that yields a concrete research direction
or engineering prescription.

Spec: docs/04-bench-spec.md §2.3.BS3.
Datasets (cited from docs/01-corpus-catalog.md):
    - #54 arXiv metadata (CC0; cross-discipline pair sampling)
    - #55 PubMed Central OA (CC-BY; biomedical corpus)
    - #50 Wikipedia (CC-BY-SA; concept definitions)
    - #14 MMLongBench-Doc (research-only; figure+caption synthesis primitives)
    - Construction: harness-bench/BS3-cross-paper (purpose-built, MIT) —
      10 paper-pair scenarios covering well-documented cross-domain
      connections: adversarial-examples<->randomized-smoothing,
      predictive-coding<->backprop, ARC<->RAG-caching, adaptive-markets
      <->Red-Queen, AES-side-channel<->membership-inference,
      Dynamo<->stigmergy, peak-end<->IDE-satisfaction, zkSNARKs
      <->reproducibility, count-min-sketch<->self-consistency, and
      sparse-distributed-memory<->LSH.

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

# Field pairs sampled per spec §2.3.BS3 (one paper from each side).
DEFAULT_FIELD_PAIRS: tuple[tuple[str, str], ...] = (
    ("cs.AI", "q-bio.NC"),       # ML <-> neuroscience
    ("cs.OS", "cs.NE"),          # systems <-> neural
    ("q-fin.TR", "q-bio.PE"),    # markets <-> ecology
    ("cs.DC", "physics.bio-ph"), # distributed <-> biophysics
    ("cs.CR", "math.PR"),        # security <-> probability
)

# Corpus location — one JSONL row per sample.
CORPUS_PATH: Path = (
    Path(__file__).parent.parent.parent / "corpus" / "bs" / "bs3.jsonl"
)


@dataclass
class CrossPaperProbe:
    """One BS3 sample (kept for downstream scorer type-safety)."""

    probe_id: str
    paper_a_arxiv_id: str
    paper_b_arxiv_id: str
    field_pair: tuple[str, str]
    gold_shared_structure: str         # canonical 1-2 sentence shared mechanism
    gold_synthesis_bullets: list[str]  # 3-5 expected synthesis points
    distractor_paper_ids: list[str]    # plausible-but-unrelated papers in context


def _row_to_sample(row: dict[str, Any]) -> "Sample":
    """Adapt one BS-3 JSONL row into an Inspect AI Sample.

    Row schema: id, axis, prompt, context, target, rubric, difficulty,
    construction_source. The `prompt` encodes both paper abstracts (or
    abstract-level summaries) and the synthesis instruction.
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
            "axis": "BS-3",
            "rubric": row["rubric"],
            "id": row["id"],
            "difficulty": row.get("difficulty"),
            "construction_source": row.get("construction_source"),
            "license_tag": "MIT",
        },
    )


def _score_bs3(
    structural_match: float,
    novelty: float,
    factual_grounding: float,
) -> float:
    """BS3_score = 0.4 * structural_match + 0.3 * novelty + 0.3 * factual_grounding.
    See spec §2.3.BS3.
    """
    return (
        0.4 * structural_match
        + 0.3 * novelty
        + 0.3 * factual_grounding
    )


BS3_JUDGE_INSTRUCTIONS = (
    "You are grading a cross-paper synthesis. The expected answer "
    "identifies a non-obvious joint implication connecting two papers "
    "from different fields AND proposes a concrete research direction "
    "or engineering prescription. Use metadata.rubric verbatim. Full "
    "credit requires BOTH the mechanistic link AND a concrete next "
    "step. Partial credit when only one is present. No credit for "
    "surface 'both are about X' restatements or one-paper summaries."
)


@task
def bs3_cross_paper(
    max_samples: int = 10,
) -> "Task":
    """Inspect AI Task for axis BS3.

    Authored 10-paper-pair corpus. Each scenario presents two abstracts
    from different subfields and requires a joint-implication synthesis.
    Headline gate: structural_match >= 60%; factual_grounding >= 80%;
    judge agreement Krippendorff alpha >= 0.6.

    :param max_samples: cap on samples used (corpus has 10).
    """
    if json_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running BS-3 task."
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
            instructions=BS3_JUDGE_INSTRUCTIONS,
            partial_credit=True,
        ),
        metadata={
            "axis": "BS-3",
            "headline_scorer": "model_graded_qa",
            "corpus": str(CORPUS_PATH),
            "n_samples": max_samples,
            "field_pairs": [list(p) for p in DEFAULT_FIELD_PAIRS],
            "construction_note": (
                "Authored corpus — 10 paper-pair scenarios drawn from "
                "well-documented cross-domain connections. Papers are "
                "summarized at abstract level (not full text) to keep "
                "samples self-contained for single-call grading."
            ),
        },
    )


__all__ = [
    "DEFAULT_FIELD_PAIRS",
    "CORPUS_PATH",
    "CrossPaperProbe",
    "bs3_cross_paper",
]
