"""
ComponentAblationHarness — wrapper that enables per-layer ARM injection.

Wraps a base Harness and intercepts `set_component(layer, arm)` to:
    1. Validate the (harness, layer, arm) triple is in the allowed matrix
       defined in docs/03-component-ablation.md.
    2. Apply the arm via the base harness's native config OR via a
       monkey-patch shim if the base harness lacks first-class support.
    3. Tag every emitted Event with `event.payload["arm.<layer>"] = arm`
       so downstream scorers / OTLP traces can attribute behavior.

This is the ONLY way the runner injects ARMs. Tasks never see component
config — they see a plain Harness interface.

Spec: docs/04-bench-spec.md §3 (Harness adapter interface) + §5 (Runner).
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from harnesses.base import Cost, Event, Harness, Tool, UnsupportedAblationError

# (harness_name, layer, arm) -> {} | {"shim": "<callable_path>"}.
# Populated from docs/03-component-ablation.md when that doc lands.
ABLATION_MATRIX: dict[tuple[str, str, str], dict[str, Any]] = {}


class ComponentAblationHarness(Harness):
    """Decorator harness that injects component ARMs.

    Usage:
        base = ClaudeCodeGoHarness()
        wrapped = ComponentAblationHarness(base)
        wrapped.set_component("memory", "ARM-M-A")
        wrapped.set_component("verification", "ARM-V-D")
        async for evt in wrapped.submit_task(prompt, tools):
            ...

    All other methods delegate transparently to `base`.
    """

    def __init__(self, base: Harness) -> None:
        self.base = base
        self.name = f"{base.name}+components"
        self._active_arms: dict[str, str] = {}

    def initialize(self, sandbox: Any) -> None:
        self.base.initialize(sandbox)

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        async for event in self.base.submit_task(prompt, tools):
            for layer, arm in self._active_arms.items():
                event.payload[f"arm.{layer}"] = arm
            yield event

    def get_token_cost(self) -> Cost:
        return self.base.get_token_cost()

    def get_wall_clock(self) -> float:
        return self.base.get_wall_clock()

    def supports_component_ablation(self, layer: str) -> bool:
        # Honor the union of base-supported layers AND matrix-known shimmed layers.
        if self.base.supports_component_ablation(layer):
            return True
        return any(
            (h, l, _) for (h, l, _) in ABLATION_MATRIX.keys()
            if h == self.base.name and l == layer
        )

    def set_component(self, layer: str, arm: str) -> None:
        key = (self.base.name, layer, arm)
        if key not in ABLATION_MATRIX and not self.base.supports_component_ablation(layer):
            raise UnsupportedAblationError(
                f"({self.base.name}, {layer}, {arm}) not in ABLATION_MATRIX "
                "and base harness does not support this layer; "
                "see docs/03-component-ablation.md"
            )
        if self.base.supports_component_ablation(layer):
            self.base.set_component(layer, arm)
        else:
            # Shim path — load the shimmed callable from the matrix entry.
            raise NotImplementedError(
                f"harnesses/components.py:set_component shim for {key} "
                "— see docs/03-component-ablation.md"
            )
        self._active_arms[layer] = arm


__all__ = [
    "ABLATION_MATRIX",
    "ComponentAblationHarness",
]
