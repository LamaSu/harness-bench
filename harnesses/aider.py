"""
Aider harness adapter.

Aider is a terminal-based pair-programmer with a tight git-aware edit loop
and minimal tool surface (file edits, git, optional shell). Excellent
ablation target for "minimal-harness" baseline.

Survey: docs/02-harness-survey.md §3.1 (Aider).
Component coverage (per docs/02-harness-survey.md §4.x):
    - control_loop, reasoning, tool_surface (limited), tool_catalog (limited),
      memory (file-only), safety (git-confirm), verification (manual)
    - NO native sub_agents
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


class AiderHarness(Harness):
    """Adapter over `aider` CLI (Apache-2.0).

    Driver: spawns `aider --message-file <prompt> --yes-always
    --map-tokens 0 --no-stream`. Captures the diff stream and final
    git SHA. Token cost from `aider --tokens` (or model-side accounting).

    Ablation hooks:
        - ARM-CL-A (single-pass, no retry): set --max-chat-history-tokens=0
        - ARM-R-B (no extended thinking): use a non-thinking model id
        - ARM-TS-D (file-edit only): default; no shell/network tools
        - ARM-M-A (flat file memory): default Aider behavior
    """

    name: str = "aider"

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/aider.py:AiderHarness.initialize — see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/aider.py:AiderHarness.submit_task — see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/aider.py:AiderHarness.get_token_cost — see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/aider.py:AiderHarness.get_wall_clock — see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return layer in SUPPORTED_ABLATION_LAYERS

    def set_component(self, layer: str, arm: str) -> None:
        if layer not in SUPPORTED_ABLATION_LAYERS:
            raise UnsupportedAblationError(
                f"aider does not expose layer={layer!r} for ablation "
                "(no native sub_agents)"
            )
        raise NotImplementedError(
            f"harnesses/aider.py:set_component(layer={layer}, arm={arm}) "
            "— see docs/03-component-ablation.md"
        )


__all__ = [
    "SUPPORTED_ABLATION_LAYERS",
    "AiderHarness",
]
