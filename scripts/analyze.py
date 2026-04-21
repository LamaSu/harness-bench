#!/usr/bin/env python3
"""
analyze.py — post-hoc stats over a runner.py result directory.

Reads results.jsonl + axis_summaries.jsonl from a v1-smoke (or any) sweep,
computes:
    - per-axis: n, mean_score, mean_cost_usd, mean_wall_s, success_rate(>=0.7),
      error_rate
    - aggregate harness Pareto point: x=mean_cost_usd across axes, y=mean_score
    - coarse time-horizon estimate: longest axis at which success_rate >= 0.5

Writes summary.md + summary.json in-place into the sweep dir.

Usage:
    python scripts/analyze.py results/v1-smoke-<ts>/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def per_axis_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group by axis and compute summary stats."""
    by_axis: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ax = r.get("axis", "?")
        by_axis.setdefault(ax, []).append(r)

    stats: dict[str, dict[str, Any]] = {}
    for ax, items in by_axis.items():
        scores = [float(it.get("score") or 0.0) for it in items]
        wallclocks = [float(it.get("wall_clock_s") or 0.0) for it in items]
        costs = [float(it.get("cost_dollars") or 0.0) for it in items]
        errors = [1 for it in items if it.get("error")]
        successes = [1 for s in scores if s >= 0.7]

        n = len(items)
        stats[ax] = {
            "n": n,
            "mean_score": round(mean(scores), 3) if scores else 0.0,
            "max_score": round(max(scores), 3) if scores else 0.0,
            "min_score": round(min(scores), 3) if scores else 0.0,
            "mean_wall_s": round(mean(wallclocks), 2) if wallclocks else 0.0,
            "mean_cost_usd": round(mean(costs), 4) if costs else 0.0,
            "sum_cost_usd": round(sum(costs), 4) if costs else 0.0,
            "error_rate": round(len(errors) / n, 3) if n else 0.0,
            "success_rate": round(len(successes) / n, 3) if n else 0.0,
            "n_errored": len(errors),
            "n_successful": len(successes),
        }
    return stats


def pareto_point(per_axis: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Aggregate /go Pareto point: mean across axes of mean_cost & mean_score."""
    if not per_axis:
        return {"x_cost_usd": 0.0, "y_score": 0.0, "n_axes": 0}
    xs = [v["mean_cost_usd"] for v in per_axis.values()]
    ys = [v["mean_score"] for v in per_axis.values()]
    return {
        "x_cost_usd_mean": round(mean(xs), 4),
        "x_cost_usd_total": round(sum(xs), 4),
        "y_score": round(mean(ys), 3),
        "n_axes": len(per_axis),
    }


def time_horizon_estimate(per_axis: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Very coarse METR-style time-horizon estimate.

    With n=5/axis, real time-horizon requires n>=20. We provide a rough
    indication: the worst-case axis where success_rate >= 0.5, and the
    spread of success rates across axes.
    """
    if not per_axis:
        return {"horizon_passing_axes": [], "note": "no data"}
    passing = [(ax, v["success_rate"]) for ax, v in per_axis.items() if v["success_rate"] >= 0.5]
    return {
        "horizon_passing_axes": sorted(passing, key=lambda x: x[1], reverse=True),
        "all_success_rates": {ax: v["success_rate"] for ax, v in per_axis.items()},
        "note": "coarse — n=5 per axis; need n>=20 for stable estimate",
    }


def render_summary_md(
    meta: dict[str, Any],
    per_axis: dict[str, dict[str, Any]],
    pareto: dict[str, float],
    horizon: dict[str, Any],
    n_rows: int,
) -> str:
    lines: list[str] = []
    lines.append(f"# Sweep summary — {meta.get('sweep_name', '?')}")
    lines.append("")
    lines.append(f"- **harness**: {meta.get('harness')}")
    lines.append(f"- **model**: {meta.get('model')}")
    lines.append(f"- **max_samples_per_axis**: {meta.get('max_samples_per_axis')}")
    lines.append(f"- **timeout_per_sample_s**: {meta.get('timeout_per_sample_s')}")
    lines.append(f"- **n_axes (planned)**: {meta.get('n_axes')}")
    lines.append(f"- **n_rows (observed)**: {n_rows}")
    lines.append(f"- **start_iso**: {meta.get('start_iso')}")
    lines.append(f"- **end_iso**: {meta.get('end_iso')}")
    lines.append("")

    lines.append("## Per-axis stats")
    lines.append("")
    lines.append("| Axis | N | Mean score | Success rate | Error rate | Mean wall (s) | Sum cost ($) |")
    lines.append("|------|---|-----------|--------------|-----------|---------------|-------------|")
    for ax in sorted(per_axis.keys()):
        v = per_axis[ax]
        lines.append(
            f"| {ax} | {v['n']} | {v['mean_score']:.3f} | "
            f"{v['success_rate']:.2f} | {v['error_rate']:.2f} | "
            f"{v['mean_wall_s']:.1f} | {v['sum_cost_usd']:.4f} |"
        )
    lines.append("")

    lines.append("## Aggregate /go Pareto point")
    lines.append("")
    lines.append(f"- **cost (mean of per-axis mean_cost)**: ${pareto['x_cost_usd_mean']}")
    lines.append(f"- **cost (total observed across all axes)**: ${pareto['x_cost_usd_total']}")
    lines.append(f"- **score (mean of per-axis mean_score)**: {pareto['y_score']}")
    lines.append(f"- **n_axes**: {pareto['n_axes']}")
    lines.append("")
    lines.append("> Cost figures are **best-effort from codeburn delta**; zero means "
                 "the local codeburn dashboard was not reachable during the run. "
                 "For the headline cost figure, rely on Anthropic billing reconciliation instead.")
    lines.append("")

    lines.append("## Time-horizon estimate (coarse)")
    lines.append("")
    lines.append(f"- **Note**: {horizon['note']}")
    lines.append(f"- **Axes with success_rate >= 0.5**:")
    if horizon["horizon_passing_axes"]:
        for ax, sr in horizon["horizon_passing_axes"]:
            lines.append(f"    - {ax}: {sr:.2f}")
    else:
        lines.append("    - (none)")
    lines.append("")

    lines.append("## Per-axis success-rate bar")
    lines.append("")
    for ax in sorted(per_axis.keys()):
        sr = per_axis[ax]["success_rate"]
        bar = "#" * int(round(sr * 20))
        lines.append(f"- {ax}: {bar:<20} {sr:.2f}")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="analyze a harness-bench sweep directory")
    parser.add_argument("sweep_dir", help="path to results/v1-smoke-<ts>/ directory")
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)
    if not sweep_dir.is_dir():
        print(f"not a directory: {sweep_dir}", file=sys.stderr)
        return 2

    meta_path = sweep_dir / "sweep_meta.json"
    results_path = sweep_dir / "results.jsonl"

    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    rows = load_jsonl(results_path)
    per_axis = per_axis_stats(rows)
    pareto = pareto_point(per_axis)
    horizon = time_horizon_estimate(per_axis)

    summary_json = {
        "meta": meta,
        "per_axis": per_axis,
        "pareto_point": pareto,
        "time_horizon": horizon,
        "n_rows": len(rows),
    }
    (sweep_dir / "summary.json").write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    md = render_summary_md(meta, per_axis, pareto, horizon, len(rows))
    (sweep_dir / "summary.md").write_text(md, encoding="utf-8")

    print(md)
    print(f"\n[analyze] wrote {sweep_dir / 'summary.md'} + summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
