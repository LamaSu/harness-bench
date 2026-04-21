"""
Claude Code (Go binary) harness adapter.

The Anthropic Claude Code CLI in Go-binary form (`harness serve` MCP +
`claude` CLI). Open core, hooks-based, BRAID/Ralph-loop conventions
established in CLAUDE.md. Used as the REFERENCE harness for ablation
arms.

Survey: docs/02-harness-survey.md §3.7 (Claude Code).
Component coverage (per docs/02-harness-survey.md §4.x): all 8 layers.
Status: STUB — to be implemented by next agent.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from harnesses.base import Cost, Event, Harness, Tool, UnsupportedAblationError

# Layers this harness exposes to the component-ablation matrix.
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


class ClaudeCodeGoHarness(Harness):
    """Harness over the Claude Code Go binary + `claude` CLI.

    Driver strategy (per spec §3 / §6):
        - Spawns `claude --print --output-format stream-json` subprocess.
        - Hook events (PreToolUse / PostToolUse / SubagentStop) parsed
          via the standard hook JSONL files in ~/.claude/audit/.
        - Token + dollar accounting from `claude --token-usage` JSON.
        - Component-ablation arms wired by injecting per-layer config
          (e.g., ARM-CL-D = disable Ralph-loop via env var; ARM-M-A =
          flat-file memory via plugin override).

    See docs/02-harness-survey.md §3.7 for layer-by-layer coverage and
    docs/03-component-ablation.md for the ARM-ID -> setting mapping.
    """

    name: str = "claude-code-go"

    def initialize(self, sandbox: Any) -> None:
        raise NotImplementedError(
            "harnesses/claude_code_go.py:ClaudeCodeGoHarness.initialize "
            "— see docs/04-bench-spec.md §3"
        )

    async def submit_task(
        self,
        prompt: str,
        tools: list[Tool],
    ) -> AsyncIterator[Event]:
        raise NotImplementedError(
            "harnesses/claude_code_go.py:ClaudeCodeGoHarness.submit_task "
            "— see docs/04-bench-spec.md §3"
        )
        yield  # type: ignore[unreachable]

    def get_token_cost(self) -> Cost:
        raise NotImplementedError(
            "harnesses/claude_code_go.py:ClaudeCodeGoHarness.get_token_cost "
            "— see docs/04-bench-spec.md §3"
        )

    def get_wall_clock(self) -> float:
        raise NotImplementedError(
            "harnesses/claude_code_go.py:ClaudeCodeGoHarness.get_wall_clock "
            "— see docs/04-bench-spec.md §3"
        )

    def supports_component_ablation(self, layer: str) -> bool:
        return layer in SUPPORTED_ABLATION_LAYERS

    def set_component(self, layer: str, arm: str) -> None:
        if layer not in SUPPORTED_ABLATION_LAYERS:
            raise UnsupportedAblationError(
                f"claude-code-go does not expose layer={layer!r} for ablation"
            )
        raise NotImplementedError(
            f"harnesses/claude_code_go.py:set_component(layer={layer}, arm={arm}) "
            "— wire via env vars / plugin overrides; see docs/03-component-ablation.md"
        )


__all__ = [
    "SUPPORTED_ABLATION_LAYERS",
    "ClaudeCodeGoHarness",
]
