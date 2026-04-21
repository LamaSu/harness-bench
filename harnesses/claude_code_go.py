"""
Claude Code (Go binary) /go pipeline harness adapter.

The Anthropic Claude Code CLI in Go-binary form (`harness serve` MCP +
`claude` CLI). Open core, hooks-based, BRAID/Ralph-loop conventions
established in CLAUDE.md. Used as the REFERENCE harness for ablation
arms.

This adapter drives the `/go` skill: a multi-agent pipeline (intake →
wheel-scout → hydrate → build/forge/skill → test → checkpoint). Calls
out via subprocess to the user's globally installed `claude` CLI in a
sandboxed cwd so the bench repo itself isn't mutated by /go's writes.

Survey: docs/02-harness-survey.md §1.7 (Claude Code + /go pipeline).
Spec:   docs/04-bench-spec.md §3 (Harness adapter interface) + §3.2
        (per-harness subprocess pattern).
Component coverage (per docs/02-harness-survey.md §4.x): all 8 layers,
        though `/go` PINS some (e.g. control_loop CL-A) — direct
        per-layer ablation is implemented by the
        ComponentAblationHarness wrapper which mutates
        ~/.claude/settings.json + injects arm-specific env vars before
        spawning this adapter.

Notes
-----
- /go runs are LONG (minutes; pipeline spawns 5-15 sub-agents).
  Default timeout is 600s; bump for full-sweep mode.
- Subprocess runs in its OWN cwd (sandbox). Never the benchmark repo.
- Cost attribution is best-effort: we snapshot the codeburn API
  (http://localhost:3457/api/codeburn) before + after the run and take
  the delta. If codeburn isn't reachable (dashboard not running) we
  return zero cost rather than fail the cell — the runner's separate
  Anthropic-billing reconciliation is the source of truth.
- `--max-budget-usd` is forwarded as a hint flag; not all `claude` CLI
  builds honour it. Treat the cap as advisory, not enforced.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from harnesses.base import (
    HARNESS_LAYERS,
    Cost,
    Event,
    Harness,
    Tool,
    UnsupportedAblationError,
)

# Layers this harness exposes to the component-ablation matrix.
# Per docs/02-harness-survey.md §1.7 and §4.x, /go touches all 8 — though
# arm SELECTION for several of them is delegated to ComponentAblationHarness
# (set_component here only validates layer membership; the wrapper does the
# actual settings.json / env-var mutation).
SUPPORTED_ABLATION_LAYERS: tuple[str, ...] = HARNESS_LAYERS  # all 8

# Codeburn API endpoint — local dashboard exposes per-session token spend.
# Reference: ~/.claude/CLAUDE.md "GenUI Integration" section.
CODEBURN_URL = "http://localhost:3457/api/codeburn"


class ClaudeCodeGoHarness(Harness):
    """Harness over the Claude Code Go binary + `claude` CLI driving /go.

    Driver strategy (per spec §3.2):
        - Spawns `claude -p "/go <task>"` as a subprocess in a sandbox cwd.
        - Captures stdout line-by-line; parses each line as JSON if
          possible, else emits as a `text` Event. (Real-time stream-json
          parsing is a future improvement once `--output-format
          stream-json` stabilizes across CLI builds.)
        - Token + dollar accounting: pre/post snapshot of codeburn API.
        - Component-ablation arms wired via env vars / settings.json
          mutations by ComponentAblationHarness; this class just
          validates the layer is supported.

    See docs/02-harness-survey.md §1.7 for layer-by-layer coverage and
    docs/04-bench-spec.md §3.2 for the per-harness subprocess contract.
    """

    name: str = "claude-code-go"

    def __init__(
        self,
        model: str = "claude-opus-4-7",
        *,
        claude_bin: str | None = None,
        sandbox_cwd: str | Path | None = None,
        timeout_s: int = 600,
        max_budget_usd: float = 2.00,
        use_go_skill: bool = True,
        extra_args: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Create the adapter.

        :param model: target model id (passed through to ``claude --model``).
        :param claude_bin: explicit path to the `claude` CLI; defaults to
            whatever ``shutil.which("claude")`` returns.
        :param sandbox_cwd: directory the subprocess runs in. Defaults to
            an OS-appropriate temp dir.
        :param timeout_s: kill the subprocess after this many seconds.
        :param max_budget_usd: forwarded as ``--max-budget-usd`` (advisory;
            not all CLI builds enforce).
        :param use_go_skill: if True, prefix prompt with ``/go ``; if False,
            send the prompt raw and let skill auto-routing kick in. Both
            paths exist so the runner can A/B them.
        :param extra_args: appended to the ``claude`` invocation verbatim
            (e.g. ``["--dangerously-skip-permissions"]`` in CI).
        """
        super().__init__(model, **kwargs)
        self.claude_bin = claude_bin or shutil.which("claude") or "claude"
        # Default sandbox: OS-appropriate temp dir under a stable name so
        # repeat invocations re-use the same workspace (cheaper for /go's
        # CodeSight index + memory files).
        if sandbox_cwd is None:
            base_tmp = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp")
            sandbox_cwd = base_tmp / "harness-bench-claude-go-sandbox"
        self.sandbox_cwd = Path(sandbox_cwd)
        self.timeout_s = timeout_s
        self.max_budget_usd = max_budget_usd
        self.use_go_skill = use_go_skill
        self.extra_args: list[str] = list(extra_args or [])

        self._cost: Cost = Cost()  # cumulative since initialize()
        self._wall_clock: float = 0.0  # cumulative seconds
        self._cost_baseline: Cost | None = None  # codeburn snapshot @ init

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self, sandbox: Any) -> None:  # noqa: ARG002
        """Create the sandbox cwd + snapshot starting cost.

        ``sandbox`` is the Inspect AI sandbox handle (Docker/K8s/Modal).
        For now we ignore it and use a local cwd — Inspect AI sandbox
        integration is a follow-up. Idempotent.
        """
        self.sandbox_cwd.mkdir(parents=True, exist_ok=True)
        # Cost baseline so subsequent get_token_cost() returns a delta,
        # not the lifetime codeburn total. Best-effort: zero on failure.
        self._cost_baseline = self._fetch_codeburn_snapshot()
        self._cost = Cost()  # reset cumulative
        self._wall_clock = 0.0
        self._initialized = True

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    async def submit_task(  # type: ignore[override]
        self,
        prompt: str,
        tools: list[Tool],  # noqa: ARG002 — /go discovers its own tools
    ) -> AsyncIterator[Event]:
        """Spawn `claude -p` in the sandbox; stream stdout as Events.

        Note: `tools` is accepted to satisfy the ABC but not forwarded —
        /go's tool surface is determined by the user's installed plugins
        + skills + MCP servers, not by the bench. To compare apples-to-
        apples across harnesses, the runner pre-stages a known plugin
        set in the sandbox's ~/.claude/ before initialize().
        """
        full_prompt = f"/go {prompt}" if self.use_go_skill else prompt
        cmd: list[str] = [
            self.claude_bin,
            "-p", full_prompt,
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
        ]
        cmd.extend(self.extra_args)

        t0 = time.time()
        # Emit a synthetic "spawn" event so consumers can mark the start
        # of this task in their trace timeline.
        yield Event(
            kind="spawn",
            payload={"cmd": cmd, "cwd": str(self.sandbox_cwd), "prompt": prompt},
            timestamp_unix=t0,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.sandbox_cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as exc:
            # `claude` not installed / not on PATH. Yield error + bail.
            self._wall_clock += time.time() - t0
            yield Event(
                kind="error",
                payload={"error": "spawn_failed", "exception": repr(exc), "cmd": cmd},
                timestamp_unix=time.time(),
            )
            return

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_s,
            )
        except asyncio.TimeoutError:
            proc.kill()
            # Drain whatever the process emitted before the kill so
            # we don't lose the partial trace.
            try:
                stdout_b, stderr_b = await proc.communicate()
            except Exception:  # noqa: BLE001
                stdout_b, stderr_b = b"", b""
            self._wall_clock += time.time() - t0
            yield Event(
                kind="error",
                payload={
                    "error": "timeout",
                    "timeout_s": self.timeout_s,
                    "stdout_tail": stdout_b.decode("utf-8", errors="replace")[-1000:],
                    "stderr_tail": stderr_b.decode("utf-8", errors="replace")[-1000:],
                },
                timestamp_unix=time.time(),
            )
            return

        self._wall_clock += time.time() - t0

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")

        # Best-effort line-by-line parse. /go writes a mix of:
        #   - status bars (ignored as `text` events)
        #   - agent spawn announcements
        #   - tool-call traces (when --output-format=stream-json is wired)
        # For now, attempt JSON-parse-then-fallback-to-text per line.
        for line in stdout.splitlines():
            if not line.strip():
                continue
            event = self._parse_stdout_line(line)
            if event is not None:
                yield event

        if proc.returncode != 0:
            yield Event(
                kind="error",
                payload={
                    "exit_code": proc.returncode,
                    "stderr_tail": stderr[-1000:],
                },
                timestamp_unix=time.time(),
            )

        # Refresh cost attribution from codeburn delta.
        self._cost = await self._compute_cost_delta()

        yield Event(
            kind="completion",
            payload={
                "exit_code": proc.returncode,
                "wall_clock_s": self._wall_clock,
                "cost_dollars": self._cost.dollars,
                "input_tokens": self._cost.input_tokens,
                "output_tokens": self._cost.output_tokens,
            },
            timestamp_unix=time.time(),
        )

    # ------------------------------------------------------------------
    # Cost + wall-clock accessors
    # ------------------------------------------------------------------

    def get_token_cost(self) -> Cost:
        """Cumulative cost since initialize(). Best-effort via codeburn."""
        return self._cost

    def get_wall_clock(self) -> float:
        """Cumulative wall-clock seconds since initialize()."""
        return self._wall_clock

    # ------------------------------------------------------------------
    # Component ablation
    # ------------------------------------------------------------------

    def supports_component_ablation(self, layer: str) -> bool:
        return layer in SUPPORTED_ABLATION_LAYERS

    def set_component(self, layer: str, arm: str) -> None:
        """Record arm selection for ``layer``.

        The actual mutation of ~/.claude/settings.json + env vars is the
        responsibility of ComponentAblationHarness (per docs §3.3). This
        method just validates the layer membership and records the arm
        in self._arms so the wrapper can read it back.
        """
        if layer not in SUPPORTED_ABLATION_LAYERS:
            raise UnsupportedAblationError(self.name, layer, arm)
        self._arms[layer] = arm

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_stdout_line(line: str) -> Event | None:
        """Parse one stdout line into an Event, or return None to drop it."""
        stripped = line.strip()
        # Try JSON first (real stream-json output)
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                kind = parsed.get("kind") or parsed.get("type") or "text"
                return Event(
                    kind=str(kind),
                    payload=parsed,
                    timestamp_unix=time.time(),
                )
        # Fallback: treat as plain text / status line.
        return Event(
            kind="text",
            payload={"line": line},
            timestamp_unix=time.time(),
        )

    async def _compute_cost_delta(self) -> Cost:
        """Return (current codeburn snapshot - baseline taken at init)."""
        current = self._fetch_codeburn_snapshot()
        baseline = self._cost_baseline or Cost()
        return current.delta(baseline)

    @staticmethod
    def _fetch_codeburn_snapshot() -> Cost:
        """One-shot codeburn API read. Returns Cost() on any error.

        Synchronous + tiny so it's safe to call from initialize() too.
        Uses urllib stdlib (no httpx dependency for a 1-call helper).
        """
        try:
            import urllib.request

            with urllib.request.urlopen(CODEBURN_URL, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 — best-effort; cost is informational
            return Cost()

        # The codeburn endpoint returns a session-scoped object; field
        # names vary across versions, so we probe a few candidates.
        session = data.get("session", data)
        return Cost(
            input_tokens=int(session.get("input_tokens", 0) or 0),
            output_tokens=int(session.get("output_tokens", 0) or 0),
            cached_input_tokens=int(session.get("cached_input_tokens", 0) or 0),
            dollars=float(session.get("cost", session.get("dollars", 0.0)) or 0.0),
        )


__all__ = [
    "SUPPORTED_ABLATION_LAYERS",
    "ClaudeCodeGoHarness",
    "CODEBURN_URL",
]
