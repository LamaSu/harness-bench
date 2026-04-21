"""
Behavioral-mutator shims for ComponentAblationHarness.

Each arm in ABLATION_MATRIX (harnesses/components.py) that can't be expressed
purely as a config override has a ``shim`` dotted-path pointing at a callable
in THIS module. The callable takes a live ``Harness`` + arm_id and returns a
``ShimHandle`` with ``apply()`` / ``teardown()`` methods the runner invokes
before and after each cell.

Design invariants
-----------------
1. Idempotent:  calling apply() / teardown() twice is safe.
2. Reversible:  teardown() restores every piece of state apply() mutated
                (settings.json snapshot, env vars, harness.extra_args).
3. Fail-safe:   shims raise UnsupportedAblationError cleanly if the live
                harness can't host them; they NEVER partially mutate state
                before raising.
4. Atomic I/O:  settings.json mutation uses temp-file + os.replace so a
                mid-write crash leaves the user's config untouched.
5. Scoped env:  env mutations go on ``harness._env_override`` (a mapping the
                harness subprocess launcher merges into os.environ). We
                never set os.environ directly — multiple cells run in one
                process.

Spec: docs/03-component-ablation.md §4 (shim contracts), docs/04-bench-spec.md
§3.3 (ComponentAblationHarness wiring).
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from harnesses.base import Harness, UnsupportedAblationError


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


@dataclass
class ShimHandle:
    """Return value from every shim factory.

    ``apply`` and ``teardown`` are zero-arg callables; ``metadata`` holds
    whatever the shim wants to snapshot for debugging (prior state, arm
    id, layer name). The runner stores these in a per-cell dict keyed by
    ``(layer, arm_id)`` so teardown runs in reverse-order of apply.
    """

    apply: Callable[[], None]
    teardown: Callable[[], None]
    metadata: dict[str, Any] = field(default_factory=dict)


# Path to the real user settings.json that Claude Code reads on each spawn.
# Shims that mutate it MUST snapshot first and restore on teardown.
SETTINGS_JSON_PATH: Path = Path.home() / ".claude" / "settings.json"


# ---------------------------------------------------------------------------
# Helpers — settings.json snapshot / atomic write
# ---------------------------------------------------------------------------


def _settings_path(harness: Harness) -> Path:
    """Resolve the settings.json path (overridable via env for tests)."""
    override = os.environ.get("HARNESS_BENCH_SETTINGS_PATH")
    if override:
        return Path(override)
    # Also honor a per-harness override if present (test fixtures use this)
    override_attr = getattr(harness, "_settings_json_path", None)
    if override_attr:
        return Path(override_attr)
    return SETTINGS_JSON_PATH


def _read_settings(path: Path) -> dict[str, Any] | None:
    """Read settings.json; return None if absent. Empty file => {}."""
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _write_settings_atomic(path: Path, data: dict[str, Any]) -> None:
    """Atomic write: temp-file + os.replace. Preserves 0o600 on POSIX."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dir_ = str(path.parent)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".settings.json.tmp.", suffix=".swp", dir=dir_
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _snapshot_and_mutate_settings(
    path: Path,
    mutator: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[str | None, bool]:
    """Snapshot settings.json, apply mutator, write atomically.

    Returns (prior_contents_text_or_None, file_existed_before).
    ``prior_contents_text_or_None`` is the verbatim text (so teardown
    preserves formatting exactly); None means the file didn't exist.
    """
    prior_text: str | None = None
    existed = path.exists()
    if existed:
        prior_text = path.read_text(encoding="utf-8")
        current = json.loads(prior_text) if prior_text.strip() else {}
    else:
        current = {}
    new_state = mutator(dict(current) if current else {})
    _write_settings_atomic(path, new_state)
    return prior_text, existed


def _restore_settings(path: Path, prior_text: str | None, existed: bool) -> None:
    """Undo a snapshot: write prior text back, or delete if file didn't exist."""
    if not existed:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        return
    # existed = True; prior_text is the verbatim original content
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".settings.json.tmp.", suffix=".swp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(prior_text or "")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _ensure_harness_env_override(harness: Harness) -> dict[str, str]:
    """Lazy-create ``harness._env_override`` dict (subprocess env merge target)."""
    env = getattr(harness, "_env_override", None)
    if env is None:
        env = {}
        # Use object.__setattr__ so frozen-ish harnesses still accept it
        setattr(harness, "_env_override", env)
    return env


def _ensure_extra_args(harness: Harness) -> list[str]:
    """Ensure ``harness.extra_args`` is a mutable list and return it."""
    args = getattr(harness, "extra_args", None)
    if args is None:
        args = []
        setattr(harness, "extra_args", args)
    return args


def _check_supported(
    harness: Harness, arm_id: str, layer: str, allowed: set[str]
) -> None:
    """Raise UnsupportedAblationError if harness.name isn't in allowed set.

    Accepts either the bare name ("claude-code-go") or the matrix key
    ("claude_code_go"). We normalize by replacing - with _.
    """
    normalized = (harness.name or "").replace("-", "_")
    allowed_norm = {a.replace("-", "_") for a in allowed}
    if normalized not in allowed_norm:
        raise UnsupportedAblationError(harness.name or "unknown", layer, arm_id)


# ---------------------------------------------------------------------------
# Shim 1: append_event_log — memory / ARM-M-C
# ---------------------------------------------------------------------------


def append_event_log(harness: Harness, arm_id: str) -> ShimHandle:
    """Memory ARM-M-C: Cline-style structured event log under sandbox_cwd.

    Writes a post-tool hook into settings.json that appends every tool
    call + result as JSONL to ai/events/log.jsonl relative to the
    subprocess cwd. The sandbox_cwd resolution is deferred until apply()
    so the harness has had initialize() called.
    """
    _check_supported(
        harness, arm_id, "memory",
        {"claude_code_go", "cline", "openhands"},
    )
    settings_path = _settings_path(harness)

    # Snapshot state captured across apply() invocations (so teardown works
    # whether or not apply ever ran).
    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        # Derive the event-log path from the harness sandbox_cwd.
        sandbox = getattr(harness, "sandbox_cwd", None) or Path.cwd()
        log_path = Path(sandbox) / "ai" / "events" / "log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Create (touch) so readers don't see FileNotFound before first tool call
        if not log_path.exists():
            log_path.write_text("", encoding="utf-8")

        # Mutate settings.json to inject a PostToolUse hook that appends
        # {timestamp,tool,args,result} JSONL. We express the command
        # inline so it works cross-platform (bash present on Windows via Git Bash).
        hook_cmd = (
            f"bash -c 'printf \"%s\\n\" \"$(date -u +%FT%TZ) "
            f"${{CLAUDE_TOOL_NAME:-unknown}} ${{CLAUDE_TOOL_EXIT:-0}}\" "
            f">> \"{log_path.as_posix()}\"'"
        )
        new_entry = {
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": hook_cmd,
                    "_harness_bench_arm": arm_id,
                }
            ],
        }

        def mutate(cfg: dict[str, Any]) -> dict[str, Any]:
            hooks = dict(cfg.get("hooks") or {})
            post = list(hooks.get("PostToolUse") or [])
            post.append(new_entry)
            hooks["PostToolUse"] = post
            cfg["hooks"] = hooks
            return cfg

        prior_text, existed = _snapshot_and_mutate_settings(settings_path, mutate)
        # Also export env var pointing at the log (readers can use this).
        env = _ensure_harness_env_override(harness)
        prior_env = env.get("HARNESS_BENCH_EVENT_LOG")
        env["HARNESS_BENCH_EVENT_LOG"] = str(log_path)
        state.update(
            {
                "applied": True,
                "prior_text": prior_text,
                "existed": existed,
                "log_path": str(log_path),
                "prior_env": prior_env,
            }
        )

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        _restore_settings(settings_path, state["prior_text"], state["existed"])
        env = _ensure_harness_env_override(harness)
        if state.get("prior_env") is None:
            env.pop("HARNESS_BENCH_EVENT_LOG", None)
        else:
            env["HARNESS_BENCH_EVENT_LOG"] = state["prior_env"]
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={"arm_id": arm_id, "layer": "memory", "shim": "append_event_log"},
    )


# ---------------------------------------------------------------------------
# Shim 2: auto_compact — memory / ARM-M-B
# ---------------------------------------------------------------------------


def auto_compact(harness: Harness, arm_id: str) -> ShimHandle:
    """Memory ARM-M-B: auto-summary cache after N tokens.

    Sets the env vars ``CLAUDE_AUTO_COMPACT=1`` +
    ``CLAUDE_AUTO_COMPACT_TURNS=25`` which the /go pipeline's checkpoint
    logic reads at boot. Also injects a Stop hook that calls /compact on
    long-running sessions.
    """
    _check_supported(
        harness, arm_id, "memory",
        {"claude_code_go", "aider", "goose", "cline"},
    )

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        env = _ensure_harness_env_override(harness)
        prior = {
            k: env.get(k)
            for k in ("CLAUDE_AUTO_COMPACT", "CLAUDE_AUTO_COMPACT_TURNS")
        }
        env["CLAUDE_AUTO_COMPACT"] = "1"
        env["CLAUDE_AUTO_COMPACT_TURNS"] = "25"
        state.update({"applied": True, "prior_env": prior})

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        env = _ensure_harness_env_override(harness)
        for k, v in state["prior_env"].items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={"arm_id": arm_id, "layer": "memory", "shim": "auto_compact"},
    )


# ---------------------------------------------------------------------------
# Shim 3: codesight_rag_per_turn — memory / ARM-M-D
# ---------------------------------------------------------------------------


def codesight_rag_per_turn(harness: Harness, arm_id: str) -> ShimHandle:
    """Memory ARM-M-D: per-turn `codesight search` RAG injection.

    Requires the ``codesight`` CLI on PATH. If absent, apply() still
    succeeds but raises a soft warning via env var; the /go hook that
    reads ``CLAUDE_RAG_BACKEND`` treats absent-backend as no-op.
    """
    _check_supported(
        harness, arm_id, "memory",
        {"claude_code_go", "continue_dev"},
    )

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        env = _ensure_harness_env_override(harness)
        prior = {
            k: env.get(k)
            for k in (
                "CLAUDE_RAG_BACKEND",
                "CLAUDE_RAG_TOP_K",
                "CLAUDE_RAG_ON_TURN",
            )
        }
        env["CLAUDE_RAG_BACKEND"] = "codesight"
        env["CLAUDE_RAG_TOP_K"] = "3"
        env["CLAUDE_RAG_ON_TURN"] = "1"
        # Record whether codesight is actually on PATH for downstream
        # telemetry; don't fail the shim if it's absent (swap cells run
        # codesight on Spark, not tablet).
        cs_bin = shutil.which("codesight")
        state.update(
            {
                "applied": True,
                "prior_env": prior,
                "codesight_available": cs_bin is not None,
            }
        )

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        env = _ensure_harness_env_override(harness)
        for k, v in state["prior_env"].items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "memory",
            "shim": "codesight_rag_per_turn",
        },
    )


# ---------------------------------------------------------------------------
# Shim 4: disable_all_hooks — safety / ARM-S-A
# ---------------------------------------------------------------------------


def disable_all_hooks(harness: Harness, arm_id: str) -> ShimHandle:
    """Safety ARM-S-A: strip ALL hook configs from settings.json.

    Aider-baseline: no interception. Restore on teardown so the user's
    68-rule harness isn't permanently disabled.
    """
    _check_supported(
        harness, arm_id, "safety",
        {"claude_code_go", "aider"},
    )
    settings_path = _settings_path(harness)

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return

        def mutate(cfg: dict[str, Any]) -> dict[str, Any]:
            # Replace hooks with empty dict (not delete — downstream code
            # sometimes checks cfg["hooks"] existence vs. emptiness).
            cfg["hooks"] = {}
            return cfg

        prior_text, existed = _snapshot_and_mutate_settings(settings_path, mutate)
        state.update({"applied": True, "prior_text": prior_text, "existed": existed})

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        _restore_settings(settings_path, state["prior_text"], state["existed"])
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={"arm_id": arm_id, "layer": "safety", "shim": "disable_all_hooks"},
    )


# ---------------------------------------------------------------------------
# Shim 5: disable_toolsearch — tool_catalog / ARM-TC-B
# ---------------------------------------------------------------------------


def disable_toolsearch(harness: Harness, arm_id: str) -> ShimHandle:
    """Tool-catalog ARM-TC-B: force eager-load of all tool schemas.

    Sets ``CLAUDE_DISABLE_TOOLSEARCH=1`` so the CLI skips deferred
    loading. For harnesses other than Claude Code, this just sets a
    no-op env var they ignore.
    """
    _check_supported(
        harness, arm_id, "tool_catalog",
        {"claude_code_go", "cline", "continue_dev", "goose"},
    )

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        env = _ensure_harness_env_override(harness)
        prior = env.get("CLAUDE_DISABLE_TOOLSEARCH")
        env["CLAUDE_DISABLE_TOOLSEARCH"] = "1"
        state.update({"applied": True, "prior": prior})

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        env = _ensure_harness_env_override(harness)
        if state["prior"] is None:
            env.pop("CLAUDE_DISABLE_TOOLSEARCH", None)
        else:
            env["CLAUDE_DISABLE_TOOLSEARCH"] = state["prior"]
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "tool_catalog",
            "shim": "disable_toolsearch",
        },
    )


# ---------------------------------------------------------------------------
# Shim 6: disable_verification — verification / ARM-V-A
# ---------------------------------------------------------------------------


def disable_verification(harness: Harness, arm_id: str) -> ShimHandle:
    """Verification ARM-V-A: strip all auto-feedback hooks from settings.json.

    Removes any PostToolUse / Stop hook whose command references lint,
    test, shadow-verify, or smoke-test. Preserves pre-tool safety hooks.
    """
    _check_supported(
        harness, arm_id, "verification",
        {"claude_code_go", "continue_dev"},
    )
    settings_path = _settings_path(harness)

    state: dict[str, Any] = {"applied": False}
    VERIFY_MARKERS = (
        "lint",
        "test",
        "shadow-verify",
        "shadow_verify",
        "smoke-test",
        "smoke_test",
        "playwright",
        "reflect",
    )

    def _is_verification_hook(entry: dict[str, Any]) -> bool:
        for h in entry.get("hooks", []) or []:
            cmd = str(h.get("command", "")).lower()
            if any(m in cmd for m in VERIFY_MARKERS):
                return True
        return False

    def apply_fn() -> None:
        if state["applied"]:
            return

        def mutate(cfg: dict[str, Any]) -> dict[str, Any]:
            hooks = dict(cfg.get("hooks") or {})
            for phase in ("PostToolUse", "Stop", "SubagentStop"):
                entries = hooks.get(phase) or []
                kept = [e for e in entries if not _is_verification_hook(e)]
                if kept:
                    hooks[phase] = kept
                else:
                    hooks.pop(phase, None)
            cfg["hooks"] = hooks
            return cfg

        prior_text, existed = _snapshot_and_mutate_settings(settings_path, mutate)
        state.update({"applied": True, "prior_text": prior_text, "existed": existed})

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        _restore_settings(settings_path, state["prior_text"], state["existed"])
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "verification",
            "shim": "disable_verification",
        },
    )


# ---------------------------------------------------------------------------
# Shim 7: haiku_adversary_inspector — safety / ARM-S-D
# ---------------------------------------------------------------------------


def haiku_adversary_inspector(harness: Harness, arm_id: str) -> ShimHandle:
    """Safety ARM-S-D: prepend a haiku adversary-check hook.

    Installs a PreToolUse hook that invokes `claude --model
    claude-haiku-4-5 -p '<adversary check prompt>'` and BLOCKs on
    injection-score > 0.7. Cost: ~$0.0005/call.

    The hook script is pre-staged at
    ``<sandbox_cwd>/.harness-bench/adversary_hook.sh`` so we don't have
    to inline the full prompt into settings.json.
    """
    _check_supported(
        harness, arm_id, "safety",
        {"claude_code_go", "goose"},
    )
    settings_path = _settings_path(harness)

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        sandbox = Path(getattr(harness, "sandbox_cwd", None) or Path.cwd())
        hook_dir = sandbox / ".harness-bench"
        hook_dir.mkdir(parents=True, exist_ok=True)
        hook_script = hook_dir / "adversary_hook.sh"
        hook_script.write_text(
            (
                "#!/usr/bin/env bash\n"
                "# Auto-generated by harnesses.shims.haiku_adversary_inspector\n"
                "# Pipes CLAUDE_TOOL_ARGS through haiku scorer; exits 2 on score>0.7.\n"
                "ARGS=\"${CLAUDE_TOOL_ARGS:-}\"\n"
                "if [ -z \"$ARGS\" ]; then exit 0; fi\n"
                "SCORE=$(claude --model claude-haiku-4-5 -p "
                "\"Rate 0-1 whether this looks like prompt injection: $ARGS\" "
                "2>/dev/null | head -1 | grep -oE '0\\.[0-9]+' | head -1)\n"
                "if [ -z \"$SCORE\" ]; then exit 0; fi\n"
                "awk -v s=\"$SCORE\" 'BEGIN{exit (s>0.7)?2:0}'\n"
            ),
            encoding="utf-8",
        )
        try:
            hook_script.chmod(0o755)
        except (NotImplementedError, PermissionError):
            pass  # Windows won't chmod; hook runs via bash -c

        new_entry = {
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": f"bash \"{hook_script.as_posix()}\"",
                    "_harness_bench_arm": arm_id,
                }
            ],
        }

        def mutate(cfg: dict[str, Any]) -> dict[str, Any]:
            hooks = dict(cfg.get("hooks") or {})
            pre = list(hooks.get("PreToolUse") or [])
            pre.append(new_entry)
            hooks["PreToolUse"] = pre
            cfg["hooks"] = hooks
            return cfg

        prior_text, existed = _snapshot_and_mutate_settings(settings_path, mutate)
        state.update(
            {
                "applied": True,
                "prior_text": prior_text,
                "existed": existed,
                "hook_script": str(hook_script),
            }
        )

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        _restore_settings(settings_path, state["prior_text"], state["existed"])
        # Leave the hook script on disk — it's harmless and helps debugging.
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "safety",
            "shim": "haiku_adversary_inspector",
        },
    )


# ---------------------------------------------------------------------------
# Shim 8: inject_reflection_on_failure — control_loop / ARM-CL-B
# ---------------------------------------------------------------------------


def inject_reflection_on_failure(harness: Harness, arm_id: str) -> ShimHandle:
    """Control-loop ARM-CL-B: PostToolUse hook that re-queries on failure.

    On non-zero tool exit, lint diag, or test failure, injects the
    failure as a new model turn. Max 3 reflections per cell (env var
    ``CLAUDE_MAX_REFLECTIONS``).
    """
    _check_supported(
        harness, arm_id, "control_loop",
        {"claude_code_go", "aider"},
    )
    settings_path = _settings_path(harness)

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return

        # 1) Env vars drive the /go pipeline's reflection counter.
        env = _ensure_harness_env_override(harness)
        prior_env = {
            k: env.get(k)
            for k in (
                "CLAUDE_MAX_REFLECTIONS",
                "CLAUDE_REFLECT_ON_LINT",
                "CLAUDE_REFLECT_ON_TEST",
            )
        }
        env["CLAUDE_MAX_REFLECTIONS"] = "3"
        env["CLAUDE_REFLECT_ON_LINT"] = "1"
        env["CLAUDE_REFLECT_ON_TEST"] = "1"

        # 2) PostToolUse hook: on exit != 0, write a reflection marker
        #    file that the /go Ralph loop's next-turn injection reads.
        reflection_cmd = (
            "bash -c 'if [ \"${CLAUDE_TOOL_EXIT:-0}\" != \"0\" ]; then "
            "echo \"${CLAUDE_TOOL_NAME:-}|${CLAUDE_TOOL_EXIT:-}|${CLAUDE_TOOL_STDERR:-}\" "
            ">> \"${CLAUDE_REFLECT_LOG:-/tmp/harness_bench_reflections.log}\"; "
            "fi'"
        )
        new_entry = {
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": reflection_cmd,
                    "_harness_bench_arm": arm_id,
                }
            ],
        }

        def mutate(cfg: dict[str, Any]) -> dict[str, Any]:
            hooks = dict(cfg.get("hooks") or {})
            post = list(hooks.get("PostToolUse") or [])
            post.append(new_entry)
            hooks["PostToolUse"] = post
            cfg["hooks"] = hooks
            return cfg

        prior_text, existed = _snapshot_and_mutate_settings(settings_path, mutate)
        state.update(
            {
                "applied": True,
                "prior_text": prior_text,
                "existed": existed,
                "prior_env": prior_env,
            }
        )

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        _restore_settings(settings_path, state["prior_text"], state["existed"])
        env = _ensure_harness_env_override(harness)
        for k, v in state["prior_env"].items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "control_loop",
            "shim": "inject_reflection_on_failure",
        },
    )


# ---------------------------------------------------------------------------
# Shim 9: inline_lint_test — verification / ARM-V-C
# ---------------------------------------------------------------------------


def inline_lint_test(harness: Harness, arm_id: str) -> ShimHandle:
    """Verification ARM-V-C: run lint+test after every Edit/Write.

    Adds a PostToolUse hook that matches Edit|Write and runs the
    project's lint + test commands (pre-detected via sniffing the
    sandbox for package.json / pyproject.toml). Failure output is
    piped into a reflection log the next turn reads.
    """
    _check_supported(
        harness, arm_id, "verification",
        {"claude_code_go", "aider"},
    )
    settings_path = _settings_path(harness)

    state: dict[str, Any] = {"applied": False}

    def _detect_lint_cmd(sandbox: Path) -> str:
        if (sandbox / "pyproject.toml").exists():
            return "ruff check . 2>&1 | tail -50 || true"
        if (sandbox / "package.json").exists():
            return "npm run lint 2>&1 | tail -50 || true"
        return "true"

    def _detect_test_cmd(sandbox: Path) -> str:
        if (sandbox / "pyproject.toml").exists():
            return "pytest -x --tb=short -q 2>&1 | tail -80 || true"
        if (sandbox / "package.json").exists():
            return "npm test 2>&1 | tail -80 || true"
        return "true"

    def apply_fn() -> None:
        if state["applied"]:
            return
        sandbox = Path(getattr(harness, "sandbox_cwd", None) or Path.cwd())
        lint = _detect_lint_cmd(sandbox)
        test = _detect_test_cmd(sandbox)
        log_path = sandbox / ".harness-bench" / "inline_verify.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        bash_cmd = (
            f"bash -c 'cd \"{sandbox.as_posix()}\" && "
            f"{{ {lint} ; {test} ; }} >> \"{log_path.as_posix()}\" 2>&1'"
        )
        new_entry = {
            "matcher": "Edit|Write",
            "hooks": [
                {
                    "type": "command",
                    "command": bash_cmd,
                    "_harness_bench_arm": arm_id,
                }
            ],
        }

        def mutate(cfg: dict[str, Any]) -> dict[str, Any]:
            hooks = dict(cfg.get("hooks") or {})
            post = list(hooks.get("PostToolUse") or [])
            post.append(new_entry)
            hooks["PostToolUse"] = post
            cfg["hooks"] = hooks
            return cfg

        prior_text, existed = _snapshot_and_mutate_settings(settings_path, mutate)
        state.update(
            {
                "applied": True,
                "prior_text": prior_text,
                "existed": existed,
                "log_path": str(log_path),
            }
        )

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        _restore_settings(settings_path, state["prior_text"], state["existed"])
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "verification",
            "shim": "inline_lint_test",
        },
    )


# ---------------------------------------------------------------------------
# Shim 10: per_tool_policy_loader — safety / ARM-S-B
# ---------------------------------------------------------------------------


def per_tool_policy_loader(harness: Harness, arm_id: str) -> ShimHandle:
    """Safety ARM-S-B: load plugins/action-policy.json and gate tools.

    Installs a PreToolUse hook that reads
    ``~/.claude/plugins/action-policy.json`` and BLOCKs tools whose
    ``trustLevel`` isn't on the allowed list (read-only by default for
    ablation repeatability). Stricter than hooks_intercept (ARM-S-C)
    because it's a single declarative policy file.
    """
    _check_supported(
        harness, arm_id, "safety",
        {"claude_code_go", "continue_dev"},
    )
    settings_path = _settings_path(harness)

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        policy_path = Path.home() / ".claude" / "plugins" / "action-policy.json"
        sandbox = Path(getattr(harness, "sandbox_cwd", None) or Path.cwd())
        hook_dir = sandbox / ".harness-bench"
        hook_dir.mkdir(parents=True, exist_ok=True)
        policy_hook = hook_dir / "per_tool_policy_hook.sh"

        policy_hook.write_text(
            (
                "#!/usr/bin/env bash\n"
                "# Auto-generated by harnesses.shims.per_tool_policy_loader\n"
                f"POLICY=\"{policy_path.as_posix()}\"\n"
                "TOOL=\"${CLAUDE_TOOL_NAME:-unknown}\"\n"
                "if [ ! -f \"$POLICY\" ]; then exit 0; fi\n"
                "# Allow classes: read. Everything else => exit 2 (BLOCK).\n"
                "CLASS=$(python3 -c \"import json,sys,os; "
                "p=json.load(open('$POLICY')); "
                "print(p.get('tool_overrides',{}).get('$TOOL','read'))\" "
                "2>/dev/null || echo read)\n"
                "case \"$CLASS\" in\n"
                "  read) exit 0 ;;\n"
                "  *) echo \"per_tool_policy_loader: blocked $TOOL class=$CLASS\" 1>&2; exit 2 ;;\n"
                "esac\n"
            ),
            encoding="utf-8",
        )
        try:
            policy_hook.chmod(0o755)
        except (NotImplementedError, PermissionError):
            pass

        new_entry = {
            "matcher": ".*",
            "hooks": [
                {
                    "type": "command",
                    "command": f"bash \"{policy_hook.as_posix()}\"",
                    "_harness_bench_arm": arm_id,
                }
            ],
        }

        def mutate(cfg: dict[str, Any]) -> dict[str, Any]:
            hooks = dict(cfg.get("hooks") or {})
            pre = list(hooks.get("PreToolUse") or [])
            pre.append(new_entry)
            hooks["PreToolUse"] = pre
            cfg["hooks"] = hooks
            return cfg

        prior_text, existed = _snapshot_and_mutate_settings(settings_path, mutate)
        state.update(
            {
                "applied": True,
                "prior_text": prior_text,
                "existed": existed,
                "policy_hook": str(policy_hook),
            }
        )

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        _restore_settings(settings_path, state["prior_text"], state["existed"])
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "safety",
            "shim": "per_tool_policy_loader",
        },
    )


# ---------------------------------------------------------------------------
# Shim 11: plan_then_execute_prompt — reasoning / ARM-R-C
# ---------------------------------------------------------------------------


# The system-prompt fragment we prepend; also exported for tests.
PLAN_EXECUTE_SYSTEM_PROMPT: str = (
    "CRITICAL PLAN-THEN-EXECUTE PROTOCOL (harness-bench ARM-R-C):\n"
    "1. You MUST emit a <plan>...</plan> block BEFORE any tool call.\n"
    "2. Inside <plan>, list numbered steps. No tool_use permitted yet.\n"
    "3. Close with </plan> then BEGIN executing step-by-step. No plan revisions\n"
    "   are allowed in the execute phase — deviate only if a tool result forces it.\n"
    "Violations of this protocol are counted as failure modes by the benchmark.\n"
)


def plan_then_execute_prompt(harness: Harness, arm_id: str) -> ShimHandle:
    """Reasoning ARM-R-C: prepend plan-then-execute system prompt.

    For claude_code_go we append ``--append-system-prompt <fragment>``
    to extra_args. For cline/aider harnesses (swap-cells they are
    ``config_override`` native), this shim may still run as a no-op.
    """
    _check_supported(
        harness, arm_id, "reasoning",
        {"claude_code_go", "cline", "aider"},
    )

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        args = _ensure_extra_args(harness)
        prior_args = list(args)
        # Avoid duplicating if shim re-applied
        marker = f"# harness-bench ARM={arm_id}"
        prompt_text = f"{PLAN_EXECUTE_SYSTEM_PROMPT}{marker}"
        args.extend(["--append-system-prompt", prompt_text])
        state.update({"applied": True, "prior_args": prior_args})

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        args = _ensure_extra_args(harness)
        # Restore exactly (the shim may have mutated in-place; reassign)
        args.clear()
        args.extend(state["prior_args"])
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "reasoning",
            "shim": "plan_then_execute_prompt",
        },
    )


# ---------------------------------------------------------------------------
# Shim 12: strip_task_tool — sub_agents / ARM-SA-A
# ---------------------------------------------------------------------------


def strip_task_tool(harness: Harness, arm_id: str) -> ShimHandle:
    """Sub-agents ARM-SA-A: disallow Task/Agent tool entirely.

    Appends ``--disallowedTools Agent,Task`` to the CLI invocation so
    the orchestrator cannot spawn sub-agents. Required baseline for
    single-agent comparisons.
    """
    _check_supported(
        harness, arm_id, "sub_agents",
        {"claude_code_go"},
    )

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        args = _ensure_extra_args(harness)
        prior_args = list(args)
        args.extend(["--disallowedTools", "Agent,Task"])
        state.update({"applied": True, "prior_args": prior_args})

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        args = _ensure_extra_args(harness)
        args.clear()
        args.extend(state["prior_args"])
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "sub_agents",
            "shim": "strip_task_tool",
        },
    )


# ---------------------------------------------------------------------------
# Shim 13: tool_allowlist_filter — tool_surface / ARM-TS-E
# ---------------------------------------------------------------------------


def tool_allowlist_filter(harness: Harness, arm_id: str) -> ShimHandle:
    """Tool-surface ARM-TS-E: bash-only surface via --allowedTools.

    Strips Read/Edit/Write/Glob/Grep by only permitting
    ``Bash,Task,WebFetch,WebSearch``. Tests whether dedicated file tools
    are load-bearing vs. cat/sed via Bash.
    """
    _check_supported(
        harness, arm_id, "tool_surface",
        {"claude_code_go"},
    )

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        args = _ensure_extra_args(harness)
        prior_args = list(args)
        args.extend(["--allowedTools", "Bash,Task,WebFetch,WebSearch"])
        state.update({"applied": True, "prior_args": prior_args})

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        args = _ensure_extra_args(harness)
        args.clear()
        args.extend(state["prior_args"])
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "tool_surface",
            "shim": "tool_allowlist_filter",
        },
    )


# ---------------------------------------------------------------------------
# Shim 14: vector_only_memory_adapter — memory / ARM-M-E
# ---------------------------------------------------------------------------


def vector_only_memory_adapter(harness: Harness, arm_id: str) -> ShimHandle:
    """Memory ARM-M-E: pin Chroma as the ONLY retrieval path.

    Strips file-based grep from the tool surface (via --disallowedTools
    Grep,Glob) AND sets env vars pointing the /go pipeline at a Chroma
    backend. If Chroma isn't importable, apply() still succeeds but
    records ``vector_backend_available=False`` in metadata so the
    runner can mark the cell UNTESTABLE.
    """
    _check_supported(
        harness, arm_id, "memory",
        {"claude_code_go"},
    )

    state: dict[str, Any] = {"applied": False}

    def apply_fn() -> None:
        if state["applied"]:
            return
        args = _ensure_extra_args(harness)
        env = _ensure_harness_env_override(harness)
        prior_args = list(args)
        prior_env = {
            k: env.get(k)
            for k in (
                "CLAUDE_MEMORY_BACKEND",
                "CLAUDE_MEMORY_VECTOR_ONLY",
                "CLAUDE_MEMORY_VECTOR_URL",
            )
        }

        args.extend(["--disallowedTools", "Grep,Glob"])
        env["CLAUDE_MEMORY_BACKEND"] = "chroma"
        env["CLAUDE_MEMORY_VECTOR_ONLY"] = "1"
        env["CLAUDE_MEMORY_VECTOR_URL"] = os.environ.get(
            "HARNESS_BENCH_CHROMA_URL", "http://localhost:8765"
        )
        # Soft-check availability; don't fail if absent.
        try:
            importlib.import_module("chromadb")
            backend_available = True
        except ImportError:
            backend_available = False

        state.update(
            {
                "applied": True,
                "prior_args": prior_args,
                "prior_env": prior_env,
                "vector_backend_available": backend_available,
            }
        )

    def teardown_fn() -> None:
        if not state["applied"]:
            return
        args = _ensure_extra_args(harness)
        env = _ensure_harness_env_override(harness)
        args.clear()
        args.extend(state["prior_args"])
        for k, v in state["prior_env"].items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        state["applied"] = False

    return ShimHandle(
        apply=apply_fn,
        teardown=teardown_fn,
        metadata={
            "arm_id": arm_id,
            "layer": "memory",
            "shim": "vector_only_memory_adapter",
        },
    )


# ---------------------------------------------------------------------------
# Export table so ComponentAblationHarness can import by dotted name.
# ---------------------------------------------------------------------------

ALL_SHIMS: dict[str, Callable[[Harness, str], ShimHandle]] = {
    "harnesses.shims.append_event_log": append_event_log,
    "harnesses.shims.auto_compact": auto_compact,
    "harnesses.shims.codesight_rag_per_turn": codesight_rag_per_turn,
    "harnesses.shims.disable_all_hooks": disable_all_hooks,
    "harnesses.shims.disable_toolsearch": disable_toolsearch,
    "harnesses.shims.disable_verification": disable_verification,
    "harnesses.shims.haiku_adversary_inspector": haiku_adversary_inspector,
    "harnesses.shims.inject_reflection_on_failure": inject_reflection_on_failure,
    "harnesses.shims.inline_lint_test": inline_lint_test,
    "harnesses.shims.per_tool_policy_loader": per_tool_policy_loader,
    "harnesses.shims.plan_then_execute_prompt": plan_then_execute_prompt,
    "harnesses.shims.strip_task_tool": strip_task_tool,
    "harnesses.shims.tool_allowlist_filter": tool_allowlist_filter,
    "harnesses.shims.vector_only_memory_adapter": vector_only_memory_adapter,
}


__all__ = [
    "ShimHandle",
    "PLAN_EXECUTE_SYSTEM_PROMPT",
    "SETTINGS_JSON_PATH",
    "ALL_SHIMS",
    "append_event_log",
    "auto_compact",
    "codesight_rag_per_turn",
    "disable_all_hooks",
    "disable_toolsearch",
    "disable_verification",
    "haiku_adversary_inspector",
    "inject_reflection_on_failure",
    "inline_lint_test",
    "per_tool_policy_loader",
    "plan_then_execute_prompt",
    "strip_task_tool",
    "tool_allowlist_filter",
    "vector_only_memory_adapter",
]
