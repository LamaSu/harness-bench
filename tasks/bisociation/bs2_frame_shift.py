"""
BS2 — Frame-Shift / Reframing Under Goal Reformulation

Mid-task, the user reframes the goal in language from a different domain
(e.g., engineer asks for "a graceful degradation pattern" -> reframes to
"a triage protocol"). Agent must recognize that the new frame applies to
the SAME underlying problem and continue without restarting.

Spec: docs/04-bench-spec.md §2.3.BS2.
Datasets (cited from docs/01-corpus-catalog.md):
    - Construction-only: harness-bench/BS2-frame-shift (purpose-built, MIT)
    - #20 TAU-bench / #21 tau2-bench (multi-turn dialogues; reframing primitives)
    - #28 PlanBench (planning under goal change)
    - #50 Wikipedia (CC-BY-SA; cross-domain vocabulary source)
Notes:
    No public bench measures this. Construction set: 80 dialogues with
    canonical "before/after frame" gold pairs + 3-judge LLM panel.
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

# Frame-shift severity per spec §2.3.BS2.
SHIFT_SEVERITY: tuple[str, ...] = (
    "lexical",      # same domain, different vocabulary
    "metaphorical", # cross-domain metaphor
    "axiomatic",    # different solution-shape entirely
)


@dataclass
class FrameShiftProbe:
    """One BS2 sample with before/after frame."""
    probe_id: str
    pre_shift_dialogue: list[dict[str, str]]   # original goal in frame A
    shift_turn: dict[str, str]                  # the user's reframed message
    post_shift_continuation: list[dict[str, str]]  # gold post-shift turns
    severity: str                               # "lexical" | "metaphorical" | "axiomatic"
    same_underlying_problem: bool               # True for in-distribution, False for true-restart probes


def _score_continuity(
    agent_post_shift_response: str,
    probe: FrameShiftProbe,
) -> dict[str, float]:
    """Score whether agent recognized continuity vs restarted from scratch.

    Sub-scores:
        continuity_recall    — did agent reuse prior reasoning?
        restart_false_positive — did agent restart on a true-shift probe?
        structural_match     — overlap of pre/post solution structure
    """
    raise NotImplementedError(
        "tasks/bisociation/bs2_frame_shift.py:_score_continuity "
        "— see docs/04-bench-spec.md §2.3.BS2"
    )


def _score_bs2(
    continuity_recall: float,
    restart_fpr: float,
    structural_match: float,
) -> float:
    """BS2_score = 0.5 * continuity_recall + 0.3 * structural_match
    - 0.2 * restart_fpr. See spec §2.3.BS2.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs2_frame_shift.py:_score_bs2 "
        "— see docs/04-bench-spec.md §2.3.BS2"
    )


@task
def bs2_frame_shift(
    n_samples: int = 80,
    severity_mix: dict[str, float] | None = None,
) -> "Task":
    """Inspect AI Task for axis BS2.

    Mid-dialogue reframing across lexical / metaphorical / axiomatic levels.
    Headline gate: continuity_recall >= 70% on lexical; >= 50% on
    metaphorical; restart_fpr <= 15% across all.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs2_frame_shift.py:bs2_frame_shift "
        "— see docs/04-bench-spec.md §2.3.BS2"
    )


__all__ = [
    "SHIFT_SEVERITY",
    "FrameShiftProbe",
    "bs2_frame_shift",
]
