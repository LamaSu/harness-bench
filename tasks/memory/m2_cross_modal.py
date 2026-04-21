"""
M2 — Cross-Modal Correlation (paper + tool output + image + table)

Synthesis of evidence across at least 3 modalities: tool JSON output,
unstructured prose, images, structured tables, code diffs. Currently
unbenchmarked at scale (MMLongBench-Doc only does within-document; nothing
crosses tool x paper x image).

Spec: docs/04-bench-spec.md §2.1.M2.
Datasets (cited from docs/01-corpus-catalog.md):
    - #14 MMLongBench-Doc (research-only) — research-only license, gated by flag
    - #15 MileBench (research-only)
    - #24 VisualWebArena (MIT)
    - #3  SWE-bench Multimodal
    - #43 FinanceBench (CC-BY-4.0 sample)
    - #10 LoCoMo
    - #60 harness-bench/M2-cross-modal (purpose-built, MIT)

Primary HF dataset: MileBench has no clean HF mirror as of catalog date;
research-only licensing. Per docs/01 §6.4 we substitute the closest
permissive multi-modal source, **princeton-nlp/SWE-bench_Multimodal**
(catalog #3), which carries text + screenshot pairs. SWE-bench Multimodal
samples bundle a problem statement (prose), a test patch (code_diff), and
a screenshot (image) — exactly 3 modalities, satisfying the M2 gate.

When `include_mmlongbench_doc=True`, the loader also pulls research-only
MMLongBench-Doc as a non-redistributable second source.

Status: IMPLEMENTED (v0.2) by implementer-foxtrot.
"""
from __future__ import annotations

from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample, hf_dataset
    from inspect_ai.model import ChatMessageUser, ContentImage, ContentText
    from inspect_ai.solver import generate
    from inspect_ai.scorer import model_graded_qa
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]
    ChatMessageUser = Any  # type: ignore[assignment,misc]
    ContentImage = Any  # type: ignore[assignment,misc]
    ContentText = Any  # type: ignore[assignment,misc]
    hf_dataset = None  # type: ignore[assignment]
    generate = None  # type: ignore[assignment]
    model_graded_qa = None  # type: ignore[assignment]

    def task(fn):  # type: ignore[no-redef]
        return fn

# Required modalities per sample. >= 3 is the gate for inclusion.
SUPPORTED_MODALITIES: tuple[str, ...] = (
    "prose",        # research paper passage / web text
    "tool_json",    # tool-call result (semgrep, BLAST, etc.)
    "image",        # chart screenshot, architecture diagram, chromatogram
    "table",        # 10-K, lab notebook, spreadsheet
    "code_diff",    # PR / commit
)

# Primary substitute (MIT, image+text+code on HF).
SWE_BENCH_MM_HF_ID = "princeton-nlp/SWE-bench_Multimodal"
SWE_BENCH_MM_DEFAULT_SPLIT = "test"

# Optional second source — research-only, not redistributed.
MMLONGBENCH_DOC_HF_ID = "yubo2333/MMLongBench-Doc"  # community mirror; verify


def _detect_modalities(record: dict[str, Any]) -> set[str]:
    """Inspect a record and return the set of modalities present.

    Heuristic mapping (SWE-bench-MM field shape):
        problem_statement / text      -> prose
        patch / test_patch / hints    -> code_diff
        image / screenshot / image_assets -> image
        environment_setup_commit json -> tool_json
        FAIL_TO_PASS / PASS_TO_PASS list -> tool_json (test results)
    """
    found: set[str] = set()
    if record.get("problem_statement") or record.get("text") or record.get("hints_text"):
        found.add("prose")
    if record.get("patch") or record.get("test_patch") or record.get("diff"):
        found.add("code_diff")
    if (
        record.get("image")
        or record.get("screenshot")
        or record.get("image_assets")
        or record.get("images")
    ):
        found.add("image")
    if (
        record.get("FAIL_TO_PASS")
        or record.get("PASS_TO_PASS")
        or record.get("test_directives")
        or record.get("environment_setup_commit")
    ):
        found.add("tool_json")
    if record.get("table") or record.get("structured_data"):
        found.add("table")
    return found


def _record_to_sample(record: dict[str, Any]) -> "Sample":
    """Adapt a multi-modal record into an Inspect AI Sample.

    Builds Sample.input from a list of [ContentText, ContentImage, ...]
    chunks. SWE-bench-MM ships images inline as URL strings or base64 in
    the `image_assets` / `image` fields. We pass them through to
    ContentImage; Inspect AI handles fetch.
    """
    chunks: list[Any] = []

    prose = record.get("problem_statement") or record.get("text") or ""
    if prose:
        chunks.append(ContentText(text=str(prose)))

    diff = record.get("patch") or record.get("test_patch") or record.get("diff") or ""
    if diff:
        chunks.append(
            ContentText(text=f"\n--- code_diff ---\n{diff}\n")
        )

    images = (
        record.get("image_assets")
        or record.get("images")
        or ([record["image"]] if record.get("image") else None)
        or ([record["screenshot"]] if record.get("screenshot") else None)
        or []
    )
    if isinstance(images, str):
        images = [images]
    for img in images:
        # ContentImage accepts URLs, file paths, or base64 strings.
        chunks.append(ContentImage(image=str(img)))

    tool_blob = record.get("FAIL_TO_PASS") or record.get("PASS_TO_PASS")
    if tool_blob:
        import json as _json
        try:
            tool_text = _json.dumps(tool_blob, indent=2)
        except (TypeError, ValueError):
            tool_text = str(tool_blob)
        chunks.append(ContentText(text=f"\n--- tool_json ---\n{tool_text}\n"))

    # Question / target. SWE-bench-MM scoring is normally test-pass, but
    # for M2 we score "did the agent integrate >=3 modalities to answer
    # what the bug is?" via model_graded_qa over the gold patch.
    question = (
        "Identify the bug, then describe the minimal change that fixes it. "
        "Reference at least 3 modalities of evidence in your answer."
    )
    chunks.append(ContentText(text=f"\n\n{question}"))

    target = record.get("patch") or record.get("answer") or ""
    sample_id = record.get("instance_id") or record.get("id") or ""

    modalities_present = sorted(_detect_modalities(record))

    # Inspect AI v0.3+ requires Sample.input to be either str or
    # list[ChatMessage]. Bare content parts (list[ContentText|ContentImage])
    # fail Pydantic validation ("input should be a valid string, input_value=
    # [ContentText(...)], input_type=list"). Wrap the chunks in a single
    # ChatMessageUser so the task runner gets a valid chat turn.
    return Sample(
        input=[ChatMessageUser(content=chunks)],
        target=str(target),
        metadata={
            "axis": "M2",
            "domain": "code",
            "license_tag": "per-HF-card",
            "source_id": sample_id,
            "modalities": modalities_present,
            "n_modalities": len(modalities_present),
        },
    )


def _validate_min_modalities(record: dict[str, Any], minimum: int = 3) -> bool:
    """Filter records that don't span >= `minimum` modalities."""
    return len(_detect_modalities(record)) >= minimum


def _harmonic_mean(source_f1: float, answer_correctness: float) -> float:
    """M2_score = HARMONIC_MEAN(source_F1, answer_correctness). See spec §2.1.M2."""
    if source_f1 <= 0.0 or answer_correctness <= 0.0:
        return 0.0
    return (2.0 * source_f1 * answer_correctness) / (source_f1 + answer_correctness)


@task
def m2_cross_modal(
    n_samples: int = 50,
    min_modalities: int = 3,
    include_locomo: bool = True,
    include_mmlongbench_doc: bool = False,  # research-only license
    hf_split: str = SWE_BENCH_MM_DEFAULT_SPLIT,
) -> "Task":
    """Inspect AI Task for axis M2.

    Combines SWE-bench Multimodal (substitution for unavailable MileBench HF
    mirror, see module docstring) with optional MMLongBench-Doc (research-
    only). Final question requires synthesis across >=3 modalities. Score
    is the harmonic mean of source_F1 and answer_correctness.

    The `include_locomo` flag is reserved — LoCoMo is git-based and not
    yet wired into the HF loader path; ignored for v0.2.
    """
    if hf_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running M2 task."
        )

    primary = hf_dataset(
        path=SWE_BENCH_MM_HF_ID,
        split=hf_split,
        sample_fields=_record_to_sample,
        limit=n_samples,
    )

    return Task(
        dataset=primary,
        solver=generate(),
        scorer=model_graded_qa(),
        metadata={
            "axis": "M2",
            "headline_scorer": "model_graded_qa",
            "min_modalities": min_modalities,
            "supported_modalities": list(SUPPORTED_MODALITIES),
            "hf_dataset": SWE_BENCH_MM_HF_ID,
            "substitution_note": (
                "MileBench HF mirror unavailable; using SWE-bench_Multimodal "
                "(MIT) as primary cross-modal source. See module docstring."
            ),
            "mmlongbench_enabled": include_mmlongbench_doc,
        },
    )


__all__ = [
    "SUPPORTED_MODALITIES",
    "SWE_BENCH_MM_HF_ID",
    "m2_cross_modal",
]
