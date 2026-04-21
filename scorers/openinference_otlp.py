"""
OpenInference / OTLP exporter scorer.

Not a "scorer" in the traditional sense: this is a side-effect Inspect AI
scorer that pipes per-sample trajectory events to an OTLP endpoint
(Phoenix, Arize, etc.) using the OpenInference semantic conventions for
LLM trajectories. Enables post-hoc trajectory replay & comparison
across harnesses.

Spec: docs/04-bench-spec.md §4.5.
References:
    - OpenInference spec: https://github.com/Arize-ai/openinference
    - Phoenix open-source: https://github.com/Arize-ai/phoenix
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

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

# OpenInference span_kind values we emit.
SPAN_KINDS: tuple[str, ...] = (
    "AGENT",
    "CHAIN",
    "LLM",
    "TOOL",
    "RETRIEVER",
    "EMBEDDING",
    "GUARDRAIL",
    "EVALUATOR",
)


def _harness_event_to_otel_span(event: dict[str, Any]) -> dict[str, Any]:
    """Map a harness Event (see harnesses/base.py) to an OpenInference span.

    Event.kind -> span_kind mapping:
        "model_call"       -> LLM
        "tool_call"        -> TOOL
        "tool_result"      -> TOOL (child)
        "subagent_spawn"   -> AGENT (child)
        "guardrail_check"  -> GUARDRAIL
        "verifier_check"   -> EVALUATOR
        "memory_read"      -> RETRIEVER
        "memory_write"     -> CHAIN

    Span attributes follow OpenInference v1 conventions
    (input.value, output.value, llm.token_count.{prompt,completion},
    tool.name, retrieval.documents, etc.).
    """
    raise NotImplementedError(
        "scorers/openinference_otlp.py:_harness_event_to_otel_span "
        "— see docs/04-bench-spec.md §4.5"
    )


@scorer(metrics=["accuracy", "stderr"])
def openinference_otlp(
    endpoint: str = "http://localhost:6006/v1/traces",
    project_name: str = "agentic-harness-bench",
    pass_through_score: float = 1.0,
) -> "Scorer":
    """Side-effect scorer: emits OTLP spans, returns pass_through_score
    for every sample (so it composes with primary scorers without
    affecting headline numbers).

    Configuration:
        - endpoint: OTLP HTTP collector (Phoenix default 6006)
        - project_name: Phoenix project to land traces in
        - resource attributes: {harness.name, harness.arms.<layer>,
                                axis, sample_id, run_id}
    """
    raise NotImplementedError(
        "scorers/openinference_otlp.py:openinference_otlp "
        "— see docs/04-bench-spec.md §4.5"
    )


__all__ = [
    "SPAN_KINDS",
    "openinference_otlp",
]
