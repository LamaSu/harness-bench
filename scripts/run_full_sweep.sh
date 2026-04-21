#!/usr/bin/env bash
# run_full_sweep.sh — execute the full agentic-harness-bench v0.2 sweep
#
# Runs 15 axes x 8 harnesses x N ARMs (per ABLATION_MATRIX) at the
# configured per-cell sample count. Designed to run on DGX Spark (119GB
# RAM) with cost-bounded parallelism. Resumable via the runner's
# Inspect-AI .eval cache + harness-bench's per-cell DONE file.
#
# Spec: docs/04-bench-spec.md §5 (Runner) and §6 (Spark Deployment).
# Status: STUB — fill in once individual cell wiring lands.
#
# Usage:
#   scripts/run_full_sweep.sh v0.2-smoke
#   scripts/run_full_sweep.sh v0.2 --resume
#   scripts/run_full_sweep.sh v1.0 --pareto --otlp http://phoenix:6006/v1/traces
set -euo pipefail
IFS=$'\n\t'

VERSION="${1:-v0.2-smoke}"
shift || true

RESULTS_ROOT="${HARNESS_BENCH_RESULTS:-./results/${VERSION}}"
mkdir -p "${RESULTS_ROOT}"

# All 15 axes (defined in tasks/__init__.py:TASK_REGISTRY).
AXES=(M1 M2 M3 M4 M5 FM1 FM2 FM3 FM4 FM5 BS1 BS2 BS3 BS4 BS5)

# Open-source harnesses (ablation-capable).
HARNESSES_OPEN=(claude-code-go aider openhands cline continue-dev goose)

# Closed harnesses (headline-only).
HARNESSES_CLOSED=(cursor-blackbox devin-blackbox)

# Per-cell sample counts (smoke vs full).
case "${VERSION}" in
    v0.2-smoke) SAMPLES_PER_CELL_OPEN=10; SAMPLES_PER_CELL_CLOSED=5 ;;
    v0.2)       SAMPLES_PER_CELL_OPEN=30; SAMPLES_PER_CELL_CLOSED=20 ;;
    v1.0)       SAMPLES_PER_CELL_OPEN=100; SAMPLES_PER_CELL_CLOSED=50 ;;
    *)          echo "unknown version: ${VERSION}" >&2; exit 2 ;;
esac

echo "[run_full_sweep] version=${VERSION} results=${RESULTS_ROOT}"
echo "[run_full_sweep] axes=${#AXES[@]} open_harnesses=${#HARNESSES_OPEN[@]} closed=${#HARNESSES_CLOSED[@]}"
echo "[run_full_sweep] samples/cell open=${SAMPLES_PER_CELL_OPEN} closed=${SAMPLES_PER_CELL_CLOSED}"

# TODO: wire to the actual Inspect-AI runner (`inspect eval` + harness-bench
# CLI). For now this script is documentation of the intended shape.
#
# Pseudocode:
# for axis in "${AXES[@]}"; do
#     for harness in "${HARNESSES_OPEN[@]}"; do
#         for arm in $(harness-bench arms --harness "${harness}"); do
#             cell="${RESULTS_ROOT}/${axis}/${harness}/${arm}"
#             [ -f "${cell}/DONE" ] && continue
#             mkdir -p "${cell}"
#             inspect eval "tasks.${axis_module}:${axis_fn}" \
#                 --solver harness_bench.solver \
#                 --solver-args "harness=${harness},arm=${arm}" \
#                 --scorer pass_at_1,time_horizon,pareto_collector \
#                 --limit "${SAMPLES_PER_CELL_OPEN}" \
#                 --log-dir "${cell}" \
#                 "$@"
#             touch "${cell}/DONE"
#         done
#     done
#     for harness in "${HARNESSES_CLOSED[@]}"; do
#         cell="${RESULTS_ROOT}/${axis}/${harness}/headline"
#         [ -f "${cell}/DONE" ] && continue
#         mkdir -p "${cell}"
#         inspect eval "tasks.${axis_module}:${axis_fn}" \
#             --solver harness_bench.solver \
#             --solver-args "harness=${harness}" \
#             --scorer pass_at_1,time_horizon,pareto_collector \
#             --limit "${SAMPLES_PER_CELL_CLOSED}" \
#             --log-dir "${cell}" \
#             "$@"
#         touch "${cell}/DONE"
#     done
# done

echo "[run_full_sweep] STUB — runner wiring pending; see docs/04-bench-spec.md §5"
exit 0
