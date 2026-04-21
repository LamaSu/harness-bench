"""
FM1 — Stuck-State / Loop Detection

Agent gets stuck in a loop: same tool call, same edit, same plan repeated
3+ times with no state delta. Modern harnesses lack reliable detection.
The "Open WebUI uvicorn loop" and Replit forced-stop incidents typify FM1.

Spec: docs/04-bench-spec.md §2.2.FM1.
Datasets (cited from docs/01-corpus-catalog.md):
    - #22 OSWorld (failure traces — agents stuck in GUI loops, MIT/Apache-2.0)
    - #25 AppWorld (multi-step workflows; loop-prone)
    - #20 TAU-bench / #21 tau2-bench (tool loops, MIT)
    - #1  SWE-bench Verified (test-fix loops)
    - #5  BigCodeBench (extended-context loops)
    - Real-trace: #51 Stack Overflow (loop-pattern Q&A), #58 ToolBench traj
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

# A "loop" per spec §2.2.FM1: same (tool_name, normalized_args) repeated
# REPEAT_THRESHOLD times within LOOP_WINDOW_TURNS turns with no observable
# state delta (file mtime, env var, sandbox FS hash unchanged).
REPEAT_THRESHOLD: int = 3
LOOP_WINDOW_TURNS: int = 8


@dataclass
class LoopVerdict:
    """One loop-detection result per sample."""
    detected: bool
    detected_at_turn: int | None
    repeated_call_signature: str | None
    state_delta_observed: bool
    intervention_correct: bool  # did agent itself break the loop?


def _normalize_call(tool_name: str, args: dict[str, Any]) -> str:
    """Stable signature for loop-equivalence (whitespace/key-order insensitive)."""
    raise NotImplementedError(
        "tasks/pain_modes/fm1_stuck_loops.py:_normalize_call — see docs/04-bench-spec.md §2.2.FM1"
    )


def _detect_loop(events: list[dict[str, Any]]) -> LoopVerdict:
    """Sliding-window detector over an event trace from `Harness.submit_task`.

    Returns the FIRST loop encountered (earliest detected_at_turn). Used both
    by the harness scorer AND as the gold-label oracle for FM1 samples
    constructed from OSWorld/SWE-bench failure traces.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm1_stuck_loops.py:_detect_loop — see docs/04-bench-spec.md §2.2.FM1"
    )


def _score_fm1(
    detection_recall: float,
    false_positive_rate: float,
    self_intervention_rate: float,
) -> float:
    """FM1_score = detection_recall - false_positive_rate + 0.5 * self_intervention_rate.
    Clamped to [0, 1]. See spec §2.2.FM1.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm1_stuck_loops.py:_score_fm1 — see docs/04-bench-spec.md §2.2.FM1"
    )


@task
def fm1_stuck_loops(
    n_samples: int = 100,
    include_osworld_failures: bool = True,
    include_swe_bench_loops: bool = True,
    repeat_threshold: int = REPEAT_THRESHOLD,
) -> "Task":
    """Inspect AI Task for axis FM1.

    Replays known-loop traces (OSWorld GUI hangs, SWE-bench test-fix
    spirals) into the harness under test. Headline gate: detection
    recall >= 90%, FPR <= 5%, self-intervention >= 50% of detected loops.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm1_stuck_loops.py:fm1_stuck_loops — see docs/04-bench-spec.md §2.2.FM1"
    )


__all__ = [
    "REPEAT_THRESHOLD",
    "LOOP_WINDOW_TURNS",
    "LoopVerdict",
    "fm1_stuck_loops",
]
