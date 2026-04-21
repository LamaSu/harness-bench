"""
Abstract Harness base class — common interface for all 8 adapters.

Spec: docs/04-bench-spec.md §3.1.
Status: STUB — concrete subclasses (claude_code_go.py etc.) implement these.
The ABC itself is fully typed and importable.

Notes
-----
- `submit_task` returns an async iterator of Event so the runner can
  stream observations into the OpenInference OTLP exporter as they happen.
- `get_token_cost` and `get_wall_clock` are CUMULATIVE since `initialize()`,
  not per-task. The runner snapshots before+after each task to derive deltas.
- `set_component` lets the ablation runner toggle one of the 8 layers
  (control_loop, reasoning, tool_surface, tool_catalog, memory, sub_agents,
  safety, verification) — see docs/02-harness-survey.md §4.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


# 8 architectural layers — per docs/02-harness-survey.md §1
HARNESS_LAYERS: tuple[str, ...] = (
    "control_loop",
    "reasoning",
    "tool_surface",
    "tool_catalog",
    "memory",
    "sub_agents",
    "safety",
    "verification",
)


@dataclass(frozen=True)
class Cost:
    """Cumulative token-and-dollar cost for a harness session."""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    dollars: float = 0.0

    def delta(self, other: "Cost") -> "Cost":
        """Return self - other element-wise (clamped at 0)."""
        return Cost(
            input_tokens=max(0, self.input_tokens - other.input_tokens),
            output_tokens=max(0, self.output_tokens - other.output_tokens),
            cached_input_tokens=max(0, self.cached_input_tokens - other.cached_input_tokens),
            dollars=max(0.0, self.dollars - other.dollars),
        )


@dataclass
class Event:
    """One discrete observation streamed from a running harness."""
    kind: str  # "tool_call" | "tool_result" | "thinking" | "message" | "completion"
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp_unix: float = 0.0
    span_id: str | None = None  # for OpenInference OTLP correlation


class Tool(Protocol):
    """The shape we expect of any tool exposed to a harness.

    Mirrors Inspect AI's `inspect_ai.tool.Tool` shape; we keep our own
    structural Protocol so adapters that don't import inspect_ai still
    typecheck.
    """
    name: str
    description: str
    input_schema: dict[str, Any]


class UnsupportedAblationError(Exception):
    """Raised by `set_component` when a layer/arm pair isn't supported."""
    def __init__(self, harness: str, layer: str, arm: str) -> None:
        super().__init__(
            f"Harness '{harness}' does not support arm '{arm}' on layer '{layer}'."
        )
        self.harness = harness
        self.layer = layer
        self.arm = arm


class Harness(ABC):
    """Abstract base for any agentic harness wrapped by harness-bench.

    Concrete subclasses (one per adapter under harnesses/<name>.py) must
    implement all 6 abstract methods.

    Lifecycle:
        h = HarnessSubclass(model="claude-opus-4-7")
        h.initialize(sandbox)
        async for event in h.submit_task(prompt, tools):
            ...  # consume
        cost = h.get_token_cost()
        elapsed = h.get_wall_clock()
    """

    name: str = "abstract-harness"

    def __init__(self, model: str, **kwargs: Any) -> None:
        """Create with target model + provider-specific kwargs."""
        self.model = model
        self._initialized = False
        # Per-layer arm settings, populated by set_component()
        self._arms: dict[str, str] = {}
        for layer in HARNESS_LAYERS:
            self._arms[layer] = "default"

    @abstractmethod
    def initialize(self, sandbox: Any) -> None:
        """Spin up workspace, install harness deps, configure model.

        Idempotent — safe to call multiple times.

        :param sandbox: Inspect AI sandbox (Docker/K8s/Modal) handle.
        """
        raise NotImplementedError("base.Harness.initialize — see docs/04-bench-spec.md §3.1")

    @abstractmethod
    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        """Submit a single task. Stream Events until the harness terminates.

        :param prompt: human-readable task description / system prompt.
        :param tools: list of Tool objects the harness may expose to the model.
        :yields: Event objects in order of occurrence.
        """
        raise NotImplementedError("base.Harness.submit_task — see docs/04-bench-spec.md §3.1")

    @abstractmethod
    def get_token_cost(self) -> Cost:
        """Cumulative cost since initialize()."""
        raise NotImplementedError("base.Harness.get_token_cost — see docs/04-bench-spec.md §3.1")

    @abstractmethod
    def get_wall_clock(self) -> float:
        """Cumulative wall-clock seconds since initialize()."""
        raise NotImplementedError("base.Harness.get_wall_clock — see docs/04-bench-spec.md §3.1")

    @abstractmethod
    def supports_component_ablation(self, layer: str) -> bool:
        """True iff the harness can toggle the named layer.

        :param layer: one of HARNESS_LAYERS.
        """
        raise NotImplementedError("base.Harness.supports_component_ablation — see docs/04-bench-spec.md §3.1")

    @abstractmethod
    def set_component(self, layer: str, arm: str) -> None:
        """Set the named layer to the named arm.

        :raises UnsupportedAblationError: if the (layer, arm) pair isn't
            supported by this harness.
        """
        raise NotImplementedError("base.Harness.set_component — see docs/04-bench-spec.md §3.1")


__all__ = [
    "Cost",
    "Event",
    "Harness",
    "Tool",
    "UnsupportedAblationError",
    "HARNESS_LAYERS",
]
