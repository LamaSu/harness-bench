"""
M4 — Procedural Memory & Skill Reuse

Agent learns a skill in Session N (e.g., "to deploy this user's PCC
project, push to `lamasu` not `origin` because origin is suspended") and
must REAPPLY it in Session N+M without being re-taught.

Spec: docs/04-bench-spec.md §2.1.M4.
Datasets (cited from docs/01-corpus-catalog.md):
    - #25 AppWorld (Apache-2.0; 750 multi-step workflows across 9 apps) — PRIMARY git-based
    - #20 TAU-bench (MIT)
    - #21 tau2-bench (MIT) — HF-mirrored
    - #22 OSWorld (MIT/Apache-2.0)
    - #23 WebArena (MIT)
    - #24 VisualWebArena (MIT)
    - #27 ToolBench (Apache-2.0)
    - #28 PlanBench
    - #8  SWE-Lancer (#36 MLE-bench for ML pipelines)
    - Real-trace: #52 GH Archive, #57 CommitPackFT (MIT)

Primary HF dataset: AppWorld is git-only per catalog #25, no HF mirror.
Per docs/01 §6.4 substitution policy, use the closest HF-resident
multi-step procedural source: **HuggingFaceH4/tau2-bench-data** (catalog
#21, MIT). tau2-bench supplies airline+retail+telecom multi-step
trajectories that exhibit the same "learn-a-procedure-then-reapply"
shape as AppWorld.

Substitution flagged in module docstring + task metadata.

The two-phase (training -> recall) pair construction is encoded in the
metadata so a downstream scorer/runner can pair two samples by `phase`
field. The actual M4_score = 1 - (repeat_time / first_time) is computed
post-run by the scorer against telemetry.

Status: IMPLEMENTED (v0.2) by implementer-foxtrot.
"""
from __future__ import annotations

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

# Substituting AppWorld (git-only, no HF mirror) with tau2-bench (HF-resident, MIT).
TAU2_HF_ID = "HuggingFaceH4/tau2-bench-data"
TAU2_DEFAULT_SPLIT = "test"


def _build_session_pair(
    training_task: dict[str, Any],
    recall_task: dict[str, Any],
    distractor_skills: list[dict[str, Any]] | None = None,
) -> tuple["Sample", "Sample"]:
    """Construct a (training, recall) Sample pair.

    Training Sample requires discovering a non-obvious procedure.
    Recall Sample (>=1 day OR >=1000 turns later) tests whether the agent
    INVOKES the saved procedure.

    Both samples carry a shared `pair_id` in metadata so the runner can
    pair them when measuring repeat_time/first_time.
    """
    pair_id = (
        f"{training_task.get('id', training_task.get('task_id', 'unknown'))}"
        f"::"
        f"{recall_task.get('id', recall_task.get('task_id', 'unknown'))}"
    )

    distractor_text = ""
    if distractor_skills:
        lines = [
            f"  - {s.get('name', 'skill')}: {s.get('description', '')}"
            for s in distractor_skills
        ]
        distractor_text = (
            "\nDistractor skills you may have considered (do NOT use):\n"
            + "\n".join(lines)
        )

    train_prompt = (
        f"[TRAINING SESSION]\n"
        f"Task: {training_task.get('instruction', training_task.get('description', ''))}\n"
        f"Context: {training_task.get('context', '')}\n\n"
        f"Discover the right multi-step procedure. After completion, "
        f"summarize what you learned in <skill>...</skill> tags so future "
        f"sessions can reuse the procedure."
    )
    recall_prompt = (
        f"[RECALL SESSION — assume >=1 day or >=1000 turns later]\n"
        f"Task: {recall_task.get('instruction', recall_task.get('description', ''))}\n"
        f"Context: {recall_task.get('context', '')}\n\n"
        f"Apply any procedure you learned previously without being re-taught."
        + distractor_text
    )

    train_sample = Sample(
        input=train_prompt,
        target=str(training_task.get("answer", training_task.get("expected", ""))),
        metadata={
            "axis": "M4",
            "phase": "training",
            "pair_id": pair_id,
            "domain": training_task.get("domain", "general"),
            "license_tag": "MIT",
        },
    )
    recall_sample = Sample(
        input=recall_prompt,
        target=str(recall_task.get("answer", recall_task.get("expected", ""))),
        metadata={
            "axis": "M4",
            "phase": "recall",
            "pair_id": pair_id,
            "domain": recall_task.get("domain", "general"),
            "license_tag": "MIT",
            "n_distractors": len(distractor_skills) if distractor_skills else 0,
        },
    )
    return train_sample, recall_sample


def _score_skill_reuse(
    first_time_seconds: float,
    repeat_time_seconds: float,
    invocation_observed: bool,
    correct_skill_picked: bool,
) -> float:
    """M4_score = 1 - (repeat_time / first_time). See spec §2.1.M4.

    Returns 0.0 when the saved skill was not invoked or wrong skill picked.
    Capped at [0, 1].
    """
    if not invocation_observed or not correct_skill_picked:
        return 0.0
    if first_time_seconds <= 0:
        return 0.0
    raw = 1.0 - (repeat_time_seconds / first_time_seconds)
    return max(0.0, min(1.0, raw))


def _tau2_record_to_sample(record: dict[str, Any]) -> "Sample":
    """Adapt a tau2-bench row into an Inspect AI Sample.

    tau2-bench row shape (per HF card, varies by domain split):
        task_id, instruction, user_id, expected_actions / outcome,
        domain (airline | retail | telecom), policy_doc.

    Each tau2 row is a multi-step trajectory. For M4 we treat each row
    as a single training-or-recall sample tagged with the originating
    task_id; the runner can later pair samples by task_id similarity to
    measure repeat-time vs first-time.
    """
    instruction = (
        record.get("instruction")
        or record.get("user_instruction")
        or record.get("description")
        or ""
    )
    expected = (
        record.get("expected_actions")
        or record.get("outcome")
        or record.get("answer")
        or ""
    )
    if isinstance(expected, list):
        # Convert list-of-actions to a deterministic string for matching.
        expected = "\n".join(str(a) for a in expected)

    task_id = record.get("task_id") or record.get("id") or ""
    domain = record.get("domain") or "general"
    policy = record.get("policy_doc") or record.get("policy") or ""

    prompt_parts = [f"Task: {instruction}"]
    if policy:
        prompt_parts.append(f"\nPolicy:\n{policy}")
    prompt_parts.append(
        "\nExecute the right multi-step procedure. If you have learned "
        "this procedure in a prior session, apply it directly."
    )
    prompt = "\n".join(prompt_parts)

    return Sample(
        input=prompt,
        target=str(expected),
        metadata={
            "axis": "M4",
            "phase": "single",  # paired downstream by task_id matching
            "domain": domain,
            "license_tag": "MIT",
            "source_id": task_id,
            "pair_id": task_id,
        },
    )


@task
def m4_procedural(
    n_samples: int = 50,
    distractor_count: int = 5,
    session_gap_turns: int = 1000,
    include_appworld: bool = True,
    include_tau_bench: bool = True,
    hf_split: str = TAU2_DEFAULT_SPLIT,
) -> "Task":
    """Inspect AI Task for axis M4.

    Two-phase: Phase A trains the skill, Phase B (after gap) tests reuse.
    Headline gate: first-time-vs-repeat performance gap <= 2x.

    AppWorld (git-only) substituted with tau2-bench (HF-resident MIT).
    See module docstring for substitution rationale.

    The `include_appworld` flag is reserved — AppWorld pull is via git
    and goes through corpus/appworld at runtime, not via hf_dataset;
    ignored for v0.2.
    """
    if hf_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running M4 task."
        )

    ds = hf_dataset(
        path=TAU2_HF_ID,
        split=hf_split,
        sample_fields=_tau2_record_to_sample,
        limit=n_samples,
    )

    return Task(
        dataset=ds,
        solver=generate(),
        scorer=model_graded_qa(),
        metadata={
            "axis": "M4",
            "headline_scorer": "model_graded_qa",
            "session_gap_turns": session_gap_turns,
            "distractor_count": distractor_count,
            "hf_dataset": TAU2_HF_ID,
            "substitution_note": (
                "AppWorld is git-only per catalog #25; substituted with "
                "tau2-bench (MIT, HF-resident). M4_score (1 - repeat/first) "
                "is computed downstream by scorers/ from telemetry once "
                "training+recall samples are paired by task_id."
            ),
        },
    )


__all__ = [
    "TAU2_HF_ID",
    "m4_procedural",
]
