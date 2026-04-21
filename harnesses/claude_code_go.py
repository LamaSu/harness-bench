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
- Cost attribution: parses ``--output-format stream-json`` NDJSON from
  stdout. Each turn's ``assistant.message.usage`` block carries partial
  token counts, and the final ``result`` event carries the authoritative
  ``total_cost_usd`` and aggregate ``usage`` totals. See
  ``docs/stream-json-schema.md`` for a full annotated sample captured
  from Claude Code CLI v2.1.116.
- Legacy codeburn fallback: if stream-json parsing surfaces zero cost
  (e.g. older CLI build that doesn't emit ``total_cost_usd``) we fall
  back to a pre/post codeburn snapshot. This keeps the adapter usable
  on Windows-only dev machines where codeburn is reachable but the CLI
  is pinned to a pre-stream-json version.
- ``--max-budget-usd`` is forwarded as a hint flag; not all ``claude``
  CLI builds honour it. Treat the cap as advisory, not enforced.
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
        - Spawns `claude -p "/go <task>" --output-format stream-json
          --verbose` as a subprocess in a sandbox cwd.
        - Captures stdout line-by-line as NDJSON; each line is routed
          through ``_parse_stdout_line`` which classifies the event type
          (thinking / tool_call / tool_result / message / completion)
          and updates the cost accumulator when the final ``result``
          event arrives with ``total_cost_usd``.
        - Token + dollar accounting: stream-json ``result.usage`` +
          ``result.total_cost_usd`` is authoritative. Codeburn snapshot
          delta is retained only as a fallback for older CLI builds.
        - Component-ablation arms wired via env vars / settings.json
          mutations by ComponentAblationHarness; this class just
          validates the layer is supported.

    See docs/02-harness-survey.md §1.7 for layer-by-layer coverage,
    docs/04-bench-spec.md §3.2 for the per-harness subprocess contract,
    and docs/stream-json-schema.md for the NDJSON event taxonomy.
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
        # Accumulator for per-run stream-json cost. Reset at the start of
        # every submit_task() call; the final `result` event overwrites
        # it with the authoritative totals.
        self._stream_cost_accumulator: Cost = Cost()

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
        # --output-format stream-json REQUIRES --verbose in non-interactive
        # (-p) mode. Both are appended together; see docs/stream-json-schema.md.
        cmd: list[str] = [
            self.claude_bin,
            "-p", full_prompt,
            "--model", self.model,
            "--max-budget-usd", str(self.max_budget_usd),
            "--output-format", "stream-json",
            "--verbose",
        ]
        cmd.extend(self.extra_args)

        # Reset the per-run stream-cost accumulator. Any previous run's
        # totals stay in self._cost (cumulative); this captures just this
        # submit_task() invocation's spend.
        self._stream_cost_accumulator = Cost()

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

        # Line-by-line NDJSON parse. _parse_stdout_line also updates
        # self._stream_cost_accumulator as a side effect when it sees
        # the final `result` message. Events we classify as internal
        # (system / result / rate_limit_event) return None and are
        # dropped from the yielded stream.
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

        # Compute final cost for this submit_task(). Prefers stream-json
        # accumulator; codeburn fallback only if stream-json saw zero.
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
        """Cost for the most recent submit_task() (via stream-json).

        Note: this is NOT cumulative across multiple submit_task() calls
        — each invocation replaces self._cost with that run's totals.
        If you need a cross-task aggregate, sum get_token_cost() into
        your own accumulator between calls. The stream-json `result`
        event always reports per-run totals, not session-lifetime.
        """
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

    def _parse_stdout_line(self, line: str) -> Event | None:
        """Parse one stream-json line into an Event (or yield a batch of them).

        For ``assistant`` messages the CLI can bundle multiple content blocks
        (thinking + tool_use + text) into a single event. We pick the FIRST
        semantically meaningful block to emit here; callers that want every
        content block should iterate ``payload["message"]["content"]``
        themselves.

        Side effect: updates ``self._stream_cost_accumulator`` whenever a
        ``result`` event carries ``total_cost_usd`` or a per-turn
        ``assistant`` event carries a ``usage`` block (the latter is
        fallback-only and not summed — see ``docs/stream-json-schema.md``
        on why per-turn ``usage`` would double-count across split
        thinking/tool_use content blocks).

        Returns ``None`` for ``system`` / ``result`` / ``rate_limit_event``
        messages (consumed internally) so the caller drops them from the
        Event stream — except for the ``result`` event, which the outer
        submit_task() loop detects by reading the accumulator.
        """
        stripped = line.strip()
        # Try JSON first (real stream-json output)
        if not (stripped.startswith("{") or stripped.startswith("[")):
            # Stray plain-text line (unusual with stream-json but possible
            # if hook stderr leaks into stdout on some builds).
            return Event(
                kind="text",
                payload={"line": line},
                timestamp_unix=time.time(),
            )
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return Event(
                kind="text",
                payload={"line": line},
                timestamp_unix=time.time(),
            )
        if not isinstance(parsed, dict):
            return Event(
                kind="text",
                payload={"line": line},
                timestamp_unix=time.time(),
            )

        msg_type = parsed.get("type")
        now = time.time()

        # ---- system / rate_limit: drop silently --------------------------
        if msg_type in ("system", "rate_limit_event"):
            return None

        # ---- result: authoritative cost + aggregate usage ----------------
        if msg_type == "result":
            usage = parsed.get("usage") or {}
            dollars = float(parsed.get("total_cost_usd") or 0.0)
            self._stream_cost_accumulator = Cost(
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                cached_input_tokens=(
                    int(usage.get("cache_read_input_tokens") or 0)
                    + int(usage.get("cache_creation_input_tokens") or 0)
                ),
                dollars=dollars,
            )
            # Don't emit as an Event — submit_task() emits its own
            # "completion" event after draining the stream so consumers
            # see a single canonical finish marker.
            return None

        # ---- user: tool_result payloads fed back to the model ------------
        if msg_type == "user":
            message = parsed.get("message") or {}
            content_list = message.get("content") or []
            # Pull out the first tool_result entry if present.
            for block in content_list:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    return Event(
                        kind="tool_result",
                        payload={
                            "tool_use_id": block.get("tool_use_id"),
                            "is_error": bool(block.get("is_error")),
                            "content": block.get("content"),
                            "stdout": (parsed.get("tool_use_result") or {}).get("stdout"),
                            "stderr": (parsed.get("tool_use_result") or {}).get("stderr"),
                            "session_id": parsed.get("session_id"),
                            "uuid": parsed.get("uuid"),
                        },
                        timestamp_unix=now,
                    )
            # No tool_result block — drop.
            return None

        # ---- assistant: message / thinking / tool_call -------------------
        if msg_type == "assistant":
            message = parsed.get("message") or {}
            content_list = message.get("content") or []
            # Pick the first block we can classify. (Most assistant events
            # emitted by the CLI contain a single content block; when they
            # contain multiple, we prefer tool_use > thinking > text.)
            chosen = None
            for priority in ("tool_use", "thinking", "text"):
                for block in content_list:
                    if isinstance(block, dict) and block.get("type") == priority:
                        chosen = block
                        break
                if chosen is not None:
                    break

            model_id = message.get("model")
            msg_id = message.get("id")
            session_id = parsed.get("session_id")
            uuid_ = parsed.get("uuid")

            if chosen is None:
                # Unrecognized content shape — still emit something so the
                # trace doesn't lose the event.
                return Event(
                    kind="message",
                    payload={
                        "raw_message": message,
                        "session_id": session_id,
                        "uuid": uuid_,
                        "model": model_id,
                    },
                    timestamp_unix=now,
                )

            block_type = chosen.get("type")
            if block_type == "tool_use":
                return Event(
                    kind="tool_call",
                    payload={
                        "tool_use_id": chosen.get("id"),
                        "tool_name": chosen.get("name"),
                        "tool_input": chosen.get("input"),
                        "caller": chosen.get("caller"),
                        "session_id": session_id,
                        "uuid": uuid_,
                        "model": model_id,
                        "message_id": msg_id,
                    },
                    timestamp_unix=now,
                )
            if block_type == "thinking":
                return Event(
                    kind="thinking",
                    payload={
                        "thinking": chosen.get("thinking"),
                        "session_id": session_id,
                        "uuid": uuid_,
                        "model": model_id,
                        "message_id": msg_id,
                    },
                    timestamp_unix=now,
                )
            # default: text → message
            return Event(
                kind="message",
                payload={
                    "text": chosen.get("text"),
                    "session_id": session_id,
                    "uuid": uuid_,
                    "model": model_id,
                    "message_id": msg_id,
                },
                timestamp_unix=now,
            )

        # ---- unknown types: pass through as 'text' ----------------------
        return Event(
            kind=str(msg_type or "text"),
            payload=parsed,
            timestamp_unix=now,
        )

    async def _compute_cost_delta(self) -> Cost:
        """Return the best available cost for the just-finished submit_task().

        Prefers the stream-json accumulator (authoritative, includes
        cache-tier pricing). Falls back to the codeburn snapshot-delta
        pattern only if stream-json parsing produced zero dollars AND a
        baseline was captured at initialize().
        """
        if self._stream_cost_accumulator.dollars > 0.0:
            return self._stream_cost_accumulator
        # Fallback: pre-stream-json CLI builds or aborted runs where no
        # `result` event was emitted. Only meaningful on Windows dev boxes
        # with a running codeburn dashboard.
        if self._cost_baseline is not None:
            current = self._fetch_codeburn_snapshot()
            return current.delta(self._cost_baseline)
        return Cost()

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
