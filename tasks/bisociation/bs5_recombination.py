"""
BS5 — Solution Recombination (E-MAGIC-style)

Given two existing partial solutions to two SEPARATE problems, agent
must recombine PARTS of each to solve a THIRD problem neither covers
alone. This is the classic "innovation by recombination" capability
and the purest test of bisociation.

BS-5 presents two working-but-partial Python implementations and a
target problem where the correct answer synthesizes properties from
BOTH. The grader checks whether the response (a) preserves the key
property each source contributes, (b) resolves any ordering / data
structure conflict correctly, and (c) does not regress on either
original's strengths.

Spec: docs/04-bench-spec.md §2.3.BS5.
Datasets (cited from docs/01-corpus-catalog.md):
    - Construction: harness-bench/E-MAGIC (purpose-built, MIT) — 10
      hand-authored triples (partial_A, partial_B, target_C) across
      list-processing, rate-limiting, text-search, HTTP-retry, streaming
      dedup, file-upload validation, distributed scheduling, config
      loading, audio normalization, and LRU+TTL caches.
    - #28 PlanBench (planning primitives)
    - #25 AppWorld (multi-tool composition)
    - #5  BigCodeBench (code recombination ground truth)
    - #57 CommitPackFT (MIT; PR refactor patterns as recombination examples)

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

# Recombination difficulty per spec §2.3.BS5.
RECOMBINATION_DIFFICULTY: tuple[str, ...] = (
    "additive",      # bolt parts together; minimal adaptation
    "substitutive",  # swap component X of A for component Y of B
    "transformative",# both halves require non-trivial adaptation to fit
)

# Corpus location — one JSONL row per sample.
CORPUS_PATH: Path = (
    Path(__file__).parent.parent.parent / "corpus" / "bs" / "bs5.jsonl"
)


@dataclass
class RecombinationProbe:
    """One BS5 sample (kept for downstream scorer type-safety)."""

    probe_id: str
    problem_a_summary: str
    solution_a_artifact: str   # working code/plan/protocol
    problem_b_summary: str
    solution_b_artifact: str
    target_problem_c: str       # the new problem to solve
    gold_recombination: str     # canonical solution drawing from A and B
    distractor_recombinations: list[str]   # plausible-but-wrong (3+)
    difficulty: str


def _row_to_sample(row: dict[str, Any]) -> "Sample":
    """Adapt one BS-5 JSONL row into an Inspect AI Sample.

    Row schema: id, axis, prompt, context, target, rubric, difficulty,
    construction_source. The `prompt` encodes both partial solutions
    inline with the target problem; the `target` holds the expected
    combined implementation.
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
            "axis": "BS-5",
            "rubric": row["rubric"],
            "id": row["id"],
            "difficulty": row.get("difficulty"),
            "construction_source": row.get("construction_source"),
            "license_tag": "MIT",
        },
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
    return (
        0.25 * structural_overlap
        + 0.40 * executes_correctly
        + 0.20 * parts_drawn_from_both
        + 0.15 * novelty_above_distractors
    )


BS5_JUDGE_INSTRUCTIONS = (
    "You are grading a solution-recombination answer. The expected "
    "answer synthesizes two partial solutions into a single "
    "implementation that preserves the key property of EACH source. "
    "Use metadata.rubric verbatim. Full credit requires BOTH key "
    "properties to be present AND correct ordering/composition. "
    "Partial credit when only one property is preserved, or when both "
    "are present but the composition introduces a new bug. Reject "
    "answers that use only one of the two source solutions."
)


@task
def bs5_recombination(
    max_samples: int = 10,
    require_sandbox_execution: bool = False,
) -> "Task":
    """Inspect AI Task for axis BS5.

    Authored 10-triple corpus spanning additive, substitutive, and
    transformative recombination difficulty. Headline gate:
    executes_correctly >= 50% on additive, >= 30% on substitutive,
    >= 15% on transformative.

    :param max_samples: cap on samples used (corpus has 10).
    :param require_sandbox_execution: reserved — v0.2 grades via
        model_graded_qa only. Sandbox execution is future work
        (see spec §2.3.BS5).
    """
    if json_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running BS-5 task."
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
            instructions=BS5_JUDGE_INSTRUCTIONS,
            partial_credit=True,
        ),
        metadata={
            "axis": "BS-5",
            "headline_scorer": "model_graded_qa",
            "corpus": str(CORPUS_PATH),
            "n_samples": max_samples,
            "difficulty_levels": list(RECOMBINATION_DIFFICULTY),
            "require_sandbox_execution": require_sandbox_execution,
            "construction_note": (
                "Authored corpus — 10 Python-coding recombination "
                "triples. Each prompt embeds two partial solutions "
                "inline. v0.2 uses model_graded_qa only; sandbox "
                "execution for 'executes_correctly' sub-score is "
                "future work (spec §2.3.BS5)."
            ),
        },
    )


__all__ = [
    "RECOMBINATION_DIFFICULTY",
    "CORPUS_PATH",
    "RecombinationProbe",
    "bs5_recombination",
]
