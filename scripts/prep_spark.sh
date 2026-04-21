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
# Status: v0.2 — .venv-claude-code-go wired (inspect-ai + npm-installed
#         `claude` CLI + credentials check). Other harnesses (aider,
#         openhands, cline, continue-dev, goose) wired at best-effort
#         level; verified fully once each adapter lands a smoke-eval.
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
    if [ -d "${venv}" ]; then
        echo "[prep_spark] ${venv} exists, re-validating install"
    else
        echo "[prep_spark] creating ${venv}"
        uv venv "${venv}" --python 3.11
    fi

    # shellcheck disable=SC1091
    source "${venv}/bin/activate"

    case "${h}" in
        claude-code-go)
            # The /go harness driver (harnesses/claude_code_go.py) calls out to
            # the globally installed `claude` CLI via subprocess; the venv itself
            # only needs the Python test deps so ClaudeCodeGoHarness can be
            # imported + the Inspect AI runner can load it. Mirror .venv-base
            # for inspect-ai + datasets + pydantic.
            uv pip install -e ".[dev,otlp]" >/dev/null

            # Install `claude` CLI if absent. Canonical path on Spark is npm
            # (node v22+ preinstalled; cargo/curl are fallbacks). User-local
            # prefix avoids /usr/lib EACCES.
            NPM_PREFIX="${HOME}/.npm-global"
            export PATH="${NPM_PREFIX}/bin:${PATH}"
            if ! command -v claude >/dev/null 2>&1; then
                echo "[prep_spark] installing claude CLI via npm (user-local prefix)"
                mkdir -p "${NPM_PREFIX}"
                npm config set prefix "${NPM_PREFIX}"
                npm install -g @anthropic-ai/claude-code
                # Persist the PATH export so subsequent shells see it.
                if ! grep -q "${NPM_PREFIX}/bin" "${HOME}/.bashrc" 2>/dev/null; then
                    echo "export PATH=${NPM_PREFIX}/bin:\$PATH" >> "${HOME}/.bashrc"
                fi
            fi
            CLAUDE_VERSION="$(claude --version 2>/dev/null || echo 'unknown')"
            echo "[prep_spark] claude CLI: ${CLAUDE_VERSION}"

            # Credentials must be present for headless runs. Do NOT print the
            # file — just check existence + warn if stale (>7 days).
            CREDS_PATH="${HOME}/.claude/.credentials.json"
            if [ ! -f "${CREDS_PATH}" ]; then
                echo "[prep_spark] WARN: ${CREDS_PATH} missing — copy from tablet: scp ~/.claude/.credentials.json dgx-spark:~/.claude/.credentials.json" >&2
            else
                CREDS_AGE_DAYS="$(( ( $(date +%s) - $(stat -c %Y "${CREDS_PATH}") ) / 86400 ))"
                echo "[prep_spark] claude credentials present (age=${CREDS_AGE_DAYS}d)"
                if [ "${CREDS_AGE_DAYS}" -gt 7 ]; then
                    echo "[prep_spark] WARN: creds older than 7 days; refresh if auth fails: scp ~/.claude/.credentials.json dgx-spark:~/.claude/.credentials.json" >&2
                fi
            fi
            ;;
        aider)
            uv pip install aider-chat >/dev/null 2>&1 || true
            ;;
        openhands)
            uv pip install openhands-ai >/dev/null 2>&1 || true
            ;;
        cline|continue-dev|goose)
            # Node/Cargo-installed; leave Python deps matching base for test-runner importability.
            uv pip install -e ".[dev]" >/dev/null 2>&1 || true
            ;;
    esac

    deactivate
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
