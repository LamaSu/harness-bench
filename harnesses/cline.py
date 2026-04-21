"""
Cline harness adapter.

Cline (formerly Claude Dev) — VS Code extension agent with computer-use,
file edits, terminal, browser. Plan/Act mode separation. Apache-2.0.

Survey: docs/02-harness-survey.md §3.3 (Cline).
Component coverage:
    - control_loop (plan/act), reasoning, tool_surface (rich incl. browser),
      tool_catalog (extensible MCP), memory (per-conversation),
      safety (per-tool approval), verification (manual diff review)
    - LIMITED native sub_agents (extension-mediated)
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
    "verification",
)


class ClineHarness(Harness):
    """Adapter over Cline (Apache-2.0).

    Driver strategy: Cline is a VS Code extension; for headless eval, we
    drive it via the `cline-cli` companion (or the extension's
    socket API in headless VS Code mode). Captures tool-call events
    from the Cline log stream.

    Ablation hooks:
        - ARM-CL-D (plan-only vs act-only vs plan+act): toggle mode
        - ARM-TS-A (computer-use enabled): wire browser tool on/off
        - ARM-S-C (per-tool approval): toggle auto-approve list
    """

    name: str = "cline"

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/cline.py:ClineHarness.initialize "
            "— see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/cline.py:ClineHarness.submit_task "
            "— see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/cline.py:ClineHarness.get_token_cost "
            "— see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/cline.py:ClineHarness.get_wall_clock "
            "— see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return layer in SUPPORTED_ABLATION_LAYERS

    def set_component(self, layer: str, arm: str) -> None:
        if layer not in SUPPORTED_ABLATION_LAYERS:
            raise UnsupportedAblationError(
                f"cline does not expose layer={layer!r} (sub-agents extension-mediated)"
            )
        raise NotImplementedError(
            f"harnesses/cline.py:set_component(layer={layer}, arm={arm}) "
            "— see docs/03-component-ablation.md"
        )


__all__ = [
    "SUPPORTED_ABLATION_LAYERS",
    "ClineHarness",
]
