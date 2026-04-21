"""
Continue.dev harness adapter.

Continue — open-source IDE assistant (VS Code, JetBrains) with
configurable agent mode, custom slash commands, model marketplace.
Apache-2.0.

Survey: docs/02-harness-survey.md §3.4 (Continue.dev).
Component coverage:
    - control_loop (configurable), reasoning, tool_surface (file/terminal),
      tool_catalog (configurable + MCP), memory (per-session),
      safety (configurable approve), verification (manual)
    - LIMITED native sub_agents
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


class ContinueDevHarness(Harness):
    """Adapter over Continue.dev (Apache-2.0).

    Driver strategy: Continue ships a `continue-cli` for headless
    invocation. Configuration via `~/.continue/config.json`. Events
    captured via Continue's telemetry stream (when opted-in locally).

    Ablation hooks:
        - ARM-TC-A (catalog scope): swap config tool list
        - ARM-R-A (single model vs router): toggle model strategy
        - ARM-M-A (file-only memory): default
    """

    name: str = "continue-dev"

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/continue_dev.py:ContinueDevHarness.initialize "
            "— see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/continue_dev.py:ContinueDevHarness.submit_task "
            "— see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/continue_dev.py:ContinueDevHarness.get_token_cost "
            "— see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/continue_dev.py:ContinueDevHarness.get_wall_clock "
            "— see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return layer in SUPPORTED_ABLATION_LAYERS

    def set_component(self, layer: str, arm: str) -> None:
        if layer not in SUPPORTED_ABLATION_LAYERS:
            raise UnsupportedAblationError(
                f"continue-dev does not expose layer={layer!r} "
                "(no native sub-agents or post-action verification)"
            )
        raise NotImplementedError(
            f"harnesses/continue_dev.py:set_component(layer={layer}, arm={arm}) "
            "— see docs/03-component-ablation.md"
        )


__all__ = [
    "SUPPORTED_ABLATION_LAYERS",
    "ContinueDevHarness",
]
