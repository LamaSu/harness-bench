# Claude CLI `--output-format stream-json` Schema

Captured from Claude Code CLI **v2.1.116** on 2026-04-21 via
`claude -p "..." --output-format stream-json --model claude-sonnet-4-6 --verbose`.

## Overview

`stream-json` emits **one JSON object per line** (NDJSON). Each line is a
self-contained event. The stream is terminated by a single `result` event
containing aggregate cost + token totals (`total_cost_usd`). That final
`result` message is the **source of truth** for cost attribution — per-turn
`usage` blocks in `assistant` events are partial and exclude the cache-tier
pricing multipliers the CLI applies.

## Required flags

`stream-json` **requires `--verbose`** for non-interactive (`-p`) mode. Without
it the CLI errors out. Always pass both together.

```bash
claude -p "<prompt>" --output-format stream-json --verbose --model <id>
```

## Event types

### `system` — startup / hook lifecycle

Two subtypes matter:

- `system.hook_started` / `system.hook_response` — project hooks fire.
  Harness consumers should ignore these (no payload semantics).
- `system.init` — emitted once per session. Fields include `cwd`,
  `session_id`, `tools`, `mcp_servers`, `model`, `permissionMode`,
  `slash_commands`, `agents`, `skills`, `plugins`, `memory_paths`.
  No cost / token data.
- `system.notification` — `priority: immediate` notifications (e.g.
  `stop-hook-error`). Not cost-bearing.

### `assistant` — per-turn model output

```jsonc
{
  "type": "assistant",
  "message": {
    "model": "claude-sonnet-4-6",
    "id": "msg_01Th7qrr28shNgoKqLSsptRm",
    "type": "message",
    "role": "assistant",
    "content": [
      { "type": "text", "text": "4" }
      // OR
      // { "type": "thinking", "thinking": "...", "signature": "..." }
      // OR
      // { "type": "tool_use", "id": "toolu_...", "name": "Bash",
      //   "input": { "command": "ls", "description": "..." },
      //   "caller": { "type": "direct" } }
    ],
    "stop_reason": null,
    "usage": {
      "input_tokens": 3,
      "cache_creation_input_tokens": 6273,
      "cache_read_input_tokens": 12688,
      "cache_creation": {
        "ephemeral_5m_input_tokens": 0,
        "ephemeral_1h_input_tokens": 6273
      },
      "output_tokens": 1,
      "service_tier": "standard",
      "inference_geo": "not_available"
    }
  },
  "parent_tool_use_id": null,
  "session_id": "...",
  "uuid": "..."
}
```

The `usage` block here reports tokens for **this specific turn**, but the
CLI re-emits a new assistant event per `content[]` block split during a
single API response (one `thinking` event, then one `tool_use` event with
identical `message.id` and identical `usage` counts). Summing across all
`assistant` events will double-count. Prefer the final `result.usage`.

Each `content[]` entry maps to a distinct Event kind in our harness:

| Content block `type` | Harness `Event.kind` |
|----------------------|----------------------|
| `text`               | `message`            |
| `thinking`           | `thinking`           |
| `tool_use`           | `tool_call`          |

### `user` — tool-call results fed back to the model

```jsonc
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "tool_use_id": "toolu_01AxusCKKD5JfEFv1YCk6ekN",
        "type": "tool_result",
        "content": "README.md\ncorpus\ndocs\n...",
        "is_error": false
      }
    ]
  },
  "parent_tool_use_id": null,
  "session_id": "...",
  "uuid": "...",
  "timestamp": "2026-04-21T19:55:11.408Z",
  "tool_use_result": {
    "stdout": "...",
    "stderr": "",
    "interrupted": false,
    "isImage": false,
    "noOutputExpected": false
  }
}
```

Maps to `Event.kind == "tool_result"`. No `usage` block (tool results are
injected by the harness, not billed).

### `rate_limit_event` — rate limiter status

```jsonc
{
  "type": "rate_limit_event",
  "rate_limit_info": {
    "status": "allowed",
    "resetsAt": 1776805200,
    "rateLimitType": "five_hour",
    "overageStatus": "rejected",
    "overageDisabledReason": "org_level_disabled",
    "isUsingOverage": false
  },
  "uuid": "...",
  "session_id": "..."
}
```

Informational; no cost impact. Can be dropped or emitted as a
low-priority telemetry event.

### `result` — final summary (source of truth for cost)

```jsonc
{
  "type": "result",
  "subtype": "success",          // or "error"
  "is_error": false,
  "api_error_status": null,
  "duration_ms": 5614,
  "duration_api_ms": 5497,
  "num_turns": 2,
  "result": "<assistant's final text>",
  "stop_reason": "end_turn",
  "session_id": "...",
  "total_cost_usd": 0.058358549999999995,
  "usage": {
    "input_tokens": 4,
    "cache_creation_input_tokens": 12721,
    "cache_read_input_tokens": 25376,
    "output_tokens": 202,
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": 0
    },
    "service_tier": "standard",
    "cache_creation": {
      "ephemeral_1h_input_tokens": 12721,
      "ephemeral_5m_input_tokens": 0
    },
    "iterations": [
      {
        "input_tokens": 1,
        "output_tokens": 83,
        "cache_read_input_tokens": 12688,
        "cache_creation_input_tokens": 6443,
        "cache_creation": { /* ... */ },
        "type": "message"
      }
    ],
    "speed": "standard"
  },
  "modelUsage": {
    "claude-sonnet-4-6": {
      "inputTokens": 4,
      "outputTokens": 202,
      "cacheReadInputTokens": 25376,
      "cacheCreationInputTokens": 12721,
      "webSearchRequests": 0,
      "costUSD": 0.058358549999999995,
      "contextWindow": 200000,
      "maxOutputTokens": 32000
    }
  },
  "permission_denials": [],
  "terminal_reason": "completed",
  "fast_mode_state": "off",
  "uuid": "..."
}
```

**`total_cost_usd`** is the authoritative dollar figure — the CLI has
already applied cache-tier pricing (ephemeral 5m vs 1h), inference-geo
multipliers, and service-tier adjustments. Our adapter treats this as
canonical and ignores per-turn `usage.input_tokens * rate_card` maths.

Token totals for the Harness `Cost` object:

- `usage.input_tokens` → `Cost.input_tokens`
- `usage.output_tokens` → `Cost.output_tokens`
- `usage.cache_read_input_tokens` + `usage.cache_creation_input_tokens`
  → `Cost.cached_input_tokens` (both count against the 200k context but at
  different rates — for ablation-telemetry purposes we sum them)
- `total_cost_usd` → `Cost.dollars`

## Sample run (full stream, annotated)

Prompt: `"List files in the current directory using the Bash tool"`,
model: `claude-sonnet-4-6`, two turns (tool_use + text follow-up).

```
1. {"type":"system","subtype":"hook_started",...}       # startup hook
2. {"type":"system","subtype":"hook_response",...}      # hook completed
3. {"type":"system","subtype":"init",...}               # session init
4. {"type":"assistant","message":{...thinking...}}      # Event(kind=thinking)
5. {"type":"assistant","message":{...tool_use Bash...}} # Event(kind=tool_call)
6. {"type":"rate_limit_event",...}                      # informational
7. {"type":"user","message":{...tool_result...}}        # Event(kind=tool_result)
8. {"type":"assistant","message":{...text...}}          # Event(kind=message)
9. {"type":"system","subtype":"notification",...}       # stop-hook error
10. {"type":"result","subtype":"success",...,           # Event(kind=completion)
     "total_cost_usd":0.058358549999999995,
     "usage":{"input_tokens":4,"output_tokens":202,...}}
```

## Reference run (`what is 2+2`, single turn)

`total_cost_usd`: **0.027414149999999998** (~$0.027, one-shot sonnet-4-6 with
~19k cached-context tokens across 5m and 1h ephemeral tiers + 1 output tok).

## Implementation notes

- Split stdout on `\n`; each complete line that starts with `{` is a valid
  JSON event. Trailing hook-error noise (e.g. Node `MODULE_NOT_FOUND`
  stack traces) arrives on **stderr** — parse stdout only.
- `result` may arrive with `subtype == "error"` (e.g. API failure). In that
  case `total_cost_usd` may still be non-zero (partial usage). Always read it.
- Cache-creation + cache-read are non-trivial on any session past the first
  — the `cost_baseline` pattern (pre/post codeburn snapshot) is obsolete
  when each run has its own `result.total_cost_usd`.
- Tool-call inputs are JSON-serialized in `content[].input`; tool-call
  outputs arrive on the **next** `user` event keyed by `tool_use_id`.
