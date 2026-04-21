"""
3-stage Bisociation Judge.

Bisociation outputs (BS1-BS5) are subjective: scoring needs (a) a
counterfactual ablation to control for "lucky guess", (b) a multi-judge
LLM panel with inter-rater agreement, (c) a small human-calibration set
to anchor the LLM panel.

Spec: docs/04-bench-spec.md §4.4.
References:
    - Krippendorff alpha for inter-rater agreement
    - Counterfactual-ablation pattern from causal-ML literature
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from inspect_ai.scorer import Score, Scorer, scorer, Target
    from inspect_ai.solver import TaskState
except ImportError:  # pragma: no cover
    Score = Any  # type: ignore[assignment,misc]
    Scorer = Any  # type: ignore[assignment,misc]
    Target = Any  # type: ignore[assignment,misc]
    TaskState = Any  # type: ignore[assignment,misc]

    def scorer(*_args, **_kwargs):  # type: ignore[no-redef]
        def deco(fn): return fn
        return deco

DEFAULT_JUDGE_MODELS: tuple[str, ...] = (
    "anthropic/claude-opus-4-7",
    "anthropic/claude-sonnet-4-6",
    "openai/gpt-5",
)

# Krippendorff alpha threshold below which we flag the sample as
# "judge disagreement" and route to the human-calibration queue.
ALPHA_FLAG_THRESHOLD: float = 0.6


@dataclass
class JudgeReport:
    """Per-sample 3-stage report."""
    sample_id: str
    judge_scores: dict[str, float]              # judge_model -> [0, 1]
    krippendorff_alpha: float
    counterfactual_score: float                 # ablated-context score
    counterfactual_delta: float                 # primary - counterfactual
    human_calibration_match: float | None       # if sample in cal-set
    flagged_for_human_review: bool = False
    rationales: dict[str, str] = field(default_factory=dict)


def _stage1_counterfactual(
    sample: Any,
    harness_response: str,
) -> float:
    """Re-run the same scorer with the bisociation-relevant context REMOVED.

    If the harness scores nearly as well WITHOUT the bisociation cue, the
    cue wasn't actually used — score is "lucky guess". The headline score
    becomes (primary - counterfactual), clamped to [0, 1].
    """
    raise NotImplementedError(
        "scorers/bisociation_judge.py:_stage1_counterfactual "
        "— see docs/04-bench-spec.md §4.4"
    )


def _stage2_judge_panel(
    sample: Any,
    harness_response: str,
    judge_models: tuple[str, ...] = DEFAULT_JUDGE_MODELS,
) -> dict[str, float]:
    """Run N judges in parallel; collect per-judge scores in [0, 1].

    Each judge is given the same rubric (see prompts/judge_rubric_bs.md).
    Returns {model_id: score}. Caller computes Krippendorff alpha.
    """
    raise NotImplementedError(
        "scorers/bisociation_judge.py:_stage2_judge_panel "
        "— see docs/04-bench-spec.md §4.4"
    )


def _stage3_human_calibration(
    sample_id: str,
    judge_scores: dict[str, float],
    calibration_set_path: str,
) -> float | None:
    """If sample is in the calibration set, compute |mean(judge) - human|.

    Used to detect systematic LLM-judge bias and to gate publication of
    a benchmark version (we require <= 0.10 mean abs error on calibration
    set before shipping a new version).
    """
    raise NotImplementedError(
        "scorers/bisociation_judge.py:_stage3_human_calibration "
        "— see docs/04-bench-spec.md §4.4"
    )


def _krippendorff_alpha(scores_per_judge: list[list[float]]) -> float:
    """Krippendorff's alpha for ordinal data; thin wrapper over the
    `krippendorff` package (declared in pyproject.toml).
    """
    raise NotImplementedError(
        "scorers/bisociation_judge.py:_krippendorff_alpha "
        "— see docs/04-bench-spec.md §4.4"
    )


@scorer(metrics=["accuracy", "stderr"])
def bisociation_judge(
    judge_models: tuple[str, ...] = DEFAULT_JUDGE_MODELS,
    counterfactual: bool = True,
    calibration_set_path: str = "corpus/bs_human_calibration.jsonl",
    alpha_flag_threshold: float = ALPHA_FLAG_THRESHOLD,
) -> "Scorer":
    """3-stage scorer for BS1-BS5.

    Score = mean(judge_scores) * counterfactual_delta_factor, with samples
    below alpha_flag_threshold queued for human review (not propagated to
    the headline number).
    """
    raise NotImplementedError(
        "scorers/bisociation_judge.py:bisociation_judge "
        "— see docs/04-bench-spec.md §4.4"
    )


__all__ = [
    "DEFAULT_JUDGE_MODELS",
    "ALPHA_FLAG_THRESHOLD",
    "JudgeReport",
    "bisociation_judge",
]
