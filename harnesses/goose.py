"""
Goose harness adapter.

Goose by Block — open-source agent with extension marketplace, MCP-native,
multi-LLM. Apache-2.0.

Survey: docs/02-harness-survey.md §3.5 (Goose).
Component coverage:
    - control_loop, reasoning, tool_surface (extensions),
      tool_catalog (MCP marketplace), memory (per-session + extension),
      safety (per-tool), verification (limited)
    - LIMITED native sub_agents (extensions can simulate)
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from harnesses.base import Cost, Event, Harness, Tool, UnsupportedAblationError

SUPPORTED_ABLATION_LAYERS: tuple[str, ...] = (
    "control_loop",
    "reasoning",
    "tool_surface",
    "tool_catalog",
    "memory",
    "safety",
)


class GooseHarness(Harness):
    """Adapter over Goose (Apache-2.0).

    Driver strategy: Goose has a CLI (`goose run -t <prompt>`). Telemetry
    via Goose's local event log. Extensions loaded via `goose extension`.

    Ablation hooks:
        - ARM-TC-B (extension marketplace breadth): load N extensions
        - ARM-R-D (model id swap): set GOOSE_MODEL env
        - ARM-M-A (no working memory layer): default
    """

    name: str = "goose"

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/goose.py:GooseHarness.initialize "
            "— see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/goose.py:GooseHarness.submit_task "
            "— see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/goose.py:GooseHarness.get_token_cost "
            "— see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/goose.py:GooseHarness.get_wall_clock "
            "— see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return layer in SUPPORTED_ABLATION_LAYERS

    def set_component(self, layer: str, arm: str) -> None:
        if layer not in SUPPORTED_ABLATION_LAYERS:
            raise UnsupportedAblationError(
                f"goose does not expose layer={layer!r}"
            )
        raise NotImplementedError(
            f"harnesses/goose.py:set_component(layer={layer}, arm={arm}) "
            "— see docs/03-component-ablation.md"
        )


__all__ = [
    "SUPPORTED_ABLATION_LAYERS",
    "GooseHarness",
]
