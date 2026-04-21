"""
OpenHands harness adapter.

OpenHands (formerly OpenDevin) — open-source autonomous SWE agent with
docker sandbox, browser, file editor, IPython runtime. Strong baseline
on SWE-bench. MIT.

Survey: docs/02-harness-survey.md §3.2 (OpenHands).
Component coverage (per docs/02-harness-survey.md §4.x):
    - control_loop (CodeAct), reasoning, tool_surface (rich),
      tool_catalog (rich), memory (per-trajectory + condenser),
      sub_agents (delegation), safety (sandbox), verification (post-action)
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
    "sub_agents",
    "safety",
    "verification",
)


class OpenHandsHarness(Harness):
    """Adapter over OpenHands (MIT).

    Driver: invokes `python -m openhands.core.main --task <task.json>
    --runtime docker` or the headless API. Streams events from the
    OpenHands event stream JSONL. Container per-task isolation.

    Ablation hooks:
        - ARM-CL-B (CodeAct vs ReAct): swap agent_class config
        - ARM-M-C (condensation): toggle condenser plugin
        - ARM-SA-B (sub-agent delegation): toggle delegate_action
        - ARM-S-C (sandbox strict): set Docker capability profile
    """

    name: str = "openhands"

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/openhands.py:OpenHandsHarness.initialize "
            "— see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/openhands.py:OpenHandsHarness.submit_task "
            "— see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/openhands.py:OpenHandsHarness.get_token_cost "
            "— see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/openhands.py:OpenHandsHarness.get_wall_clock "
            "— see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return layer in SUPPORTED_ABLATION_LAYERS

    def set_component(self, layer: str, arm: str) -> None:
        if layer not in SUPPORTED_ABLATION_LAYERS:
            raise UnsupportedAblationError(
                f"openhands does not expose layer={layer!r}"
            )
        raise NotImplementedError(
            f"harnesses/openhands.py:set_component(layer={layer}, arm={arm}) "
            "— see docs/03-component-ablation.md"
        )


__all__ = [
    "SUPPORTED_ABLATION_LAYERS",
    "OpenHandsHarness",
]
