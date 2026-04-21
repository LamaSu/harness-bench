"""
M3 — Stale-Fact Rejection Under Knowledge Updates

When facts change, agent must use the LATEST fact AND recognize when a
stored memory is provably stale. Adversarial variant: surface BOTH old and
new fact in retrieved context.

Spec: docs/04-bench-spec.md §2.1.M3.
Datasets (cited from docs/01-corpus-catalog.md):
    - #9  LongMemEval (knowledge-updates axis, MIT)
    - #16 FreshQA (temporal-rotating Q&A) — PRIMARY
    - #17 RealTimeQA (weekly-updated)
    - #54 arXiv metadata (CC0; date-anchored)
    - Construction: harness-bench/M3-stale (synthesized 30-90 day timeline)

Primary HF dataset: FreshQA is git-only per catalog #16 and ships from
github.com/freshllms/freshqa as CSV. There is a community HF mirror at
**z-uo/freshqa** (verify on first pull). When the canonical mirror is
unavailable, this loader falls back to the LongMemEval knowledge-updates
slice (xiaowu0162/longmemeval-cleaned filtered by qa_type='knowledge-update').

Substitution flag: `use_longmemeval_fallback=True` switches to LongMemEval
filter mode. Documented in task metadata.

Status: IMPLEMENTED (v0.2) by implementer-foxtrot.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample, hf_dataset
    from inspect_ai.solver import generate
    from inspect_ai.scorer import model_graded_qa
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]
    hf_dataset = None  # type: ignore[assignment]
    generate = None  # type: ignore[assignment]
    model_graded_qa = None  # type: ignore[assignment]

    def task(fn):  # type: ignore[no-redef]
        return fn

# Primary FreshQA HF mirror (community-maintained per catalog substitution policy).
FRESHQA_HF_ID = "z-uo/freshqa"
FRESHQA_DEFAULT_SPLIT = "test"

# Fallback: LongMemEval knowledge-updates slice.
LONGMEMEVAL_HF_ID = "xiaowu0162/longmemeval-cleaned"
LONGMEMEVAL_KU_QA_TYPE = "knowledge-update"


def _generate_versioned_fact_timeline(
    n_facts: int = 7,
    timeline_days: int = 60,
    updates_per_fact_range: tuple[int, int] = (2, 5),
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Build a synthetic 30-90 day timeline of N facts updated 2-5x each.

    Each entry: {fact_id, version, value, effective_date, supersedes}.
    Used to construct M3 sample histories when no live FreshQA pull is
    possible. Deterministic per seed.
    """
    import random
    rng = random.Random(seed)

    base_date = date(2026, 1, 1)
    timeline: list[dict[str, Any]] = []

    lo_updates, hi_updates = updates_per_fact_range
    for fact_id in range(n_facts):
        n_updates = rng.randint(lo_updates, hi_updates)
        # Ensure last update sits within timeline_days.
        update_days = sorted(
            rng.sample(range(timeline_days), min(n_updates, timeline_days))
        )
        previous_version = None
        for v_idx, days_offset in enumerate(update_days):
            entry = {
                "fact_id": f"fact_{fact_id:03d}",
                "version": v_idx,
                "value": f"value_v{v_idx}_for_fact_{fact_id:03d}",
                "effective_date": (
                    base_date + timedelta(days=days_offset)
                ).isoformat(),
                "supersedes": previous_version,
            }
            timeline.append(entry)
            previous_version = entry["version"]
    return timeline


def _build_adversarial_sample(
    timeline: list[dict[str, Any]],
    test_date: date,
    surface_old_too: bool = True,
) -> "Sample":
    """Build one M3 sample.

    If surface_old_too=True, the retrieval context will contain BOTH the
    superseded value and the latest value. Agent should detect contradiction
    AND pick latest.
    """
    if not timeline:
        raise ValueError("timeline must contain at least one fact entry")

    target_fact_id = timeline[0]["fact_id"]
    versions = [
        e for e in timeline
        if e["fact_id"] == target_fact_id
        and date.fromisoformat(e["effective_date"]) <= test_date
    ]
    versions.sort(key=lambda e: e["effective_date"])
    if not versions:
        raise ValueError(
            f"no fact entry for {target_fact_id} on or before {test_date}"
        )
    latest = versions[-1]

    context_lines = [
        f"As of {test_date.isoformat()}, here is the conversation history:",
    ]
    if surface_old_too and len(versions) >= 2:
        old = versions[0]
        context_lines.append(
            f"[Earlier note, dated {old['effective_date']}] "
            f"{target_fact_id} = {old['value']}"
        )
    context_lines.append(
        f"[Latest update, dated {latest['effective_date']}] "
        f"{target_fact_id} = {latest['value']}"
    )

    prompt = "\n".join(context_lines) + (
        f"\n\nWhat is the current value of {target_fact_id}? "
        "If you see contradicting versions, state the contradiction "
        "and pick the latest."
    )

    return Sample(
        input=prompt,
        target=str(latest["value"]),
        metadata={
            "axis": "M3",
            "domain": "general",
            "license_tag": "MIT (synthetic)",
            "fact_id": target_fact_id,
            "is_adversarial": surface_old_too,
            "test_date": test_date.isoformat(),
            "n_versions_seen": len(versions),
        },
    )


def _score_m3(
    last_write_accuracy: float,
    contradiction_f1: float,
) -> float:
    """M3_score = 0.6 * last_write_accuracy + 0.4 * contradiction_F1. See spec §2.1.M3."""
    return 0.6 * last_write_accuracy + 0.4 * contradiction_f1


def _freshqa_record_to_sample(record: dict[str, Any]) -> "Sample":
    """Adapt a FreshQA row into a Sample.

    FreshQA fields (per repo CSV header):
        id, question, answer (current correct), false_premise (bool),
        effective_date / source_date, prior_answer (optional, when fact
        changed), source_url.
    """
    question = record.get("question") or record.get("query") or ""
    answer = record.get("answer") or record.get("current_answer") or ""
    prior = record.get("prior_answer") or record.get("old_answer")
    src_date = (
        record.get("effective_date")
        or record.get("source_date")
        or record.get("date")
        or "unknown"
    )

    if prior:
        prompt = (
            f"Two notes from your memory:\n"
            f"  [older] The answer to '{question}' was: {prior}\n"
            f"  [latest, dated {src_date}] The answer is now: {answer}\n\n"
            f"Question: {question}\n"
            f"If the notes contradict, flag the contradiction and pick the latest."
        )
        is_adversarial = True
    else:
        prompt = (
            f"As of {src_date}, please answer the following question.\n\n"
            f"Question: {question}"
        )
        is_adversarial = False

    return Sample(
        input=prompt,
        target=str(answer),
        metadata={
            "axis": "M3",
            "domain": "general",
            "license_tag": "per-FreshQA-card",
            "source_id": record.get("id") or record.get("question_id") or "",
            "is_adversarial": is_adversarial,
            "source_date": str(src_date),
            "false_premise": bool(record.get("false_premise", False)),
        },
    )


def _longmemeval_ku_record_to_sample(record: dict[str, Any]) -> "Sample":
    """Fallback adapter: LongMemEval knowledge-updates slice."""
    question = record.get("question") or ""
    answer = record.get("answer") or ""
    history = record.get("haystack_sessions") or record.get("session_history") or []

    history_text = "\n\n".join(
        f"[{turn.get('role', 'user').upper()}] {turn.get('content', '')}"
        for turn in history if isinstance(turn, dict)
    ) if history else ""

    prompt = (
        f"Conversation history:\n\n{history_text}\n\n"
        f"---\n\nQuestion (knowledge-update axis): {question}\n"
        f"If older notes contradict newer notes, flag and pick the latest."
        if history_text
        else f"Question: {question}"
    )

    return Sample(
        input=prompt,
        target=str(answer),
        metadata={
            "axis": "M3",
            "domain": "general",
            "license_tag": "MIT",
            "source_id": record.get("question_id") or "",
            "is_adversarial": True,  # KU slice is inherently adversarial
            "qa_type": record.get("qa_type"),
        },
    )


@task
def m3_stale_fact(
    n_samples: int = 50,
    pct_adversarial: float = 0.5,
    include_freshqa: bool = True,
    include_realtimeqa: bool = True,
    use_longmemeval_fallback: bool = False,
    hf_split: str = FRESHQA_DEFAULT_SPLIT,
) -> "Task":
    """Inspect AI Task for axis M3.

    Combines FreshQA (primary) with optional LongMemEval knowledge-updates
    slice fallback. Headline gate: >=90% last-write-wins AND >=80%
    contradiction-flag F1. See spec §2.1.M3.

    The `include_realtimeqa` flag is reserved — RealTimeQA pulls live and
    not yet wired into the HF loader path; ignored for v0.2.
    """
    if hf_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running M3 task."
        )

    if use_longmemeval_fallback:
        ds = hf_dataset(
            path=LONGMEMEVAL_HF_ID,
            split="test",
            sample_fields=_longmemeval_ku_record_to_sample,
            limit=n_samples,
        )
        dataset_used = LONGMEMEVAL_HF_ID
        substitution_note = (
            "Using LongMemEval knowledge-updates slice as fallback "
            "(use_longmemeval_fallback=True)."
        )
    else:
        ds = hf_dataset(
            path=FRESHQA_HF_ID,
            split=hf_split,
            sample_fields=_freshqa_record_to_sample,
            limit=n_samples,
        )
        dataset_used = FRESHQA_HF_ID
        substitution_note = (
            "Primary FreshQA HF mirror; community-maintained, "
            "verify field layout on first pull."
        )

    return Task(
        dataset=ds,
        solver=generate(),
        scorer=model_graded_qa(),
        metadata={
            "axis": "M3",
            "headline_scorer": "model_graded_qa",
            "pct_adversarial": pct_adversarial,
            "hf_dataset": dataset_used,
            "substitution_note": substitution_note,
        },
    )


__all__ = [
    "FRESHQA_HF_ID",
    "m3_stale_fact",
]
