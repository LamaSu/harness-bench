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
# `HuggingFaceH4/tau2-bench-data` has no parquet shards — the real data is a
# tree of per-domain `domains/<name>/tasks.json` files. `load_dataset` stalls
# ("generating train split: 1 example") when asked to infer shards. Fix: pin
# a specific domain via data_files + split="train" (the only split present).
TAU2_HF_ID = "HuggingFaceH4/tau2-bench-data"
TAU2_DEFAULT_SPLIT = "train"
TAU2_AVAILABLE_DOMAINS: tuple[str, ...] = ("airline", "retail", "telecom", "mock")
TAU2_DEFAULT_DOMAIN = "airline"


def _tau2_data_files_for(domain: str) -> str:
    """Resolve the HF tasks.json path for a given tau2 domain."""
    if domain not in TAU2_AVAILABLE_DOMAINS:
        raise ValueError(
            f"tau2 domain must be one of {TAU2_AVAILABLE_DOMAINS}; got {domain!r}"
        )
    return f"domains/{domain}/tasks.json"


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

    tau2-bench rows (from the `domains/<x>/tasks.json` files) ship with
    heavily nested JSON-as-string columns:

        id, description (json str: {purpose, ...}),
        user_scenario (json str: {persona, instructions, ...}),
        initial_state (json str | None),
        evaluation_criteria (json str: {actions, communicate_info, nl_assertions}),
        annotations (optional).

    For M4 we treat each row as a single training-or-recall sample tagged
    with `task_id` = `id`; the runner can later pair samples by task_id
    similarity to measure repeat-time vs first-time.
    """
    import json as _json

    def _maybe_json(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return _json.loads(value)
            except (ValueError, TypeError):
                return value
        return value

    description = _maybe_json(record.get("description"))
    scenario = _maybe_json(record.get("user_scenario"))
    criteria = _maybe_json(record.get("evaluation_criteria"))

    if isinstance(description, dict):
        purpose = description.get("purpose") or description.get("description") or ""
    else:
        purpose = str(description or "")

    if isinstance(scenario, dict):
        persona = scenario.get("persona") or ""
        task_block = ""
        instr = scenario.get("instructions") or {}
        if isinstance(instr, dict):
            task_block = instr.get("task_instructions") or instr.get("instructions") or ""
        elif isinstance(instr, str):
            task_block = instr
        instruction = task_block or str(scenario)
    else:
        persona = ""
        instruction = str(scenario or "")

    expected_parts: list[str] = []
    if isinstance(criteria, dict):
        for key in ("actions", "communicate_info", "nl_assertions"):
            val = criteria.get(key)
            if val:
                expected_parts.append(f"{key}: {_json.dumps(val, default=str)}")
    else:
        expected_parts.append(str(criteria or ""))
    expected = "\n".join(p for p in expected_parts if p)

    task_id = str(record.get("id") or record.get("task_id") or "")

    prompt_parts: list[str] = []
    if purpose:
        prompt_parts.append(f"Task purpose: {purpose}")
    if persona:
        prompt_parts.append(f"User persona: {persona}")
    if instruction:
        prompt_parts.append(f"User instructions:\n{instruction}")
    prompt_parts.append(
        "\nExecute the right multi-step procedure. If you have learned "
        "this procedure in a prior session, apply it directly."
    )
    prompt = "\n\n".join(prompt_parts)

    return Sample(
        input=prompt,
        target=str(expected),
        metadata={
            "axis": "M4",
            "phase": "single",  # paired downstream by task_id matching
            "domain": "tau2",
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
    tau2_domain: str = TAU2_DEFAULT_DOMAIN,
) -> "Task":
    """Inspect AI Task for axis M4.

    Two-phase: Phase A trains the skill, Phase B (after gap) tests reuse.
    Headline gate: first-time-vs-repeat performance gap <= 2x.

    AppWorld (git-only) substituted with tau2-bench (HF-resident MIT).
    See module docstring for substitution rationale. `tau2_domain` picks
    one of airline | retail | telecom | mock — the HF dataset has no
    parquet shards, so we resolve a single `domains/<d>/tasks.json` via
    the `data_files=` kwarg.

    The `include_appworld` flag is reserved — AppWorld pull is via git
    and goes through corpus/appworld at runtime, not via hf_dataset;
    ignored for v0.2.
    """
    if hf_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running M4 task."
        )

    data_files = _tau2_data_files_for(tau2_domain)

    ds = hf_dataset(
        path=TAU2_HF_ID,
        split=hf_split,
        sample_fields=_tau2_record_to_sample,
        limit=n_samples,
        data_files=data_files,
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
            "tau2_domain": tau2_domain,
            "tau2_data_files": data_files,
            "substitution_note": (
                "AppWorld is git-only per catalog #25; substituted with "
                "tau2-bench (MIT, HF-resident). tau2-bench-data on HF is "
                f"loaded per-domain via data_files={data_files!r}. "
                "M4_score (1 - repeat/first) is computed downstream by "
                "scorers/ from telemetry once training+recall samples are "
                "paired by task_id."
            ),
        },
    )


__all__ = [
    "TAU2_HF_ID",
    "TAU2_AVAILABLE_DOMAINS",
    "TAU2_DEFAULT_DOMAIN",
    "m4_procedural",
]
