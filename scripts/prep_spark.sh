#!/usr/bin/env bash
# prep_spark.sh — provision DGX Spark for harness-bench sweeps
#
# Idempotent. Run on the Spark node (192.168.108.72) before any
# `run_full_sweep.sh` invocation. Sets up:
#   - Per-harness venvs (uv-managed) so adapter dep conflicts don't collide
#   - Inspect AI + harness-bench package
#   - Corpus pull (scripts/pull_datasets.sh)
#   - Phoenix (Arize) for OTLP collection (optional, --otlp flag)
#   - Disk + RAM sanity checks
#
# Spec: docs/04-bench-spec.md §6 (Spark Deployment).
# Status: STUB — fill in once individual harness install recipes land.
set -euo pipefail
IFS=$'\n\t'

WANT_OTLP=false
WANT_BLACKBOX=false
for arg in "$@"; do
    case "${arg}" in
        --otlp)     WANT_OTLP=true ;;
        --blackbox) WANT_BLACKBOX=true ;;
        *)          echo "unknown arg: ${arg}" >&2; exit 2 ;;
    esac
done

echo "[prep_spark] host=$(hostname) user=$(whoami) cwd=$(pwd)"

# ---- sanity ---------------------------------------------------------
RAM_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo "?")
DISK_GB=$(df -BG --output=avail . | tail -n1 | tr -dc '0-9')
echo "[prep_spark] RAM=${RAM_GB}GB Disk(free)=${DISK_GB}GB"
if [[ "${RAM_GB}" != "?" && "${RAM_GB}" -lt 64 ]]; then
    echo "[prep_spark] WARN: <64GB RAM; Spark target is 119GB" >&2
fi
if [[ "${DISK_GB}" -lt 100 ]]; then
    echo "[prep_spark] WARN: <100GB disk free; corpus is ~280GB" >&2
fi

# ---- shared base venv ----------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    echo "[prep_spark] installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
fi

uv venv .venv-base --python 3.11
# shellcheck disable=SC1091
source .venv-base/bin/activate
uv pip install -e ".[dev,otlp]"
deactivate

# ---- per-harness venvs ---------------------------------------------
HARNESSES_OPEN=(claude-code-go aider openhands cline continue-dev goose)
for h in "${HARNESSES_OPEN[@]}"; do
    venv=".venv-${h}"
    [ -d "${venv}" ] && { echo "[prep_spark] ${venv} exists, skipping"; continue; }
    echo "[prep_spark] creating ${venv}"
    uv venv "${venv}" --python 3.11
    # TODO: per-harness install commands. e.g.:
    # source "${venv}/bin/activate"
    # case "${h}" in
    #     aider)        uv pip install aider-chat ;;
    #     openhands)    uv pip install openhands-ai ;;
    #     cline)        npm install -g @cline/cli ;;
    #     continue-dev) npm install -g @continuedev/cli ;;
    #     goose)        cargo install goose-cli ;;
    #     claude-code-go) go install github.com/anthropics/harness@latest ;;
    # esac
    # deactivate
done

# ---- blackbox harness creds ----------------------------------------
if [[ "${WANT_BLACKBOX}" == "true" ]]; then
    echo "[prep_spark] verifying blackbox creds (DEVIN_API_KEY, REPLIT_API_KEY)..."
    : "${DEVIN_API_KEY:?DEVIN_API_KEY not set}"
    : "${REPLIT_API_KEY:?REPLIT_API_KEY not set}"
fi

# ---- corpus --------------------------------------------------------
if [ ! -d corpus ]; then
    echo "[prep_spark] pulling datasets via scripts/pull_datasets.sh"
    bash scripts/pull_datasets.sh
fi

# ---- OTLP collector (Phoenix) --------------------------------------
if [[ "${WANT_OTLP}" == "true" ]]; then
    if ! docker ps --filter "name=phoenix" --format "{{.Names}}" | grep -q phoenix; then
        echo "[prep_spark] starting Phoenix on :6006"
        docker run -d --name phoenix \
            -p 6006:6006 -p 4317:4317 \
            arizephoenix/phoenix:latest
    else
        echo "[prep_spark] Phoenix already running"
    fi
fi

echo "[prep_spark] done. Next: scripts/run_full_sweep.sh v0.2-smoke"
