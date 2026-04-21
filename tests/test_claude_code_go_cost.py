"""Cost-smoke tests for the Claude Code /go harness stream-json parser.

Two layers:

1. **Offline parser tests** — exercise ``_parse_stdout_line`` with a frozen
   NDJSON sample captured from Claude Code CLI v2.1.116 (see
   ``docs/stream-json-schema.md``). These are pure-Python, no subprocess.
2. **Live smoke test** — actually invokes ``claude -p "..." --output-format
   stream-json`` and asserts the adapter surfaces a non-zero dollar cost.
   Skipped unless ``CLAUDE_COSTSMOKE_LIVE=1`` is set and ``claude`` is on
   PATH (gates network calls in CI).

Run via::

    pytest tests/test_claude_code_go_cost.py -v
    CLAUDE_COSTSMOKE_LIVE=1 pytest tests/test_claude_code_go_cost.py::test_live_cost -v
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil

import pytest

from harnesses.base import Cost
from harnesses.claude_code_go import ClaudeCodeGoHarness


# ---------------------------------------------------------------------------
# Frozen stream-json fixture (captured 2026-04-21 from claude CLI v2.1.116,
# `claude -p "what is 2+2" --output-format stream-json --model claude-sonnet-4-6
# --verbose` on Spark). Only the events that exercise our parser paths are
# retained; the stack-trace noise from the Windows-pathed hooks is dropped.
# ---------------------------------------------------------------------------

FROZEN_STREAM: list[dict] = [
    {
        "type": "system",
        "subtype": "init",
        "cwd": "/home/ryangeorge/projects/harness-bench",
        "session_id": "7f6b7062",
        "model": "claude-sonnet-4-6",
        "uuid": "4ea16e72",
    },
    {
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-6",
            "id": "msg_01Th7qrr",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "4"}],
            "stop_reason": None,
            "usage": {
                "input_tokens": 3,
                "cache_creation_input_tokens": 6273,
                "cache_read_input_tokens": 12688,
                "output_tokens": 1,
            },
        },
        "parent_tool_use_id": None,
        "session_id": "7f6b7062",
        "uuid": "c9888fdd",
    },
    {
        "type": "rate_limit_event",
        "rate_limit_info": {"status": "allowed", "resetsAt": 1776805200},
        "session_id": "7f6b7062",
        "uuid": "4739a73c",
    },
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 1528,
        "num_turns": 1,
        "result": "4",
        "stop_reason": "end_turn",
        "session_id": "7f6b7062",
        "total_cost_usd": 0.027414149999999998,
        "usage": {
            "input_tokens": 3,
            "cache_creation_input_tokens": 6273,
            "cache_read_input_tokens": 12688,
            "output_tokens": 5,
        },
        "uuid": "f1cb4fe8",
    },
]


FROZEN_STREAM_WITH_TOOL: list[dict] = [
    {"type": "system", "subtype": "init", "session_id": "s", "uuid": "u-init"},
    {
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-6",
            "id": "msg_thinking",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "Need to list files."}],
        },
        "session_id": "s",
        "uuid": "u-think",
    },
    {
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-6",
            "id": "msg_toolcall",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "Bash",
                    "input": {"command": "ls", "description": "list dir"},
                    "caller": {"type": "direct"},
                }
            ],
        },
        "session_id": "s",
        "uuid": "u-tool",
    },
    {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "tool_use_id": "toolu_abc",
                    "type": "tool_result",
                    "content": "README.md\ndocs",
                    "is_error": False,
                }
            ],
        },
        "tool_use_result": {"stdout": "README.md\ndocs", "stderr": ""},
        "session_id": "s",
        "uuid": "u-toolres",
    },
    {
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-6",
            "id": "msg_final",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Files: README.md, docs"}],
        },
        "session_id": "s",
        "uuid": "u-final",
    },
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 5614,
        "result": "Files: README.md, docs",
        "session_id": "s",
        "total_cost_usd": 0.058358549999999995,
        "usage": {
            "input_tokens": 4,
            "cache_creation_input_tokens": 12721,
            "cache_read_input_tokens": 25376,
            "output_tokens": 202,
        },
        "uuid": "u-result",
    },
]


# ---------------------------------------------------------------------------
# Unit tests (pure-Python, no subprocess)
# ---------------------------------------------------------------------------


def _fresh_harness() -> ClaudeCodeGoHarness:
    h = ClaudeCodeGoHarness(
        model="claude-sonnet-4-6",
        claude_bin="claude",
        use_go_skill=False,
        timeout_s=30,
    )
    h.initialize(sandbox=None)
    return h


def test_parser_drops_system_and_rate_limit() -> None:
    h = _fresh_harness()
    sys_line = json.dumps(FROZEN_STREAM[0])
    rl_line = json.dumps(FROZEN_STREAM[2])
    assert h._parse_stdout_line(sys_line) is None
    assert h._parse_stdout_line(rl_line) is None


def test_parser_emits_message_for_assistant_text() -> None:
    h = _fresh_harness()
    ev = h._parse_stdout_line(json.dumps(FROZEN_STREAM[1]))
    assert ev is not None
    assert ev.kind == "message"
    assert ev.payload["text"] == "4"
    assert ev.payload["model"] == "claude-sonnet-4-6"
    assert ev.payload["message_id"] == "msg_01Th7qrr"


def test_parser_emits_thinking_tool_call_tool_result() -> None:
    h = _fresh_harness()
    think_ev = h._parse_stdout_line(json.dumps(FROZEN_STREAM_WITH_TOOL[1]))
    tool_ev = h._parse_stdout_line(json.dumps(FROZEN_STREAM_WITH_TOOL[2]))
    result_ev = h._parse_stdout_line(json.dumps(FROZEN_STREAM_WITH_TOOL[3]))

    assert think_ev is not None and think_ev.kind == "thinking"
    assert think_ev.payload["thinking"] == "Need to list files."

    assert tool_ev is not None and tool_ev.kind == "tool_call"
    assert tool_ev.payload["tool_name"] == "Bash"
    assert tool_ev.payload["tool_input"] == {"command": "ls", "description": "list dir"}
    assert tool_ev.payload["tool_use_id"] == "toolu_abc"

    assert result_ev is not None and result_ev.kind == "tool_result"
    assert result_ev.payload["tool_use_id"] == "toolu_abc"
    assert result_ev.payload["is_error"] is False


def test_parser_accumulates_cost_from_result_event() -> None:
    h = _fresh_harness()
    assert h._stream_cost_accumulator == Cost()
    for item in FROZEN_STREAM:
        h._parse_stdout_line(json.dumps(item))
    accum = h._stream_cost_accumulator
    assert accum.dollars == pytest.approx(0.02741415, rel=1e-6)
    assert accum.input_tokens == 3
    assert accum.output_tokens == 5
    # cache_read + cache_creation folded into cached_input_tokens
    assert accum.cached_input_tokens == 12688 + 6273


def test_parser_accumulates_across_multi_turn_stream() -> None:
    h = _fresh_harness()
    for item in FROZEN_STREAM_WITH_TOOL:
        h._parse_stdout_line(json.dumps(item))
    accum = h._stream_cost_accumulator
    assert accum.dollars == pytest.approx(0.05835855, rel=1e-6)
    assert accum.input_tokens == 4
    assert accum.output_tokens == 202
    assert accum.cached_input_tokens == 12721 + 25376


def test_malformed_lines_degrade_to_text_event() -> None:
    h = _fresh_harness()
    ev = h._parse_stdout_line('{"type": "assistant"  # malformed')
    assert ev is not None
    assert ev.kind == "text"

    ev2 = h._parse_stdout_line("plain status bar line with no JSON")
    assert ev2 is not None
    assert ev2.kind == "text"


def test_compute_cost_delta_prefers_stream_accumulator() -> None:
    """After a run with a non-zero stream accumulator, the adapter must
    return that value regardless of the codeburn baseline (which may be
    empty on Spark)."""
    h = _fresh_harness()
    for item in FROZEN_STREAM:
        h._parse_stdout_line(json.dumps(item))
    cost = asyncio.run(h._compute_cost_delta())
    assert cost.dollars == pytest.approx(0.02741415, rel=1e-6)
    assert cost.input_tokens == 3
    assert cost.output_tokens == 5


# ---------------------------------------------------------------------------
# Live smoke — only runs when CLAUDE_COSTSMOKE_LIVE=1
# ---------------------------------------------------------------------------

_LIVE = os.environ.get("CLAUDE_COSTSMOKE_LIVE") == "1"


@pytest.mark.skipif(not _LIVE, reason="Set CLAUDE_COSTSMOKE_LIVE=1 to run live smoke")
@pytest.mark.skipif(
    shutil.which("claude") is None, reason="claude CLI not on PATH"
)
def test_live_cost_smoke() -> None:
    """Invoke the real claude CLI and confirm we observe non-zero cost."""

    async def _run() -> Cost:
        h = ClaudeCodeGoHarness(
            model="claude-sonnet-4-6",
            use_go_skill=False,
            timeout_s=60,
        )
        h.initialize(sandbox=None)
        seen_kinds: list[str] = []
        async for ev in h.submit_task(
            "What is the capital of Mongolia? Respond with just the city name.",
            [],
        ):
            seen_kinds.append(ev.kind)
        return h.get_token_cost()

    cost = asyncio.run(_run())
    assert cost.dollars > 0.0, f"expected >0 dollars, got {cost}"
    assert cost.input_tokens > 0
    assert cost.output_tokens > 0
