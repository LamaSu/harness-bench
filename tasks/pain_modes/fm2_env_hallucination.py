"""
FM2 — Environmental Hallucination at Scale

In a 1M+ token context with thousands of files, the agent confidently
references files/symbols/APIs that DO NOT EXIST in the workspace. Closely
linked to long-context "needle in haystack" pathologies but the failure
mode is FABRICATION (positive assertion of false), not retrieval miss.

Spec: docs/04-bench-spec.md §2.2.FM2.
Datasets (cited from docs/01-corpus-catalog.md):
    - #11 BABILong (synthetic 0K-10M, permissive)
    - #12 RULER (Apache-2.0)
    - #13 InfiniteBench (research-only)
    - #6  RepoBench v1.1 (CC-BY-NC-ND-4.0 — eval-only)
    - #7  Long Code Arena (mixed permissive)
    - #5  BigCodeBench (Apache-2.0; extended-context experiments)
    - #1  SWE-bench Verified / #2 SWE-bench Pro (real large repos)
    - #59 harness-bench/FM2-fabrication (purpose-built, MIT)
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

# Default context sizes for stress (per spec §2.2.FM2). -1 = model max.
DEFAULT_CONTEXT_SIZES_TOKENS: tuple[int, ...] = (
    256_000,
    1_000_000,
    -1,
)


def _build_phantom_workspace(
    real_repo_path: str,
    n_phantom_paths: int = 25,
    n_phantom_symbols: int = 50,
    seed: int = 0,
) -> dict[str, Any]:
    """Construct a workspace manifest that includes plausible-but-absent paths.

    Returns {real_files, phantom_files, real_symbols, phantom_symbols, oracle}.
    Phantom paths look like neighbors of real ones (e.g., real `src/auth.ts` ->
    phantom `src/auth_v2.ts`). Used to bait fabrication.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm2_env_hallucination.py:_build_phantom_workspace "
        "— see docs/04-bench-spec.md §2.2.FM2"
    )


def _question_about_phantom(workspace_manifest: dict[str, Any]) -> str:
    """Generate a probe question that, if answered confidently, reveals fabrication.

    e.g., "Summarize what `src/auth_v2.ts::loginV2` does." (the file does NOT
    exist; the correct response is "no such file" or a tool call that confirms).
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm2_env_hallucination.py:_question_about_phantom "
        "— see docs/04-bench-spec.md §2.2.FM2"
    )


def _score_fm2(
    fabrication_rate_per_size: dict[int, float],
    abstention_rate_per_size: dict[int, float],
) -> dict[str, float]:
    """FM2 score: fabrication-rate curve over context sizes + AUC. See spec §2.2.FM2.

    Headline: fabrication_rate <= 5% at 1M tokens; abstention >= 80% on phantom
    probes; degradation curve flatter than +5pp per context-size doubling.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm2_env_hallucination.py:_score_fm2 "
        "— see docs/04-bench-spec.md §2.2.FM2"
    )


@task
def fm2_env_hallucination(
    context_sizes_tokens: tuple[int, ...] = DEFAULT_CONTEXT_SIZES_TOKENS,
    samples_per_size: int = 40,
    phantom_density: float = 0.10,
    include_swe_bench_repos: bool = True,
) -> "Task":
    """Inspect AI Task for axis FM2.

    Inflates a real repo (RepoBench / Long Code Arena / SWE-bench) with
    phantom files & symbols, then probes for confident references.
    Headline gate: <=5% fabrication at 1M tokens with >=80% abstention.
    """
    raise NotImplementedError(
        "tasks/pain_modes/fm2_env_hallucination.py:fm2_env_hallucination "
        "— see docs/04-bench-spec.md §2.2.FM2"
    )


__all__ = [
    "DEFAULT_CONTEXT_SIZES_TOKENS",
    "fm2_env_hallucination",
]
