#!/usr/bin/env python3
"""
runner.py — minimal sweep runner for harness-bench.

Reads a sweep yaml (e.g. sweeps/v1-smoke.yaml), for each axis:
  - Imports the task factory module and calls fn(limit_kwarg=max_samples_per_axis)
  - Pulls the Inspect-AI `dataset` out of the returned Task
  - For each Sample: drives the input through the target harness adapter
    (e.g. ClaudeCodeGoHarness), captures the final text, and scores it
    with a substring+token-match heuristic against sample.target
  - Writes per-sample JSONL to results/<sweep.name>-<timestamp>/results.jsonl
  - Emits a per-axis summary into the same directory

This is the v1-smoke scaffold. It does NOT use model_graded_qa as the headline
scorer (too expensive for 45 samples that each already cost a /go subprocess
run). Instead, it captures the full response + target so a follow-up
scorer pass can re-score with model_graded_qa downstream.

Usage:
    python scripts/runner.py --sweep sweeps/v1-smoke.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Ensure the harness-bench repo root is on PYTHONPATH so tasks/harnesses import.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harnesses.claude_code_go import ClaudeCodeGoHarness


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace + strip leading/trailing non-alnum."""
    t = text.lower()
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", t)
    return t


def _token_set(text: str) -> set[str]:
    """Crude alphanumeric tokenization."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def score_substring_inclusion(response: str, target: str) -> float:
    """Heuristic score: 1.0 if target substring in response; 0.7 if all
    target tokens present in response; else a fractional token-recall."""
    if not response or not target:
        return 0.0
    resp_norm = _normalize(response)
    targ_norm = _normalize(target)
    if not targ_norm:
        return 0.0
    if targ_norm in resp_norm:
        return 1.0
    targ_toks = _token_set(target)
    resp_toks = _token_set(response)
    if not targ_toks:
        return 0.0
    overlap = len(targ_toks & resp_toks) / len(targ_toks)
    if overlap >= 0.9:
        return 0.7
    return round(overlap, 3)


# ----------------------------------------------------------------------
# Dataset extraction from Inspect-AI Task
# ----------------------------------------------------------------------

def _task_to_samples(task_obj: Any, limit: int) -> list[Any]:
    """Return up to `limit` Sample objects from an Inspect-AI Task.

    Inspect-AI datasets are iterable; materialize the first N.
    """
    try:
        ds = task_obj.dataset
    except AttributeError:
        raise RuntimeError(f"Task object has no .dataset attribute: {type(task_obj)!r}")

    samples: list[Any] = []
    iterator = iter(ds)
    for i, sample in enumerate(iterator):
        if i >= limit:
            break
        samples.append(sample)
    return samples


def _extract_sample_text(sample: Any) -> tuple[str, str]:
    """Coerce (input_str, target_str) from an Inspect-AI Sample.

    Handles both simple-string inputs and the multi-modal content-chunk form.
    """
    inp = sample.input
    # Inspect can store input as str OR as list[Content{Text,Image}]
    if isinstance(inp, str):
        input_str = inp
    elif isinstance(inp, list):
        parts: list[str] = []
        for chunk in inp:
            # ContentText has .text; ContentImage just note it exists
            txt = getattr(chunk, "text", None)
            if txt:
                parts.append(str(txt))
            elif hasattr(chunk, "image"):
                parts.append("[IMAGE]")
        input_str = "\n".join(parts)
    else:
        input_str = str(inp)

    target = sample.target
    if isinstance(target, list):
        target_str = "\n".join(str(t) for t in target)
    else:
        target_str = str(target)

    return input_str, target_str


# ----------------------------------------------------------------------
# Response extraction from harness Events
# ----------------------------------------------------------------------

def _extract_response(events: list[dict[str, Any]]) -> str:
    """Scan the Event list from a harness run for the most plausible final
    textual response.

    Strategy:
        1. Prefer any Event with kind == "completion" that carries a text
           payload.
        2. Otherwise take the last `text`-kind Event's payload.line.
        3. Fallback: concatenate all text lines.
    """
    # 1. look for explicit completion/message/text with substantial content
    for ev in reversed(events):
        kind = ev.get("kind", "")
        payload = ev.get("payload", {}) or {}
        # Message-style payload
        for key in ("response", "text", "message", "content", "output"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # Line-style (from our _parse_stdout_line fallback)
        line = payload.get("line")
        if kind == "text" and isinstance(line, str) and line.strip():
            return line.strip()

    # 3. concatenate
    parts = []
    for ev in events:
        payload = ev.get("payload", {}) or {}
        line = payload.get("line")
        if isinstance(line, str):
            parts.append(line)
    return "\n".join(parts).strip()


# ----------------------------------------------------------------------
# Running one sample through a harness
# ----------------------------------------------------------------------

async def run_one_sample(
    harness: ClaudeCodeGoHarness,
    axis: str,
    arm: str,
    sample_idx: int,
    sample: Any,
    timeout_s: int,
    per_sample_budget_usd: float,
) -> dict[str, Any]:
    """Drive one Sample through the harness and return a result row."""
    input_str, target_str = _extract_sample_text(sample)
    prompt_hash = hashlib.sha256(input_str.encode("utf-8", errors="replace")).hexdigest()[:16]

    t0 = time.time()
    events: list[dict[str, Any]] = []
    error_msg: str | None = None

    try:
        async for ev in harness.submit_task(input_str, tools=[]):
            events.append({
                "kind": ev.kind,
                "payload": ev.payload,
                "timestamp_unix": ev.timestamp_unix,
            })
            # Bail early if a fatal error Event came through
            if ev.kind == "error" and ev.payload.get("error") == "spawn_failed":
                error_msg = f"spawn_failed: {ev.payload.get('exception')}"
                break
    except asyncio.TimeoutError:
        error_msg = f"asyncio timeout after {timeout_s}s"
    except Exception as exc:  # noqa: BLE001
        error_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}"

    wall_s = time.time() - t0
    response = _extract_response(events)
    score = score_substring_inclusion(response, target_str) if response else 0.0
    cost = harness.get_token_cost()

    # Extract the completion event's exit_code if present
    completion = next(
        (e for e in events if e.get("kind") == "completion"),
        None,
    )
    exit_code = completion.get("payload", {}).get("exit_code") if completion else None

    # Error events captured during run
    err_events = [e for e in events if e.get("kind") == "error"]

    return {
        "axis": axis,
        "arm": arm,
        "sample_idx": sample_idx,
        "prompt_hash": prompt_hash,
        "input_preview": input_str[:500],
        "input_len_chars": len(input_str),
        "target": target_str[:500],
        "target_len_chars": len(target_str),
        "response": response[:2000],
        "response_len_chars": len(response),
        "score": score,
        "wall_clock_s": round(wall_s, 2),
        "cost_input_tokens": cost.input_tokens,
        "cost_output_tokens": cost.output_tokens,
        "cost_dollars": cost.dollars,
        "exit_code": exit_code,
        "error": error_msg,
        "n_events": len(events),
        "error_events": err_events[:3],  # cap to 3 for size
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
    }


# ----------------------------------------------------------------------
# Running one axis
# ----------------------------------------------------------------------

async def run_one_axis(
    axis_cfg: dict[str, Any],
    harness_model: str,
    max_samples: int,
    timeout_s: int,
    per_sample_budget_usd: float,
    out_jsonl: Path,
) -> dict[str, Any]:
    """Run all samples for one axis. Returns a per-axis summary dict."""
    axis = axis_cfg["id"]
    arm = axis_cfg["arm"]
    task_module_name = axis_cfg["task"]
    fn_name = axis_cfg["fn"]
    limit_kwarg = axis_cfg["limit_kwarg"]

    print(f"\n{'=' * 60}", flush=True)
    print(f"[axis:{axis}] start arm={arm} module={task_module_name} fn={fn_name}", flush=True)
    print(f"{'=' * 60}", flush=True)

    summary = {
        "axis": axis,
        "arm": arm,
        "task_module": task_module_name,
        "start_iso": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "n_planned": max_samples,
        "n_completed": 0,
        "n_errored": 0,
        "n_successful": 0,
        "scores": [],
        "wall_clocks": [],
    }

    # Import task module + call factory
    try:
        mod = importlib.import_module(task_module_name)
        fn = getattr(mod, fn_name)
        task_obj = fn(**{limit_kwarg: max_samples})
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}"
        print(f"[axis:{axis}] TASK_LOAD_ERROR: {err}", flush=True)
        summary["status"] = "task_load_error"
        summary["error"] = err
        summary["end_iso"] = datetime.now(timezone.utc).isoformat()
        return summary

    # Materialize samples
    try:
        samples = _task_to_samples(task_obj, max_samples)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}"
        print(f"[axis:{axis}] DATASET_ERROR: {err}", flush=True)
        summary["status"] = "dataset_error"
        summary["error"] = err
        summary["end_iso"] = datetime.now(timezone.utc).isoformat()
        return summary

    n_planned = len(samples)
    summary["n_planned"] = n_planned
    print(f"[axis:{axis}] materialized {n_planned} samples", flush=True)

    if n_planned == 0:
        summary["status"] = "empty_dataset"
        summary["end_iso"] = datetime.now(timezone.utc).isoformat()
        return summary

    # Create ONE harness per axis (reuse sandbox cwd) — reduces init overhead
    sandbox_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"harness-bench-sandbox-{axis}-{int(time.time())}"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    harness = ClaudeCodeGoHarness(
        model=harness_model,
        sandbox_cwd=sandbox_dir,
        timeout_s=timeout_s,
        max_budget_usd=per_sample_budget_usd,
        use_go_skill=True,
    )
    harness.initialize(sandbox=None)

    for idx, sample in enumerate(samples):
        t0 = time.time()
        print(f"[axis:{axis}] sample {idx + 1}/{n_planned} begin", flush=True)
        try:
            row = await asyncio.wait_for(
                run_one_sample(
                    harness=harness,
                    axis=axis,
                    arm=arm,
                    sample_idx=idx,
                    sample=sample,
                    timeout_s=timeout_s,
                    per_sample_budget_usd=per_sample_budget_usd,
                ),
                timeout=timeout_s + 60,
            )
        except asyncio.TimeoutError:
            row = {
                "axis": axis,
                "arm": arm,
                "sample_idx": idx,
                "score": 0.0,
                "error": f"outer_timeout_{timeout_s}s",
                "wall_clock_s": round(time.time() - t0, 2),
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            row = {
                "axis": axis,
                "arm": arm,
                "sample_idx": idx,
                "score": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
                "wall_clock_s": round(time.time() - t0, 2),
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
            }

        # Append to JSONL
        with open(out_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

        score = row.get("score") or 0.0
        wall = row.get("wall_clock_s") or 0.0
        err = row.get("error")
        summary["n_completed"] += 1
        summary["scores"].append(score)
        summary["wall_clocks"].append(wall)
        if err:
            summary["n_errored"] += 1
        if score >= 0.7:
            summary["n_successful"] += 1

        print(
            f"[axis:{axis}] sample {idx + 1}/{n_planned} done "
            f"score={score:.2f} wall={wall:.1f}s err={bool(err)}",
            flush=True,
        )

    summary["status"] = "done"
    summary["end_iso"] = datetime.now(timezone.utc).isoformat()
    if summary["scores"]:
        summary["mean_score"] = round(sum(summary["scores"]) / len(summary["scores"]), 3)
        summary["mean_wall_clock_s"] = round(sum(summary["wall_clocks"]) / len(summary["wall_clocks"]), 2)
    else:
        summary["mean_score"] = 0.0
        summary["mean_wall_clock_s"] = 0.0
    return summary


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------

async def main_async(args: argparse.Namespace) -> int:
    sweep_path = Path(args.sweep)
    with open(sweep_path, encoding="utf-8") as f:
        sweep = yaml.safe_load(f)

    model = sweep.get("model", "claude-sonnet-4-6")
    max_samples = int(sweep.get("max_samples_per_axis", 5))
    timeout_s = int(sweep.get("timeout_per_sample_s", 600))
    per_sample_budget_usd = float(sweep.get("budget_per_sample_usd", 2.00))
    axes = sweep["axes"]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_template = sweep.get("output", "results/{name}-{timestamp}/").format(
        name=sweep.get("name", "sweep"),
        timestamp=timestamp,
    )
    output_dir = REPO_ROOT / output_template.rstrip("/")
    output_dir.mkdir(parents=True, exist_ok=True)

    results_jsonl = output_dir / "results.jsonl"
    axis_summaries_jsonl = output_dir / "axis_summaries.jsonl"
    sweep_meta_json = output_dir / "sweep_meta.json"

    meta = {
        "sweep_name": sweep.get("name"),
        "sweep_file": str(sweep_path),
        "harness": sweep.get("harness"),
        "model": model,
        "max_samples_per_axis": max_samples,
        "timeout_per_sample_s": timeout_s,
        "budget_per_sample_usd": per_sample_budget_usd,
        "n_axes": len(axes),
        "start_iso": datetime.now(timezone.utc).isoformat(),
        "results_jsonl": str(results_jsonl),
        "output_dir": str(output_dir),
    }
    with open(sweep_meta_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"[sweep] name={meta['sweep_name']} axes={meta['n_axes']} out={output_dir}", flush=True)

    # Run axes sequentially so we don't blow up /go concurrency.
    axis_summaries: list[dict[str, Any]] = []
    for axis_cfg in axes:
        summary = await run_one_axis(
            axis_cfg=axis_cfg,
            harness_model=model,
            max_samples=max_samples,
            timeout_s=timeout_s,
            per_sample_budget_usd=per_sample_budget_usd,
            out_jsonl=results_jsonl,
        )
        axis_summaries.append(summary)
        with open(axis_summaries_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")

    meta["end_iso"] = datetime.now(timezone.utc).isoformat()
    meta["axis_summaries"] = axis_summaries
    with open(sweep_meta_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n[sweep] DONE. Results: {results_jsonl}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="harness-bench sweep runner")
    parser.add_argument(
        "--sweep",
        required=True,
        help="path to sweep yaml (e.g. sweeps/v1-smoke.yaml)",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
