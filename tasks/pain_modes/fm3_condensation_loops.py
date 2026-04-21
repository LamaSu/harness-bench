"""
FM3 — Condensation / Auto-Compaction Loops

When a harness compacts/summarizes context, key facts get lost. The agent
then asks again, the new turn re-fills context, compaction runs again,
and the loop repeats. Closely related to M5 (eviction quality) but the
failure surface here is the COMPACTION POLICY itself, not budget choice.

Spec: docs/04-bench-spec.md §2.2.FM3.
Datasets (cited from docs/01-corpus-catalog.md):
    - #9  LongMemEval (knowledge-updates + long-session reasoning, MIT)
    - #10 LoCoMo (multi-session dialogues)
    - #11 BABILong (variable-length stress)
    - #12 RULER (Apache-2.0)
    - #1  SWE-bench Verified (long fix sessions)
    - Real-trace: harness-bench/FM3-condensation

Construction source: 10 hand-authored scenarios (v0.2), each containing
a long prelude (~1k+ tokens of realistic debugging / code-review /
incident-response transcript) that plants a specific fact pre-compaction,
followed by a question that can only be answered correctly if the
harness has preserved that fact across the compaction boundary.

Status: IMPLEMENTED (v0.2) by impl-juliet.
"""
from __future__ import annotations

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

# Triggered if compaction occurs > MAX_COMPACTIONS times in a session that
# was supposed to terminate with K turns. Per spec §2.2.FM3.
MAX_COMPACTIONS_PER_SESSION: int = 3

# Corpus location — one JSONL row per sample.
CORPUS_PATH: Path = (
    Path(__file__).parent.parent.parent / "corpus" / "fm" / "fm3.jsonl"
)


def _force_compaction_pressure(
    base_session: list[dict[str, Any]],
    target_compactions: int = 4,
    facts_to_preserve: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Inflate a session to force the harness's compaction policy to fire.

    Adds turns of plausible-but-irrelevant tool output until total tokens
    exceed the harness's compaction trigger. The `facts_to_preserve` list is
    seeded early; we score whether they survive each compaction event.

    Not used in v0.2 static-corpus mode — reserved for future synthetic
    session amplification when we want to push past the authored
    scenarios' natural compaction depth.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm3_condensation_loops.py:_force_compaction_pressure "
        "— synthetic-pressure mode deferred; v0.2 uses authored corpus"
    )


def _detect_condensation_loop(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Identify post-compaction re-asking pattern.

    Loop signature: (compaction_event) -> (agent re-asks for fact F that was
    in pre-compaction context) -> (new turn re-fills context with F's source)
    -> (next compaction). Returns {detected, n_cycles, lost_facts}.

    Consumed by downstream scorer in scorers/ when a harness's trace events
    include compaction markers. Stubbed here; scorer lands separately.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm3_condensation_loops.py:_detect_condensation_loop "
        "— scorer lives in scorers/; see docs/04-bench-spec.md §2.2.FM3"
    )


def _score_fm3(
    fact_loss_rate_per_compaction: float,
    redundant_refetch_count: int,
    final_task_success: bool,
) -> float:
    """FM3_score = (1 - fact_loss_rate) * (1 / (1 + redundant_refetch_count))
    * float(final_task_success). See spec §2.2.FM3.

    Implementation kept in scorers/ so the scorer can read trace telemetry;
    this v0.2 task just yields per-sample correctness via model_graded_qa.
    """
    if not final_task_success:
        return 0.0
    loss_factor = max(0.0, 1.0 - fact_loss_rate_per_compaction)
    refetch_factor = 1.0 / (1.0 + max(0, redundant_refetch_count))
    return max(0.0, min(1.0, loss_factor * refetch_factor))


def _row_to_sample(row: dict[str, Any]) -> "Sample":
    """Adapt one FM-3 JSONL row into an Inspect AI Sample.

    Row schema: id, axis, prompt, context, target, rubric, difficulty.
    The `context` list is the long pre-compaction transcript; we serialize
    it verbatim so the harness must actually retain facts across any
    compaction its policy triggers.
    """
    context_lines = row.get("context") or []
    context_block = (
        "\n\nPrior session transcript (pre-compaction):\n" + "\n".join(context_lines)
        if context_lines
        else ""
    )
    prompt = (
        f"{context_block}\n\n---\n\nQuestion (post-compaction): {row['prompt']}"
        if context_block
        else f"Question: {row['prompt']}"
    )

    return Sample(
        input=prompt,
        target=str(row["target"]),
        metadata={
            "axis": "FM-3",
            "rubric": row["rubric"],
            "id": row["id"],
            "difficulty": row.get("difficulty"),
            "license_tag": "MIT",
        },
    )


FM3_JUDGE_INSTRUCTIONS = (
    "You are grading whether a harness has preserved a specific fact "
    "across an auto-compaction boundary in a long session. The expected "
    "answer contains one or more concrete facts (URLs, SHAs, IDs, dates, "
    "file paths, numerical values) that were planted earlier in the "
    "session transcript. Use metadata.rubric verbatim. Full credit "
    "requires the exact fact (or all listed facts) be reproduced. Half "
    "credit is appropriate when the rubric explicitly allows 'partial' "
    "(e.g., 2 of 3 facts correct, short SHA vs full SHA). Zero credit "
    "if the agent re-asks the user for the fact or fabricates a "
    "different value — that is the classic condensation-loop failure."
)


@task
def fm3_condensation_loops(
    n_samples: int = 10,
    target_compactions_per_sample: int = 4,
    facts_per_sample: int = 5,
) -> "Task":
    """Inspect AI Task for axis FM3.

    Long multi-session task that forces the harness's compaction policy to
    fire >=3 times. Plants 5 facts in pre-compaction context that the
    agent will need post-compaction. Headline gate: fact_loss <= 20%
    per compaction, no redundant re-fetch loops, final-task success >= 70%.

    v0.2 corpus = 10 authored scenarios (see corpus/fm/fm3.jsonl). The
    `target_compactions_per_sample` and `facts_per_sample` knobs are
    reserved for synthetic-pressure mode (see _force_compaction_pressure);
    static corpus uses whatever prelude depth was authored into each row.
    """
    if json_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running FM-3 task."
        )

    ds = json_dataset(
        str(CORPUS_PATH),
        sample_fields=_row_to_sample,
        limit=n_samples,
    )

    return Task(
        dataset=ds,
        solver=generate(),
        scorer=model_graded_qa(
            instructions=FM3_JUDGE_INSTRUCTIONS,
            partial_credit=True,
        ),
        metadata={
            "axis": "FM-3",
            "headline_scorer": "model_graded_qa",
            "corpus": str(CORPUS_PATH),
            "n_samples": n_samples,
            "target_compactions_per_sample": target_compactions_per_sample,
            "facts_per_sample": facts_per_sample,
            "construction_note": (
                "Authored corpus of 10 long-prelude scenarios; no public "
                "benchmark directly measures condensation loops. Each "
                "prelude plants a specific fact pre-compaction, then "
                "asks a question whose correct answer requires that "
                "fact post-compaction."
            ),
        },
    )


__all__ = [
    "MAX_COMPACTIONS_PER_SESSION",
    "CORPUS_PATH",
    "fm3_condensation_loops",
]
