"""
BS2 — Frame-Shift / Reframing Under Goal Reformulation

Mid-task, the user (or the problem) reframes the goal in language from a
different domain (e.g., engineer asks for "a graceful degradation pattern"
-> reframes to "a triage protocol"). The agent must recognize that the
new frame applies to the SAME underlying problem and continue without
restarting. BS-2 measures this by presenting a "stuck" investigation
state with a current frame and a menu of candidate reframes, exactly
one of which is the productive shift; the agent must identify it and
articulate WHY.

Spec: docs/04-bench-spec.md §2.3.BS2.
Datasets (cited from docs/01-corpus-catalog.md):
    - Construction-only: harness-bench/BS2-frame-shift (purpose-built, MIT)
    - #20 TAU-bench / #21 tau2-bench (multi-turn dialogues; reframing primitives)
    - #28 PlanBench (planning under goal change)
    - #50 Wikipedia (CC-BY-SA; cross-domain vocabulary source)

Construction source: 15 hand-authored scenarios spanning async-Python,
LLM training, deployment, mouse genetics, SaaS analytics, k8s, ML
fine-tuning, distributed DB, mobile crash, quant finance, Rust
concurrency, CI flakiness, healthcare denials, secops, and CFD
numerics. Each scenario pins the frozen frame + 5 candidate reframes
and identifies the canonical frame-shift with rubric.

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

# Frame-shift severity per spec §2.3.BS2.
SHIFT_SEVERITY: tuple[str, ...] = (
    "lexical",      # same domain, different vocabulary
    "metaphorical", # cross-domain metaphor
    "axiomatic",    # different solution-shape entirely
)

# Corpus location — one JSONL row per sample.
CORPUS_PATH: Path = (
    Path(__file__).parent.parent.parent / "corpus" / "bs" / "bs2.jsonl"
)


@dataclass
class FrameShiftProbe:
    """One BS2 sample (kept for downstream scorer type-safety)."""

    probe_id: str
    pre_shift_dialogue: list[dict[str, str]]   # original goal in frame A
    shift_turn: dict[str, str]                  # the user's reframed message
    post_shift_continuation: list[dict[str, str]]  # gold post-shift turns
    severity: str                               # "lexical" | "metaphorical" | "axiomatic"
    same_underlying_problem: bool               # True for in-distribution, False for true-restart probes


def _row_to_sample(row: dict[str, Any]) -> "Sample":
    """Adapt one BS-2 JSONL row into an Inspect AI Sample.

    Row schema: id, axis, prompt, context, target, rubric, difficulty,
    construction_source.
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
            "axis": "BS-2",
            "rubric": row["rubric"],
            "id": row["id"],
            "difficulty": row.get("difficulty"),
            "construction_source": row.get("construction_source"),
            "license_tag": "MIT",
        },
    )


def _score_bs2(
    continuity_recall: float,
    restart_fpr: float,
    structural_match: float,
) -> float:
    """BS2_score = 0.5 * continuity_recall + 0.3 * structural_match
    - 0.2 * restart_fpr. See spec §2.3.BS2.
    """
    return (
        0.5 * continuity_recall
        + 0.3 * structural_match
        - 0.2 * restart_fpr
    )


BS2_JUDGE_INSTRUCTIONS = (
    "You are grading a frame-shift reframing answer. The expected answer "
    "identifies ONE specific reframe from the candidate list and "
    "articulates why it productively relocates the investigation. Use "
    "the rubric in metadata.rubric verbatim. Full credit requires both "
    "the correct letter AND the articulation. Partial credit applies "
    "when the letter is right but the articulation is weak, OR when a "
    "rubric-specified alternative letter is chosen. Reject answers that "
    "name the right letter without any reasoning about WHY it is a frame "
    "shift rather than a local patch."
)


@task
def bs2_frame_shift(
    max_samples: int = 15,
) -> "Task":
    """Inspect AI Task for axis BS2.

    Authored 15-scenario corpus of stuck-investigation probes with
    candidate reframes. Headline gate: continuity_recall >= 70% on
    lexical; >= 50% on metaphorical; restart_fpr <= 15% across all.

    :param max_samples: cap on samples used (corpus has 15).
    """
    if json_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running BS-2 task."
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
            instructions=BS2_JUDGE_INSTRUCTIONS,
            partial_credit=True,
        ),
        metadata={
            "axis": "BS-2",
            "headline_scorer": "model_graded_qa",
            "corpus": str(CORPUS_PATH),
            "n_samples": max_samples,
            "construction_note": (
                "Authored corpus — 15 stuck-investigation scenarios "
                "with 5 candidate reframes each. No public benchmark "
                "measures this axis directly (docs/01 §29.5)."
            ),
        },
    )


__all__ = [
    "SHIFT_SEVERITY",
    "CORPUS_PATH",
    "FrameShiftProbe",
    "bs2_frame_shift",
]
