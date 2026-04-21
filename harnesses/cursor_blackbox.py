"""
Cursor (closed-source) harness adapter — BLACKBOX.

Cursor 2 ships as a closed IDE. We measure it ONLY via inputs/outputs
(prompt -> diff/patch + token cost from invoice / API headers). Component-
ablation arms are NOT supported (we cannot toggle internals).

Survey: docs/02-harness-survey.md §3.6 (Cursor).
Component coverage: BLACKBOX — no internal toggles exposed.
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from harnesses.base import Cost, Event, Harness, Tool, UnsupportedAblationError


class CursorBlackboxHarness(Harness):
    """Adapter over Cursor's CLI/API surface (where exposed).

    Driver options:
        1. `cursor-agent` CLI (when available; covers Cursor's autonomous
           background-agent surface). Prompts come in, diffs come out.
        2. Manual replay: human operator runs the prompt in Cursor IDE,
           exports the resulting diff. (Used for parity validation only.)

    Cost accounting:
        - Best-effort from Cursor billing API or model-side proxy headers.
        - When unavailable, we tag the run with `cost.observed=false` and
          fall back to wallclock + diff-size as proxy signals.

    NO ABLATION ARMS. Any call to `set_component` raises
    `UnsupportedAblationError`. Use this harness for headline pass@1,
    METR time-horizon, and Pareto plotting only.
    """

    name: str = "cursor-blackbox"

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/cursor_blackbox.py:CursorBlackboxHarness.initialize "
            "— see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/cursor_blackbox.py:CursorBlackboxHarness.submit_task "
            "— see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/cursor_blackbox.py:CursorBlackboxHarness.get_token_cost "
            "— see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/cursor_blackbox.py:CursorBlackboxHarness.get_wall_clock "
            "— see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return False

    def set_component(self, layer: str, arm: str) -> None:
        raise UnsupportedAblationError(
            "cursor-blackbox is closed-source; component ablation not supported. "
            "Use only for headline metrics (pass@1, METR, Pareto)."
        )


__all__ = [
    "CursorBlackboxHarness",
]
