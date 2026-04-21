"""
Devin / Replit Agent 3 (closed-source) harness adapter — BLACKBOX.

Devin (Cognition) and Replit Agent 3 are hosted, closed-source autonomous
agents. We measure them only via the public API: send a task, poll for
completion, read the resulting diff/PR/artifact + invoice cost.

Survey: docs/02-harness-survey.md §3.8 (Devin / Replit Agent 3).
Component coverage: BLACKBOX.
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from harnesses.base import Cost, Event, Harness, Tool, UnsupportedAblationError

# Which of the two backends to drive. Selected at construction time.
SUPPORTED_BACKENDS: tuple[str, ...] = ("devin", "replit-agent-3")


class DevinBlackboxHarness(Harness):
    """Adapter over Devin OR Replit Agent 3 hosted APIs.

    Driver:
        - Devin: POST /v1/sessions with task; poll /v1/sessions/{id} until
          status==completed. Diff in `output.diff`. Cost in `usage.acu`.
        - Replit Agent 3: similar shape; see Replit docs.

    Cost: ACU (Devin) or Replit-credits, converted to dollars via published
    rate at run time. Token-level cost not exposed.

    NO ABLATION ARMS. Use only for headline metrics. The headline-only
    nature is also why we DEFAULT to a 50-sample-per-axis ceiling for
    blackbox harnesses (cost containment) — see scripts/run_full_sweep.sh.
    """

    name: str = "devin-blackbox"

    def __init__(self, backend: str = "devin") -> None:
        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(f"unknown blackbox backend: {backend!r}")
        self.backend = backend

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/devin_blackbox.py:DevinBlackboxHarness.initialize "
            "— see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/devin_blackbox.py:DevinBlackboxHarness.submit_task "
            "— see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/devin_blackbox.py:DevinBlackboxHarness.get_token_cost "
            "— see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/devin_blackbox.py:DevinBlackboxHarness.get_wall_clock "
            "— see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return False

    def set_component(self, layer: str, arm: str) -> None:
        raise UnsupportedAblationError(
            "devin/replit-agent-3 are closed-source; component ablation not supported"
        )


__all__ = [
    "SUPPORTED_BACKENDS",
    "DevinBlackboxHarness",
]
