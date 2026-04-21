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
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]

    def task(fn):  # type: ignore[no-redef]
        return fn

# Triggered if compaction occurs > MAX_COMPACTIONS times in a session that
# was supposed to terminate with K turns. Per spec §2.2.FM3.
MAX_COMPACTIONS_PER_SESSION: int = 3


def _force_compaction_pressure(
    base_session: list[dict[str, Any]],
    target_compactions: int = 4,
    facts_to_preserve: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Inflate a session to force the harness's compaction policy to fire.

    Adds turns of plausible-but-irrelevant tool output until total tokens
    exceed the harness's compaction trigger. The `facts_to_preserve` list is
    seeded early; we score whether they survive each compaction event.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm3_condensation_loops.py:_force_compaction_pressure "
        "— see docs/04-bench-spec.md §2.2.FM3"
    )


def _detect_condensation_loop(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Identify post-compaction re-asking pattern.

    Loop signature: (compaction_event) -> (agent re-asks for fact F that was
    in pre-compaction context) -> (new turn re-fills context with F's source)
    -> (next compaction). Returns {detected, n_cycles, lost_facts}.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm3_condensation_loops.py:_detect_condensation_loop "
        "— see docs/04-bench-spec.md §2.2.FM3"
    )


def _score_fm3(
    fact_loss_rate_per_compaction: float,
    redundant_refetch_count: int,
    final_task_success: bool,
) -> float:
    """FM3_score = (1 - fact_loss_rate) * (1 / (1 + redundant_refetch_count))
    * float(final_task_success). See spec §2.2.FM3.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm3_condensation_loops.py:_score_fm3 "
        "— see docs/04-bench-spec.md §2.2.FM3"
    )


@task
def fm3_condensation_loops(
    n_samples: int = 50,
    target_compactions_per_sample: int = 4,
    facts_per_sample: int = 5,
) -> "Task":
    """Inspect AI Task for axis FM3.

    Long multi-session task that forces the harness's compaction policy to
    fire >=3 times. Plants 5 facts in pre-compaction context that the
    agent will need post-compaction. Headline gate: fact_loss <= 20%
    per compaction, no redundant re-fetch loops, final-task success >= 70%.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm3_condensation_loops.py:fm3_condensation_loops "
        "— see docs/04-bench-spec.md §2.2.FM3"
    )


__all__ = [
    "MAX_COMPACTIONS_PER_SESSION",
    "fm3_condensation_loops",
]
