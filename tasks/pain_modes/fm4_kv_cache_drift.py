"""
FM4 — KV-Cache Drift / Cache-Poisoning Probes

Programmatic probes for cache-state drift: when prefix-shared KV-cache is
incorrectly reused across logically distinct prompts, model output drifts
from gold. Hard to test via natural traffic; we synthesize controlled
prefix-mutation pairs.

Spec: docs/04-bench-spec.md §2.2.FM4.
Datasets (cited from docs/01-corpus-catalog.md):
    - Construction-only: harness-bench/FM4-cache-drift (purpose-built, MIT)
    - #12 RULER (Apache-2.0; deterministic synthetic primitives)
    - #16 FreshQA (date-anchored prompts for prefix permutation)
    - #5  BigCodeBench (code prefixes for cache-stress)
Notes:
    Dataset is fully synthesized (no public corpus exists for cache-poisoning).
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

# Permutation modes per spec §2.2.FM4.
PERMUTATION_MODES: tuple[str, ...] = (
    "swap_two_facts",      # swap order of two semantically-distinct prelude facts
    "negate_one_fact",     # flip one fact's polarity
    "rename_entity",       # rename Alice -> Bob throughout prelude
    "shift_dates",         # rotate all dates by +30 days
    "permute_tool_outputs",# reorder tool-call results
)


@dataclass
class CachePair:
    """One (baseline, mutant) prompt pair with gold deltas."""
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
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm4_kv_cache_drift.py:_generate_cache_pairs "
        "— see docs/04-bench-spec.md §2.2.FM4"
    )


def _drift_score(
    baseline_response: str,
    mutant_response: str,
    pair: CachePair,
) -> float:
    """Per-pair drift score in [0, 1]. 1 = perfect (mutant differs as required).

    drift = 1 if (response_differs and matches_gold_mutant) else 0.
    Aggregate FM4_score = mean over pairs.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm4_kv_cache_drift.py:_drift_score "
        "— see docs/04-bench-spec.md §2.2.FM4"
    )


@task
def fm4_kv_cache_drift(
    n_pairs: int = 200,
    permutations: tuple[str, ...] = PERMUTATION_MODES,
    seed: int = 0,
) -> "Task":
    """Inspect AI Task for axis FM4.

    Synthesizes N (baseline, mutant) prompt pairs covering the 5 permutation
    modes. Headline gate: drift_score >= 95% on all permutation modes;
    evidence of prefix-cache invalidation visible in trace events.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm4_kv_cache_drift.py:fm4_kv_cache_drift "
        "— see docs/04-bench-spec.md §2.2.FM4"
    )


__all__ = [
    "PERMUTATION_MODES",
    "CachePair",
    "fm4_kv_cache_drift",
]
