"""
FM4 — KV-Cache Drift / Cache-Poisoning Probes

Programmatic probes for cache-state drift: when prefix-shared KV-cache is
incorrectly reused across logically distinct prompts, model output drifts
from gold. Hard to test via natural traffic; we synthesize controlled
prefix-mutation pairs.

In v0.2 we use a simpler but complementary formulation: the same setup +
three semantically equivalent rephrasings of ONE question asked in a
single turn. A correctly-behaving harness returns three responses that
all agree on the same fact. Cache-drift manifests as divergent answers
across the three rephrasings.

Spec: docs/04-bench-spec.md §2.2.FM4.
Datasets (cited from docs/01-corpus-catalog.md):
    - Construction-only: harness-bench/FM4-cache-drift (purpose-built, MIT)
    - #12 RULER (Apache-2.0; deterministic synthetic primitives)
    - #16 FreshQA (date-anchored prompts for prefix permutation)
    - #5  BigCodeBench (code prefixes for cache-stress)

Construction source: 10 hand-authored scenarios (v0.2). Each scenario
pins a concrete setup (portfolio numbers / schema / catalog / timeline)
and poses Q1/Q2/Q3, three genuinely-same-fact rephrasings. Harness
passes iff all three answers agree. Prefix-swap / entity-rename /
date-shift mutation modes from the older spec are deferred to v1.0.

Status: IMPLEMENTED (v0.2) by impl-juliet.
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

# Permutation modes per spec §2.2.FM4.
# v0.2 uses a simpler "three rephrasings" probe in-corpus; the permutation
# mode machinery stays here for the v1.0 prefix-swap expansion.
PERMUTATION_MODES: tuple[str, ...] = (
    "swap_two_facts",      # swap order of two semantically-distinct prelude facts
    "negate_one_fact",     # flip one fact's polarity
    "rename_entity",       # rename Alice -> Bob throughout prelude
    "shift_dates",         # rotate all dates by +30 days
    "permute_tool_outputs",  # reorder tool-call results
)

# Corpus location — one JSONL row per sample.
CORPUS_PATH: Path = (
    Path(__file__).parent.parent.parent / "corpus" / "fm" / "fm4.jsonl"
)


@dataclass
class CachePair:
    """One (baseline, mutant) prompt pair with gold deltas.

    Kept for downstream scorer type-safety. v0.2 corpus does not use
    explicit baseline/mutant pairs (uses 3-rephrasings consistency probe
    instead); this dataclass is reserved for v1.0 prefix-swap expansion.
    """

    pair_id: str
    baseline_prompt: str
    mutant_prompt: str
    permutation: str
    gold_baseline_answer: str
    gold_mutant_answer: str
    expected_diff_token_count: int  # min |gold_baseline - gold_mutant|


def _generate_cache_pairs(
    n_pairs: int = 200,
    permutations: tuple[str, ...] = PERMUTATION_MODES,
    seed: int = 0,
) -> list[CachePair]:
    """Synthesize N controlled (baseline, mutant) prompt pairs.

    Pairs are designed so a CORRECT model returns measurably different
    answers; an agent suffering cache-drift returns the baseline answer
    even when fed the mutant.

    Deferred to v1.0 — v0.2 uses authored 3-rephrasings corpus instead.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm4_kv_cache_drift.py:_generate_cache_pairs "
        "— prefix-swap synthesis deferred to v1.0; v0.2 uses authored corpus"
    )


def _drift_score(
    baseline_response: str,
    mutant_response: str,
    pair: CachePair,
) -> float:
    """Per-pair drift score in [0, 1]. 1 = perfect (mutant differs as required).

    drift = 1 if (response_differs and matches_gold_mutant) else 0.
    Aggregate FM4_score = mean over pairs.

    Used by v1.0 scorer; v0.2 uses model_graded_qa on 3-rephrasings
    consistency (scorer checks whether all three answers agree with
    metadata.target).
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm4_kv_cache_drift.py:_drift_score "
        "— drift-pair scorer deferred to v1.0; v0.2 scoring via judge"
    )


def _row_to_sample(row: dict[str, Any]) -> "Sample":
    """Adapt one FM-4 JSONL row into an Inspect AI Sample.

    Row schema: id, axis, prompt, context, target, rubric, difficulty.
    The `prompt` field already contains the setup + Q1/Q2/Q3 rephrasings;
    we pass it through verbatim so the harness produces three answers in
    one turn. The scorer checks whether all three agree with `target`.
    """
    # FM-4 corpus embeds setup + three rephrasings in the prompt itself.
    # `context` is typically empty for FM-4 but we merge it if present
    # for forward compatibility.
    context_lines = row.get("context") or []
    context_block = (
        "\n\nAdditional context:\n" + "\n".join(context_lines)
        if context_lines
        else ""
    )
    prompt = f"{row['prompt']}{context_block}"

    return Sample(
        input=prompt,
        target=str(row["target"]),
        metadata={
            "axis": "FM-4",
            "rubric": row["rubric"],
            "id": row["id"],
            "difficulty": row.get("difficulty"),
            "license_tag": "MIT",
            "probe_shape": "three_rephrasings",
        },
    )


FM4_JUDGE_INSTRUCTIONS = (
    "You are grading KV-cache drift probes. Each probe asks the SAME "
    "underlying fact THREE times, rephrased (Q1 / Q2 / Q3). A "
    "correctly-behaving harness returns three answers that all agree on "
    "the same fact (as given in metadata.target). Cache-drift manifests "
    "as divergent answers across the three rephrasings. Use metadata.rubric "
    "verbatim. Full credit requires all three answers to semantically "
    "match the target. Half credit when 2 of 3 match. Zero when all three "
    "differ or the harness fails to produce three answers."
)


@task
def fm4_kv_cache_drift(
    n_pairs: int = 10,
    permutations: tuple[str, ...] = PERMUTATION_MODES,
    seed: int = 0,
) -> "Task":
    """Inspect AI Task for axis FM4.

    v0.2: 10 authored three-rephrasings probes (see corpus/fm/fm4.jsonl).
    Each row presents a setup and three semantically-equivalent reformulations
    of one question in a single prompt. A cache-drift-prone harness will
    produce inconsistent answers; a robust one will produce three
    matching answers.

    v1.0 (deferred): synthesizes N (baseline, mutant) prompt pairs across
    the 5 permutation modes in PERMUTATION_MODES. Headline gate:
    drift_score >= 95% on all permutation modes.

    :param n_pairs: number of probes from corpus (capped at 10 in v0.2).
    :param permutations: reserved for v1.0 synthesis.
    :param seed: reserved for v1.0 synthesis.
    """
    if json_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running FM-4 task."
        )

    ds = json_dataset(
        str(CORPUS_PATH),
        sample_fields=_row_to_sample,
        limit=n_pairs,
    )

    return Task(
        dataset=ds,
        solver=generate(),
        scorer=model_graded_qa(
            instructions=FM4_JUDGE_INSTRUCTIONS,
            partial_credit=True,
        ),
        metadata={
            "axis": "FM-4",
            "headline_scorer": "model_graded_qa",
            "corpus": str(CORPUS_PATH),
            "n_samples": n_pairs,
            "permutations_v1_0": list(permutations),
            "construction_note": (
                "Authored 3-rephrasings corpus (10 scenarios). The "
                "5-permutation prefix-swap synthesis (PERMUTATION_MODES) "
                "is reserved for v1.0 — see _generate_cache_pairs."
            ),
        },
    )


__all__ = [
    "PERMUTATION_MODES",
    "CORPUS_PATH",
    "CachePair",
    "fm4_kv_cache_drift",
]
