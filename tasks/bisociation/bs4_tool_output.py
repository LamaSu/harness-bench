"""
BS4 — Tool-Output Bisociation (the "noticed something else" axis)

Agent runs two tools for an explicit PRIMARY purpose, but the joint
output contains a structural clue relevant to an explicit OPEN_SECONDARY
task the agent is tracking. Score: does the agent NOTICE the
cross-relevance and surface it?

Example: ran `git log --grep=AUTH_REFACTOR` (PRIMARY: find the refactor
PR) + `grep legacy_auth packages/` (completely separate investigation).
Output jointly reveals that legacy_auth imports still exist AFTER the
refactor "completed" — a cross-relevant insight the agent must flag.

Spec: docs/04-bench-spec.md §2.3.BS4.
Datasets (cited from docs/01-corpus-catalog.md):
    - #25 AppWorld (Apache-2.0; multi-purpose tool sessions)
    - #27 ToolBench (Apache-2.0; multi-tool primitives)
    - Construction: harness-bench/BS4-tool-bisociation (purpose-built, MIT) —
      10 hand-authored dual-purpose tool sessions with planted cross-relevant
      signals across git+grep, logs+curl, profiling+explain-analyze,
      package-managers, tcpdump+pprof, CI+analytics, npm+service-workers,
      NTP+DB, bench-variance, and cross-AZ latency+cost.
    - Real-trace: #58 ToolBench trajectories (filter dual-task sessions)

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

# Cross-relevance categories per spec §2.3.BS4.
RELEVANCE_TYPES: tuple[str, ...] = (
    "security",      # security signal in non-security tool output
    "performance",   # perf-relevant clue in functional test output
    "data-quality",  # schema drift in non-validation tool
    "compliance",    # PII/license signal in code/doc tool output
    "stale-state",   # cache/freshness signal in lookup tool
)

# Corpus location — one JSONL row per sample.
CORPUS_PATH: Path = (
    Path(__file__).parent.parent.parent / "corpus" / "bs" / "bs4.jsonl"
)


@dataclass
class BS4Probe:
    """One BS4 sample (kept for downstream scorer type-safety)."""

    probe_id: str
    primary_task: str            # what the agent was asked to do
    secondary_open_task: str     # the OTHER task the agent is tracking
    tool_calls_to_run: list[dict[str, Any]]
    planted_signal_in_output: str  # the cross-relevant clue
    relevance_type: str
    gold_notice: str             # what a great agent would say


def _row_to_sample(row: dict[str, Any]) -> "Sample":
    """Adapt one BS-4 JSONL row into an Inspect AI Sample.

    Row schema: id, axis, prompt, context, target, rubric, difficulty,
    construction_source. The `prompt` already encodes the PRIMARY and
    OPEN_SECONDARY tasks plus the two tool outputs; the `target` holds
    the expected joint answer.
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
            "axis": "BS-4",
            "rubric": row["rubric"],
            "id": row["id"],
            "difficulty": row.get("difficulty"),
            "construction_source": row.get("construction_source"),
            "license_tag": "MIT",
        },
    )


def _score_bs4(
    notice_recall: float,
    attribution_correct: float,
    false_alert_rate: float,
) -> float:
    """BS4_score = 0.5 * notice_recall + 0.4 * attribution_correct
    - 0.1 * false_alert_rate. See spec §2.3.BS4.
    """
    return (
        0.5 * notice_recall
        + 0.4 * attribution_correct
        - 0.1 * false_alert_rate
    )


BS4_JUDGE_INSTRUCTIONS = (
    "You are grading tool-output bisociation. The expected answer has "
    "TWO parts: (1) a correct response to the PRIMARY task, and (2) a "
    "call-out of any cross-relevance to the OPEN_SECONDARY task that "
    "the tool outputs jointly reveal. Use metadata.rubric verbatim. "
    "Full credit requires BOTH the primary answer AND the cross-relevant "
    "surface. Partial credit when the primary is correct but the "
    "cross-reference is missing, weak, or over-general. Penalize "
    "false-alert responses that fabricate cross-relevance where none "
    "exists in the rubric."
)


@task
def bs4_tool_output(
    max_samples: int = 10,
) -> "Task":
    """Inspect AI Task for axis BS4.

    10-scenario authored corpus of dual-purpose tool sessions with
    planted cross-relevant signals across security, performance, data
    integrity, compliance, and stale-state categories. Headline gate:
    notice_recall >= 50%; attribution_correct >= 80% conditional on
    notice; false_alert_rate <= 10%.

    :param max_samples: cap on samples used (corpus has 10).
    """
    if json_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running BS-4 task."
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
            instructions=BS4_JUDGE_INSTRUCTIONS,
            partial_credit=True,
        ),
        metadata={
            "axis": "BS-4",
            "headline_scorer": "model_graded_qa",
            "corpus": str(CORPUS_PATH),
            "n_samples": max_samples,
            "relevance_types": list(RELEVANCE_TYPES),
            "construction_note": (
                "Authored corpus — 10 dual-task scenarios covering the "
                "5 cross-relevance categories. Tool outputs are realistic "
                "synthetic but preserve structural signal fidelity."
            ),
        },
    )


__all__ = [
    "RELEVANCE_TYPES",
    "CORPUS_PATH",
    "BS4Probe",
    "bs4_tool_output",
]
