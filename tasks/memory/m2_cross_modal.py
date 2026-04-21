"""
M2 — Cross-Modal Correlation (paper + tool output + image + table)

Synthesis of evidence across at least 3 modalities: tool JSON output,
unstructured prose, images, structured tables, code diffs. Currently
unbenchmarked at scale (MMLongBench-Doc only does within-document; nothing
crosses tool x paper x image).

Spec: docs/04-bench-spec.md §2.1.M2.
Datasets (cited from docs/01-corpus-catalog.md):
    - #14 MMLongBench-Doc (research-only)
    - #15 MileBench (research-only)
    - #24 VisualWebArena (MIT)
    - #3  SWE-bench Multimodal
    - #43 FinanceBench (CC-BY-4.0 sample)
    - #10 LoCoMo
    - #60 harness-bench/M2-cross-modal (purpose-built, MIT)
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample
    from inspect_ai.model import ContentImage, ContentText
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]
    ContentImage = Any  # type: ignore[assignment,misc]
    ContentText = Any  # type: ignore[assignment,misc]

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


def _record_to_sample(record: dict[str, Any]) -> "Sample":
    """Adapt a multi-modal record into an Inspect AI Sample.

    Builds Sample.input from a list of [ContentText, ContentImage, ...]
    chunks. Image paths point into corpus/<dataset>/images/.
    """
    raise NotImplementedError(
        "tasks/memory/m2_cross_modal.py:_record_to_sample — see docs/04-bench-spec.md §2.1.M2"
    )


def _validate_min_modalities(record: dict[str, Any], minimum: int = 3) -> bool:
    """Filter records that don't span >= `minimum` modalities."""
    raise NotImplementedError(
        "tasks/memory/m2_cross_modal.py:_validate_min_modalities — see docs/04-bench-spec.md §2.1.M2"
    )


def _harmonic_mean(source_f1: float, answer_correctness: float) -> float:
    """M2_score = HARMONIC_MEAN(source_F1, answer_correctness). See spec §2.1.M2."""
    raise NotImplementedError(
        "tasks/memory/m2_cross_modal.py:_harmonic_mean — see docs/04-bench-spec.md §2.1.M2"
    )


@task
def m2_cross_modal(
    n_samples: int = 50,
    min_modalities: int = 3,
    include_locomo: bool = True,
    include_mmlongbench_doc: bool = False,  # research-only license
) -> "Task":
    """Inspect AI Task for axis M2.

    Combines LoCoMo multi-modal dialogues with VisualWebArena screenshot
    contexts and constructed harness-bench/M2 samples. Final question
    requires synthesis across >=3 modalities. Score is harmonic mean of
    source_F1 and answer_correctness.
    """
    raise NotImplementedError(
        "tasks/memory/m2_cross_modal.py:m2_cross_modal — see docs/04-bench-spec.md §2.1.M2"
    )


__all__ = [
    "SUPPORTED_MODALITIES",
    "m2_cross_modal",
]
