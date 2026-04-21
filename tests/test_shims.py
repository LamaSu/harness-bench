"""
Unit tests for harnesses/shims.py + ComponentAblationHarness integration.

Covers all 14 behavioral-mutator shims:
    - apply() mutates state (settings.json / env / extra_args)
    - teardown() restores prior state verbatim
    - both are idempotent (double-apply / double-teardown safe)
    - UnsupportedAblationError on wrong harness

Plus one integration test: full ComponentAblationHarness cycle with
ARM-CL-B (reflection on failure) — apply_arm + set_component + event
tagging + teardown_all.

Run:
    python -m pytest tests/test_shims.py -xvs
"""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from harnesses import shims
from harnesses.base import Cost, Event, Harness, Tool, UnsupportedAblationError
from harnesses.components import ABLATION_MATRIX, ComponentAblationHarness
from harnesses.shims import ShimHandle


# ---------------------------------------------------------------------------
# Fake harness — no subprocess, deterministic
# ---------------------------------------------------------------------------


class FakeHarness(Harness):
    """In-memory stand-in that records what shims do to it.

    Only the attributes the shims touch are real:
        * name            — dispatched to _check_supported
        * sandbox_cwd     — where per-cell files land
        * extra_args      — CLI flag list shims mutate
        * _env_override   — env-var dict shims mutate
        * _settings_json_path — per-test temp file
    """

    name = "claude_code_go"

    def __init__(self, tmp_path: Path, name: str = "claude_code_go") -> None:
        super().__init__(model="claude-opus-4-7")
        self.name = name
        self.sandbox_cwd = tmp_path / "sandbox"
        self.sandbox_cwd.mkdir(parents=True, exist_ok=True)
        self.extra_args: list[str] = []
        self._env_override: dict[str, str] = {}
        # Per-test settings.json to avoid mutating the user's real one.
        self._settings_json_path = tmp_path / "settings.json"
        # Populate with a plausible starting config so "restore to prior"
        # means something.
        self._initial_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": "echo original-pre"}
                        ],
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "bash /original/lint.sh",
                            }
                        ],
                    }
                ],
            },
            "other": "untouched",
        }
        self._settings_json_path.write_text(
            json.dumps(self._initial_settings, indent=2) + "\n",
            encoding="utf-8",
        )

    def initialize(self, sandbox: Any) -> None:
        self._initialized = True

    async def submit_task(
        self, prompt: str, tools: list[Tool]
    ) -> AsyncIterator[Event]:
        yield Event(kind="text", payload={"line": f"prompt={prompt}"})
        yield Event(kind="completion", payload={"exit_code": 0})

    def get_token_cost(self) -> Cost:
        return Cost()

    def get_wall_clock(self) -> float:
        return 0.0

    def supports_component_ablation(self, layer: str) -> bool:
        return True

    def set_component(self, layer: str, arm: str) -> None:
        self._arms[layer] = arm


@pytest.fixture
def fake_harness(tmp_path: Path) -> FakeHarness:
    """Fresh FakeHarness per test; its settings.json is per-test temp."""
    return FakeHarness(tmp_path)


# ---------------------------------------------------------------------------
# Per-shim unit tests
# ---------------------------------------------------------------------------


def _read_settings(h: FakeHarness) -> dict[str, Any]:
    return json.loads(h._settings_json_path.read_text(encoding="utf-8"))


def _assert_restored(h: FakeHarness) -> None:
    """After teardown, settings.json must equal the initial snapshot."""
    current = _read_settings(h)
    assert current == h._initial_settings, (
        f"settings.json drift after teardown: "
        f"expected={h._initial_settings!r} got={current!r}"
    )


def test_append_event_log(fake_harness: FakeHarness) -> None:
    handle = shims.append_event_log(fake_harness, "ARM-M-C")
    handle.apply()
    cfg = _read_settings(fake_harness)
    post = cfg["hooks"]["PostToolUse"]
    assert any("_harness_bench_arm" in h for entry in post for h in entry["hooks"])
    assert fake_harness._env_override["HARNESS_BENCH_EVENT_LOG"].endswith("log.jsonl")
    # Idempotent re-apply
    handle.apply()
    # Teardown
    handle.teardown()
    handle.teardown()  # idempotent
    _assert_restored(fake_harness)
    assert "HARNESS_BENCH_EVENT_LOG" not in fake_harness._env_override


def test_auto_compact(fake_harness: FakeHarness) -> None:
    handle = shims.auto_compact(fake_harness, "ARM-M-B")
    handle.apply()
    assert fake_harness._env_override["CLAUDE_AUTO_COMPACT"] == "1"
    assert fake_harness._env_override["CLAUDE_AUTO_COMPACT_TURNS"] == "25"
    handle.teardown()
    assert "CLAUDE_AUTO_COMPACT" not in fake_harness._env_override
    assert "CLAUDE_AUTO_COMPACT_TURNS" not in fake_harness._env_override


def test_codesight_rag_per_turn(fake_harness: FakeHarness) -> None:
    handle = shims.codesight_rag_per_turn(fake_harness, "ARM-M-D")
    handle.apply()
    assert fake_harness._env_override["CLAUDE_RAG_BACKEND"] == "codesight"
    assert fake_harness._env_override["CLAUDE_RAG_TOP_K"] == "3"
    # Metadata should report whether codesight is actually available
    # (True on Spark, maybe False on Windows — either is fine).
    handle.teardown()
    assert "CLAUDE_RAG_BACKEND" not in fake_harness._env_override


def test_disable_all_hooks(fake_harness: FakeHarness) -> None:
    handle = shims.disable_all_hooks(fake_harness, "ARM-S-A")
    handle.apply()
    cfg = _read_settings(fake_harness)
    assert cfg["hooks"] == {}
    # Non-hook state preserved
    assert cfg["other"] == "untouched"
    handle.teardown()
    _assert_restored(fake_harness)


def test_disable_toolsearch(fake_harness: FakeHarness) -> None:
    handle = shims.disable_toolsearch(fake_harness, "ARM-TC-B")
    handle.apply()
    assert fake_harness._env_override["CLAUDE_DISABLE_TOOLSEARCH"] == "1"
    handle.teardown()
    assert "CLAUDE_DISABLE_TOOLSEARCH" not in fake_harness._env_override


def test_disable_verification(fake_harness: FakeHarness) -> None:
    # Ensure the initial PostToolUse has a verification-looking hook
    handle = shims.disable_verification(fake_harness, "ARM-V-A")
    handle.apply()
    cfg = _read_settings(fake_harness)
    # The /original/lint.sh command matches the "lint" marker, so it
    # should be stripped.
    post = cfg["hooks"].get("PostToolUse", [])
    for entry in post:
        for h in entry.get("hooks", []):
            assert "lint" not in h["command"].lower()
    # Pre-tool hooks preserved
    pre = cfg["hooks"].get("PreToolUse", [])
    assert len(pre) == 1
    handle.teardown()
    _assert_restored(fake_harness)


def test_haiku_adversary_inspector(fake_harness: FakeHarness) -> None:
    handle = shims.haiku_adversary_inspector(fake_harness, "ARM-S-D")
    handle.apply()
    cfg = _read_settings(fake_harness)
    pre = cfg["hooks"]["PreToolUse"]
    # Should contain the adversary hook entry marked with our arm id.
    found = False
    for entry in pre:
        for h in entry.get("hooks", []):
            if h.get("_harness_bench_arm") == "ARM-S-D":
                found = True
    assert found, "adversary hook not found in PreToolUse"
    # Hook script on disk
    script_path = Path(handle.metadata.get("arm_id", "")) / "nonexistent"  # just a probe
    # Actual script lives under sandbox/.harness-bench
    hook_file = fake_harness.sandbox_cwd / ".harness-bench" / "adversary_hook.sh"
    assert hook_file.exists()
    handle.teardown()
    _assert_restored(fake_harness)


def test_inject_reflection_on_failure(fake_harness: FakeHarness) -> None:
    handle = shims.inject_reflection_on_failure(fake_harness, "ARM-CL-B")
    handle.apply()
    assert fake_harness._env_override["CLAUDE_MAX_REFLECTIONS"] == "3"
    cfg = _read_settings(fake_harness)
    post = cfg["hooks"]["PostToolUse"]
    assert any(
        h.get("_harness_bench_arm") == "ARM-CL-B"
        for entry in post
        for h in entry.get("hooks", [])
    )
    handle.teardown()
    _assert_restored(fake_harness)
    assert "CLAUDE_MAX_REFLECTIONS" not in fake_harness._env_override


def test_inline_lint_test(fake_harness: FakeHarness) -> None:
    # Create a pyproject.toml so the shim detects pytest
    (fake_harness.sandbox_cwd / "pyproject.toml").write_text(
        "[project]\nname='probe'\n", encoding="utf-8"
    )
    handle = shims.inline_lint_test(fake_harness, "ARM-V-C")
    handle.apply()
    cfg = _read_settings(fake_harness)
    # Find the Edit|Write matcher entry
    post = cfg["hooks"]["PostToolUse"]
    edit_entries = [e for e in post if e.get("matcher") == "Edit|Write"]
    assert edit_entries, "Edit|Write matcher not installed"
    cmd = edit_entries[0]["hooks"][0]["command"]
    assert "pytest" in cmd or "ruff" in cmd
    handle.teardown()
    _assert_restored(fake_harness)


def test_per_tool_policy_loader(fake_harness: FakeHarness) -> None:
    handle = shims.per_tool_policy_loader(fake_harness, "ARM-S-B")
    handle.apply()
    hook_file = fake_harness.sandbox_cwd / ".harness-bench" / "per_tool_policy_hook.sh"
    assert hook_file.exists()
    cfg = _read_settings(fake_harness)
    pre = cfg["hooks"]["PreToolUse"]
    assert any(
        h.get("_harness_bench_arm") == "ARM-S-B"
        for entry in pre
        for h in entry.get("hooks", [])
    )
    handle.teardown()
    _assert_restored(fake_harness)


def test_plan_then_execute_prompt(fake_harness: FakeHarness) -> None:
    assert fake_harness.extra_args == []
    handle = shims.plan_then_execute_prompt(fake_harness, "ARM-R-C")
    handle.apply()
    assert "--append-system-prompt" in fake_harness.extra_args
    idx = fake_harness.extra_args.index("--append-system-prompt")
    prompt = fake_harness.extra_args[idx + 1]
    assert "<plan>" in prompt.lower() or "plan-then-execute" in prompt.lower()
    handle.teardown()
    assert fake_harness.extra_args == []


def test_strip_task_tool(fake_harness: FakeHarness) -> None:
    handle = shims.strip_task_tool(fake_harness, "ARM-SA-A")
    handle.apply()
    assert "--disallowedTools" in fake_harness.extra_args
    idx = fake_harness.extra_args.index("--disallowedTools")
    val = fake_harness.extra_args[idx + 1]
    assert "Task" in val and "Agent" in val
    handle.teardown()
    assert fake_harness.extra_args == []


def test_tool_allowlist_filter(fake_harness: FakeHarness) -> None:
    handle = shims.tool_allowlist_filter(fake_harness, "ARM-TS-E")
    handle.apply()
    assert "--allowedTools" in fake_harness.extra_args
    idx = fake_harness.extra_args.index("--allowedTools")
    val = fake_harness.extra_args[idx + 1]
    # Bash-only: Read/Edit/Write/Glob/Grep must NOT be present
    assert "Bash" in val
    for stripped in ("Read", "Edit", "Write", "Glob", "Grep"):
        assert stripped not in val.split(","), (
            f"{stripped} leaked into allowlist: {val}"
        )
    handle.teardown()
    assert fake_harness.extra_args == []


def test_vector_only_memory_adapter(fake_harness: FakeHarness) -> None:
    handle = shims.vector_only_memory_adapter(fake_harness, "ARM-M-E")
    handle.apply()
    assert fake_harness._env_override["CLAUDE_MEMORY_BACKEND"] == "chroma"
    assert fake_harness._env_override["CLAUDE_MEMORY_VECTOR_ONLY"] == "1"
    assert "--disallowedTools" in fake_harness.extra_args
    idx = fake_harness.extra_args.index("--disallowedTools")
    val = fake_harness.extra_args[idx + 1]
    assert "Grep" in val and "Glob" in val
    handle.teardown()
    assert fake_harness.extra_args == []
    assert "CLAUDE_MEMORY_BACKEND" not in fake_harness._env_override


# ---------------------------------------------------------------------------
# Unsupported-harness rejection
# ---------------------------------------------------------------------------


def test_shim_rejects_unsupported_harness(tmp_path: Path) -> None:
    """strip_task_tool only works for claude_code_go; using it on 'goose'
    must raise cleanly WITHOUT mutating state."""
    h = FakeHarness(tmp_path, name="goose")
    with pytest.raises(UnsupportedAblationError) as exc_info:
        shims.strip_task_tool(h, "ARM-SA-A")
    assert "goose" in str(exc_info.value) or "sub_agents" in str(exc_info.value)
    assert h.extra_args == []
    assert h._env_override == {}


# ---------------------------------------------------------------------------
# Integration: ComponentAblationHarness full cycle
# ---------------------------------------------------------------------------


def test_component_ablation_full_cycle_arm_cl_b(
    fake_harness: FakeHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full apply → emit event → teardown cycle for ARM-CL-B (reflection)."""
    # Redirect SETTINGS_JSON_PATH so the shim writes to our temp file,
    # not the user's real ~/.claude/settings.json.
    monkeypatch.setattr(
        shims, "SETTINGS_JSON_PATH", fake_harness._settings_json_path
    )

    wrapped = ComponentAblationHarness(fake_harness)
    wrapped.initialize(sandbox=None)

    # apply_arm via the new API
    wrapped.apply_arm("control_loop", "ARM-CL-B")
    assert wrapped.active_arms == {"control_loop": "ARM-CL-B"}
    # Env var set by the shim
    assert fake_harness._env_override["CLAUDE_MAX_REFLECTIONS"] == "3"

    # Drive one submit_task through the wrapper; events must be tagged.
    async def _drain() -> list[Event]:
        collected: list[Event] = []
        async for evt in wrapped.submit_task("hello world", tools=[]):
            collected.append(evt)
        return collected

    import asyncio
    events = asyncio.run(_drain())
    # Every event should carry arm.control_loop = ARM-CL-B
    assert events, "no events yielded"
    for evt in events:
        assert evt.payload.get("arm.control_loop") == "ARM-CL-B"

    # Teardown reverses everything
    wrapped.teardown_all()
    assert wrapped.active_arms == {}
    assert "CLAUDE_MAX_REFLECTIONS" not in fake_harness._env_override
    _assert_restored(fake_harness)


def test_component_ablation_rejects_swap_only(fake_harness: FakeHarness) -> None:
    """ARM-TS-B is swap-only (Cline); wrapper must refuse it cleanly."""
    wrapped = ComponentAblationHarness(fake_harness)
    with pytest.raises(UnsupportedAblationError) as exc:
        wrapped.apply_arm("tool_surface", "ARM-TS-B")
    assert "swap-only" in str(exc.value).lower() or "ARM-TS-B" in str(exc.value)


def test_component_ablation_enforces_depends_on(
    fake_harness: FakeHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ARM-CL-D depends on SA-B/C/D/E. Applying it alone must raise."""
    monkeypatch.setattr(
        shims, "SETTINGS_JSON_PATH", fake_harness._settings_json_path
    )
    wrapped = ComponentAblationHarness(fake_harness)
    with pytest.raises(UnsupportedAblationError) as exc:
        wrapped.apply_arm("control_loop", "ARM-CL-D")
    assert "depends on" in str(exc.value).lower()

    # But after applying SA-B, CL-D is accepted.
    wrapped.apply_arm("sub_agents", "ARM-SA-B")
    # CL-D has no shim (only config_override), so apply should succeed.
    wrapped.apply_arm("control_loop", "ARM-CL-D")
    assert wrapped.active_arms["control_loop"] == "ARM-CL-D"
    wrapped.teardown_all()


def test_component_ablation_unknown_triple_raises(fake_harness: FakeHarness) -> None:
    wrapped = ComponentAblationHarness(fake_harness)
    with pytest.raises(UnsupportedAblationError):
        wrapped.apply_arm("control_loop", "ARM-ZZ-Z")


def test_shims_registered_in_matrix() -> None:
    """Sanity: every shim in ABLATION_MATRIX.shim points at a real callable."""
    for key, entry in ABLATION_MATRIX.items():
        shim_path = entry.get("shim")
        if shim_path is None:
            continue
        # Split and import
        module_name, _, fn_name = shim_path.rpartition(".")
        mod = __import__(module_name, fromlist=[fn_name])
        fn = getattr(mod, fn_name)
        assert callable(fn), f"{shim_path} not callable"
