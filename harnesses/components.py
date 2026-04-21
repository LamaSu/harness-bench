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

# (harness_name, layer, arm) -> entry dict.
#
# Entry schema (all keys required):
#   description: str                -- 1-2 sentence summary from docs/03.
#   config_override: dict[str, Any] -- parameters this arm sets on the base harness.
#   shim: str | None                -- dotted callable path for monkey-patch arms;
#                                      None if pure-config. Shims are stubs for now;
#                                      see TODO comments near each reference.
#   depends_on: list[str]           -- cross-layer arm IDs that MUST be co-applied
#                                      (e.g. ARM-SA-C parallel best-of-N needs a
#                                      verification arm to pick the winner).
#   applicable_harnesses: list[str] -- harnesses that can natively run this arm;
#                                      empty list means "swap-only" — the arm
#                                      requires running a different harness binary
#                                      entirely (OpenHands, Cline, Aider, Goose,
#                                      Continue) and cannot be replicated via
#                                      wrapper on the convergent Claude Code shell.
#
# Arm-ID mapping: docs/03 uses CL-1..CL-4 etc.; we normalize to ARM-<LAYER>-<LETTER>
# where 1->A, 2->B, 3->C, 4->D, 5->E. See docs/03 §2.x summary table (37 arms total).
#
# Populated from docs/03-component-ablation.md (2026-04-21).
ABLATION_MATRIX: dict[tuple[str, str, str], dict[str, Any]] = {
    # --------------------------------------------------------------------
    # Layer 1: control_loop  (4 arms: A-D)
    # --------------------------------------------------------------------
    ("claude_code_go", "control_loop", "ARM-CL-A"): {
        "description": (
            "BASELINE — pure single-thread ReAct. Synchronous tool-call loop, "
            "~30s/turn, no reflection on tool failure (just appends error and "
            "continues). docs/03 §2.1 CL-1."
        ),
        "config_override": {
            "control_loop.mode": "react",
            "control_loop.max_reflections": 0,
            "control_loop.async_events": False,
            "control_loop.orchestrator": False,
        },
        "shim": None,
        "depends_on": [],
        "applicable_harnesses": ["claude_code_go"],
    },
    ("claude_code_go", "control_loop", "ARM-CL-B"): {
        "description": (
            "ReAct + reflection-bound: on tool failure (lint/test/non-zero exit), "
            "re-query the model with failure as observation, up to 3 reflections. "
            "Aider-style auto_lint/auto_test. docs/03 §2.1 CL-2."
        ),
        "config_override": {
            "control_loop.mode": "react",
            "control_loop.max_reflections": 3,
            "control_loop.auto_lint": True,
            "control_loop.auto_test": True,
        },
        # TODO(shim): implement harnesses.shims.inject_reflection_on_failure
        #             — post-tool hook that catches non-zero exit + lint diag +
        #               test-failure and re-injects as a model turn.
        "shim": "harnesses.shims.inject_reflection_on_failure",
        "depends_on": [],
        "applicable_harnesses": ["claude_code_go", "aider"],
    },
    ("claude_code_go", "control_loop", "ARM-CL-C"): {
        "description": (
            "Event-driven async controller — OpenHands-style _step() + event "
            "stream + should_step() decision. Model action published as event; "
            "observation event triggers next _step. docs/03 §2.1 CL-3. SWAP arm: "
            "cannot be retrofit onto claude_code_go."
        ),
        "config_override": {
            "control_loop.mode": "event_driven",
            "control_loop.async_events": True,
        },
        "shim": None,
        "depends_on": [],
        # Empty list: this arm is swap-only — run OpenHands V0 as the harness for
        # this cell. See docs/03 §6.1 (swap strategy) and §6.2.
        "applicable_harnesses": [],
    },
    ("claude_code_go", "control_loop", "ARM-CL-D"): {
        "description": (
            "Multi-agent orchestrator wrapping inner ReAct. Outer orchestrator "
            "decomposes task, spawns N worktree-isolated inner agents, merges "
            "results. Maps to /go Phase 1b wave model. docs/03 §2.1 CL-4."
        ),
        "config_override": {
            "control_loop.orchestrator": True,
            "control_loop.wave_max_parallel": 4,
            "control_loop.single_agent_shortcircuit": False,
        },
        "shim": None,
        # Orchestrator with no sub-agents collapses to sequential ReAct (= CL-A).
        # docs/03 §3.1 hard dependency: CL-4 requires SA-B, SA-C, SA-D, or SA-E.
        "depends_on": ["ARM-SA-B", "ARM-SA-C", "ARM-SA-D", "ARM-SA-E"],
        "applicable_harnesses": ["claude_code_go"],
    },

    # --------------------------------------------------------------------
    # Layer 2: reasoning  (4 arms: A-D)
    # --------------------------------------------------------------------
    ("claude_code_go", "reasoning", "ARM-R-A"): {
        "description": (
            "BASELINE — interleaved thinking ON, default for Opus 4.6/4.7 + "
            "Sonnet 4.6. Anthropic interleaved-thinking content blocks emitted "
            "between tool calls. docs/03 §2.2 R-1."
        ),
        "config_override": {
            "reasoning.thinking": "interleaved",
            "reasoning.plan_then_execute": False,
            "reasoning.echo_thinking": False,
        },
        "shim": None,
        "depends_on": [],
        "applicable_harnesses": ["claude_code_go"],
    },
    ("claude_code_go", "reasoning", "ARM-R-B"): {
        "description": (
            "Interleaved thinking OFF — hard-disable via Anthropic API "
            "thinking={'type':'disabled'}. Faster turns, raw ReAct; expected "
            "to hurt bisociation (BS-1/BS-2) but help condensation (FM-3) "
            "and KV-cache drift (FM-4). docs/03 §2.2 R-2."
        ),
        "config_override": {
            "reasoning.thinking": "disabled",
            "reasoning.api_thinking_param": {"type": "disabled"},
        },
        "shim": None,
        "depends_on": [],
        "applicable_harnesses": ["claude_code_go"],
    },
    ("claude_code_go", "reasoning", "ARM-R-C"): {
        "description": (
            "Plan-then-execute split — Cline Plan/Act mode + Aider architect "
            "mode. First call produces plan only (no tool calls); second call "
            "executes (no plan revisions). docs/03 §2.2 R-3. Retrofittable on "
            "claude_code_go via system-prompt that forbids tool calls until "
            "<plan>...</plan> is emitted."
        ),
        "config_override": {
            "reasoning.plan_then_execute": True,
            "reasoning.plan_phase_no_tools": True,
            "reasoning.execute_phase_no_replan": True,
        },
        # TODO(shim): implement harnesses.shims.plan_then_execute_prompt
        #             — system-prompt injection that gates tool calls on the
        #               <plan> block (for non-Cline harnesses).
        "shim": "harnesses.shims.plan_then_execute_prompt",
        "depends_on": [],
        "applicable_harnesses": ["claude_code_go", "cline", "aider"],
    },
    ("claude_code_go", "reasoning", "ARM-R-D"): {
        "description": (
            "Echo thinking content across turns — Goose pattern. Preserve "
            "reasoning_content from one turn and prepend to next assistant "
            "message; provider-specific (Gemini, Kimi, DeepSeek). docs/03 §2.2 "
            "R-4. Anthropic API doesn't expose reasoning_content cross-turn, "
            "so this is effectively swap-only (Goose harness pin)."
        ),
        "config_override": {
            "reasoning.echo_thinking": True,
            "reasoning.preserve_reasoning_content": True,
        },
        "shim": None,
        # Hard dependency from docs/03 §3.1: requires non-Anthropic provider.
        "depends_on": [],
        "applicable_harnesses": [],  # Goose-only swap cell.
    },

    # --------------------------------------------------------------------
    # Layer 3: tool_surface  (5 arms: A-E)
    # --------------------------------------------------------------------
    ("claude_code_go", "tool_surface", "ARM-TS-A"): {
        "description": (
            "BASELINE — atomic core ~10 (Read/Edit/Glob/Grep/Bash/Write/Web/"
            "Task) + MCP for everything else. Standard Claude Code surface. "
            "docs/03 §2.3 TS-1."
        ),
        "config_override": {
            "tool_surface.mode": "atomic_core_plus_mcp",
            "tool_surface.atomic_count": 10,
            "tool_surface.mcp_enabled": True,
        },
        "shim": None,
        "depends_on": [],
        "applicable_harnesses": ["claude_code_go"],
    },
    ("claude_code_go", "tool_surface", "ARM-TS-B"): {
        "description": (
            "Wide flat surface — Cline-style 24 named tool handlers (ReadFile, "
            "WriteToFile, ApplyPatch, ExecuteCommand, BrowserTool, WebFetch, "
            "WebSearch, SearchFiles, ListFiles, ListCodeDefinitionNames, "
            "AskFollowupQuestion, AttemptCompletion, ...). No MCP. docs/03 "
            "§2.3 TS-2. SWAP-only — pin Cline as harness."
        ),
        "config_override": {
            "tool_surface.mode": "wide_flat_no_mcp",
            "tool_surface.handler_count": 24,
            "tool_surface.mcp_enabled": False,
        },
        "shim": None,
        "depends_on": [],
        "applicable_harnesses": [],  # Cline-only swap cell.
    },
    ("claude_code_go", "tool_surface", "ARM-TS-C"): {
        "description": (
            "Pure-MCP — every capability comes from an MCP extension, no fixed "
            "atomic set. Goose ExtensionManager pattern. docs/03 §2.3 TS-3. "
            "Impossible to retrofit onto claude_code_go without forking; SWAP "
            "to Goose."
        ),
        "config_override": {
            "tool_surface.mode": "pure_mcp",
            "tool_surface.atomic_count": 0,
            "tool_surface.mcp_enabled": True,
        },
        "shim": None,
        # Hard dep from docs/03 §3.1: needs >=3 MCP servers configured.
        "depends_on": [],
        "applicable_harnesses": [],  # Goose-only swap cell.
    },
    ("claude_code_go", "tool_surface", "ARM-TS-D"): {
        "description": (
            "Text-native diffs — Aider pattern. Model emits diffs in textual "
            "editblock/udiff/whole/patch format; no tool-call protocol. "
            "docs/03 §2.3 TS-4. SWAP-only — pin Aider; sub-arm matrix on "
            "diff format choice collapsed to one."
        ),
        "config_override": {
            "tool_surface.mode": "text_diff",
            "tool_surface.diff_format": "editblock",
            "tool_surface.tool_call_protocol": False,
        },
        "shim": None,
        "depends_on": [],
        "applicable_harnesses": [],  # Aider-only swap cell.
    },
    ("claude_code_go", "tool_surface", "ARM-TS-E"): {
        "description": (
            "Bash-only — strip Read/Edit/Write/Glob/Grep, leave only Bash + "
            "Task + Web. Tests whether dedicated file tools are load-bearing "
            "or whether cat/grep/sed via Bash suffices. docs/03 §2.3 TS-5. "
            "Wrappable on claude_code_go via per-tool allowlist hook."
        ),
        "config_override": {
            "tool_surface.mode": "bash_only",
            "tool_surface.allowlist": ["Bash", "Task", "WebFetch", "WebSearch"],
            "tool_surface.mcp_enabled": False,
        },
        # TODO(shim): implement harnesses.shims.tool_allowlist_filter
        #             — pre-tool hook that denies any tool not in allowlist.
        "shim": "harnesses.shims.tool_allowlist_filter",
        "depends_on": [],
        "applicable_harnesses": ["claude_code_go"],
    },
}


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
