"""
BS4 — Tool-Output Bisociation (the "noticed something else" axis)

Agent runs tool A for purpose X, but the OUTPUT contains a structural
clue relevant to UNRELATED problem Y the agent is also tracking. Score:
does the agent NOTICE the cross-relevance and update Y?

Example: ran `semgrep` looking for SQLi (purpose X). Output happened to
flag a `eval(user_input)` site — relevant to a separate code-review task
the agent had open (purpose Y). Did the agent surface it?

Spec: docs/04-bench-spec.md §2.3.BS4.
Datasets (cited from docs/01-corpus-catalog.md):
    - #25 AppWorld (Apache-2.0; multi-purpose tool sessions)
    - #27 ToolBench (Apache-2.0; multi-tool primitives)
    - Construction: harness-bench/BS4-tool-bisociation (purpose-built, MIT) —
      120 dual-purpose tool sessions with planted cross-relevant signals.
    - Real-trace: #58 ToolBench trajectories (filter dual-task sessions)
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

# Cross-relevance categories per spec §2.3.BS4.
RELEVANCE_TYPES: tuple[str, ...] = (
    "security",      # security signal in non-security tool output
    "performance",   # perf-relevant clue in functional test output
    "data-quality",  # schema drift in non-validation tool
    "compliance",    # PII/license signal in code/doc tool output
    "stale-state",   # cache/freshness signal in lookup tool
)


@dataclass
class BS4Probe:
    """One BS4 sample."""
    probe_id: str
    primary_task: str            # what the agent was asked to do
    secondary_open_task: str     # the OTHER task the agent is tracking
    tool_calls_to_run: list[dict[str, Any]]
    planted_signal_in_output: str  # the cross-relevant clue
    relevance_type: str
    gold_notice: str             # what a great agent would say


def _inject_planted_signal(
    tool_output: str,
    signal: str,
    placement: str = "midstream",
) -> str:
    """Splice the planted cross-relevant signal into a real tool output.

    Placement controls where in the output stream the signal appears
    (head / midstream / tail) — affects whether agents that skim
    head-only miss it.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs4_tool_output.py:_inject_planted_signal "
        "— see docs/04-bench-spec.md §2.3.BS4"
    )


def _score_notice(
    agent_response: str,
    probe: BS4Probe,
) -> dict[str, float]:
    """Score whether agent surfaced the cross-relevant signal.

    Sub-scores:
        notice_recall      — did agent reference the planted signal?
        attribution_correct — linked to the right secondary task?
        false_alert_rate   — flagged irrelevant noise as cross-relevant?
    """
    raise NotImplementedError(
        "tasks/bisociation/bs4_tool_output.py:_score_notice "
        "— see docs/04-bench-spec.md §2.3.BS4"
    )


def _score_bs4(
    notice_recall: float,
    attribution_correct: float,
    false_alert_rate: float,
) -> float:
    """BS4_score = 0.5 * notice_recall + 0.4 * attribution_correct
    - 0.1 * false_alert_rate. See spec §2.3.BS4.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs4_tool_output.py:_score_bs4 "
        "— see docs/04-bench-spec.md §2.3.BS4"
    )


@task
def bs4_tool_output(
    n_samples: int = 120,
    relevance_types: tuple[str, ...] = RELEVANCE_TYPES,
    placement_mix: dict[str, float] | None = None,
) -> "Task":
    """Inspect AI Task for axis BS4.

    Dual-purpose tool sessions; planted cross-relevant signals in tool
    outputs. Headline gate: notice_recall >= 50%; attribution_correct
    >= 80% conditional on notice; false_alert_rate <= 10%.
    """
    raise NotImplementedError(
        "tasks/bisociation/bs4_tool_output.py:bs4_tool_output "
        "— see docs/04-bench-spec.md §2.3.BS4"
    )


__all__ = [
    "RELEVANCE_TYPES",
    "BS4Probe",
    "bs4_tool_output",
]
