"""
Scorer registry for harness-bench.

5 scorers, all importable as `from scorers import pass_at_1, time_horizon, ...`.

Spec: docs/04-bench-spec.md §4.
Status: STUB — scorer functions raise NotImplementedError; to be
implemented by the next agent (implementer-* family).
"""
from __future__ import annotations

from scorers.pass_at_1 import pass_at_1
from scorers.time_horizon import time_horizon, TimeHorizonTier
from scorers.pareto import pareto_collector, ParetoPoint
from scorers.bisociation_judge import (
    bisociation_judge,
    BisociationJudgeResult,
    counterfactual_ablation,
    llm_panel_score,
    human_calibration_factor,
)
from scorers.openinference_otlp import openinference_otlp_exporter

SCORER_REGISTRY = {
    "pass_at_1": pass_at_1,
    "time_horizon": time_horizon,
    "pareto_collector": pareto_collector,
    "bisociation_judge": bisociation_judge,
    "openinference_otlp": openinference_otlp_exporter,
}

__all__ = [
    "SCORER_REGISTRY",
    "pass_at_1",
    "time_horizon",
    "TimeHorizonTier",
    "pareto_collector",
    "ParetoPoint",
    "bisociation_judge",
    "BisociationJudgeResult",
    "counterfactual_ablation",
    "llm_panel_score",
    "human_calibration_factor",
    "openinference_otlp_exporter",
]
