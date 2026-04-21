"""
Harness adapter registry for harness-bench.

Each adapter under harnesses/<harness>.py wraps one of the 8 surveyed
agentic-coding harnesses (per docs/02-harness-survey.md) into the common
Harness ABC defined in harnesses/base.py. The registry below maps
short string IDs to the concrete adapter class so the runner can spawn
harness-bench cells by name.

Spec: docs/04-bench-spec.md §3 (Harness adapter interface).
Status: STUB — adapter methods raise NotImplementedError; to be
implemented by the next agent (implementer-* family).
"""
from __future__ import annotations

from typing import Type

from harnesses.base import (
    Cost,
    Event,
    Harness,
    Tool,
    UnsupportedAblationError,
)

# Open-source harnesses (6) — per docs/02-harness-survey.md §1.1-§1.6 + §1.7
from harnesses.claude_code_go import ClaudeCodeGoHarness
from harnesses.aider import AiderHarness
from harnesses.openhands import OpenHandsHarness
from harnesses.cline import ClineHarness
from harnesses.continue_dev import ContinueDevHarness
from harnesses.goose import GooseHarness

# Closed/SaaS harnesses (2) — per docs/02-harness-survey.md §1.6 + §1.8
from harnesses.cursor_blackbox import CursorBlackboxHarness
from harnesses.devin_blackbox import DevinBlackboxHarness

# Component-toggle wrapper — per docs/04-bench-spec.md §3.3
from harnesses.components import ComponentAblationHarness

HARNESS_REGISTRY: dict[str, Type[Harness]] = {
    # Open-source
    "claude_code_go": ClaudeCodeGoHarness,
    "aider": AiderHarness,
    "openhands": OpenHandsHarness,
    "cline": ClineHarness,
    "continue_dev": ContinueDevHarness,
    "goose": GooseHarness,
    # Closed
    "cursor_blackbox": CursorBlackboxHarness,
    "devin_blackbox": DevinBlackboxHarness,
}

# Harnesses that are open enough to support per-layer ablation
ABLATION_CAPABLE: list[str] = [
    "claude_code_go",
    "aider",
    "cline",
    "openhands",
    "goose",
    "continue_dev",
]

# Black-box harnesses run as fixed cells — no ablation support
BLACKBOX_HARNESSES: list[str] = ["cursor_blackbox", "devin_blackbox"]

__all__ = [
    "Cost",
    "Event",
    "Harness",
    "Tool",
    "UnsupportedAblationError",
    "HARNESS_REGISTRY",
    "ABLATION_CAPABLE",
    "BLACKBOX_HARNESSES",
    "ClaudeCodeGoHarness",
    "AiderHarness",
    "OpenHandsHarness",
    "ClineHarness",
    "ContinueDevHarness",
    "GooseHarness",
    "CursorBlackboxHarness",
    "DevinBlackboxHarness",
    "ComponentAblationHarness",
]
