"""
Task family registry for harness-bench.

Each axis (M1-M5, FM1-FM5, BS1-BS5) is a separate Inspect AI Task module
under tasks/<family>/<axis_id>.py. This file imports them for registry-style
discovery so the runner can iterate axes by ID.

Spec: docs/04-bench-spec.md §1.2 (folder layout) + §2 (task taxonomy).
Status: STUB — task functions raise NotImplementedError; to be implemented
by the next agent (implementer-* family).
"""
from __future__ import annotations

# Memory axes (M1-M5) — see docs/04-bench-spec.md §2.1
from tasks.memory.m1_cross_window import m1_cross_window
from tasks.memory.m2_cross_modal import m2_cross_modal
from tasks.memory.m3_stale_fact import m3_stale_fact
from tasks.memory.m4_procedural import m4_procedural
from tasks.memory.m5_eviction import m5_eviction

# Pain modes (FM1-FM5) — see docs/04-bench-spec.md §2.2
from tasks.pain_modes.fm1_stuck_loops import fm1_stuck_loops
from tasks.pain_modes.fm2_env_hallucination import fm2_env_hallucination
from tasks.pain_modes.fm3_condensation_loops import fm3_condensation_loops
from tasks.pain_modes.fm4_kv_cache_drift import fm4_kv_cache_drift
from tasks.pain_modes.fm5_destructive_action import fm5_destructive_action

# Bisociation (BS1-BS5) — see docs/04-bench-spec.md §2.3
from tasks.bisociation.bs1_analogy_retrieval import bs1_analogy_retrieval
from tasks.bisociation.bs2_frame_shift import bs2_frame_shift
from tasks.bisociation.bs3_cross_paper import bs3_cross_paper
from tasks.bisociation.bs4_tool_output import bs4_tool_output
from tasks.bisociation.bs5_recombination import bs5_recombination

# Axis-ID → callable map. Used by runner to look up tasks by string ID
# from CLI / suite definitions / config files.
TASK_REGISTRY: dict[str, callable] = {
    # Memory
    "M1": m1_cross_window,
    "M2": m2_cross_modal,
    "M3": m3_stale_fact,
    "M4": m4_procedural,
    "M5": m5_eviction,
    # Pain modes
    "FM1": fm1_stuck_loops,
    "FM2": fm2_env_hallucination,
    "FM3": fm3_condensation_loops,
    "FM4": fm4_kv_cache_drift,
    "FM5": fm5_destructive_action,
    # Bisociation
    "BS1": bs1_analogy_retrieval,
    "BS2": bs2_frame_shift,
    "BS3": bs3_cross_paper,
    "BS4": bs4_tool_output,
    "BS5": bs5_recombination,
}

# Axis families — used by suite definitions in eval_suites/*.eval
FAMILY_MEMORY: list[str] = ["M1", "M2", "M3", "M4", "M5"]
FAMILY_PAIN_MODES: list[str] = ["FM1", "FM2", "FM3", "FM4", "FM5"]
FAMILY_BISOCIATION: list[str] = ["BS1", "BS2", "BS3", "BS4", "BS5"]
ALL_AXES: list[str] = FAMILY_MEMORY + FAMILY_PAIN_MODES + FAMILY_BISOCIATION

__all__ = [
    "TASK_REGISTRY",
    "FAMILY_MEMORY",
    "FAMILY_PAIN_MODES",
    "FAMILY_BISOCIATION",
    "ALL_AXES",
    # Memory
    "m1_cross_window",
    "m2_cross_modal",
    "m3_stale_fact",
    "m4_procedural",
    "m5_eviction",
    # Pain modes
    "fm1_stuck_loops",
    "fm2_env_hallucination",
    "fm3_condensation_loops",
    "fm4_kv_cache_drift",
    "fm5_destructive_action",
    # Bisociation
    "bs1_analogy_retrieval",
    "bs2_frame_shift",
    "bs3_cross_paper",
    "bs4_tool_output",
    "bs5_recombination",
]
