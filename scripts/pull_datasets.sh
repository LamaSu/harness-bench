#!/usr/bin/env bash
# pull_datasets.sh — master pull script for harness-bench corpus
# See docs/01-corpus-catalog.md §5 for full per-dataset rationale.
#
# Usage:
#   bash scripts/pull_datasets.sh [strategy]
#
# Strategies:
#   minimal  — HF JSONL + git only, no bulk corpora (~30 GB)
#   fast     — minimal + one-month GH Archive + arXiv metadata (~50 GB) [DEFAULT]
#   full     — fast + S2ORC OA + PMC OA commercial subset + Stack Overflow (~280 GB total)

set -euo pipefail

STRATEGY="${1:-fast}"
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
CORPUS_DIR="${CORPUS_DIR:-./corpus}"

mkdir -p "$CORPUS_DIR"

echo "[pull_datasets] Strategy: $STRATEGY"
echo "[pull_datasets] HF cache: $HF_CACHE"
echo "[pull_datasets] Corpus dir: $CORPUS_DIR"

# ---- 1. HuggingFace datasets (always pulled) ----
pull_hf() {
  local repo="$1" subdir="$2"
  echo "[hf] $repo -> $CORPUS_DIR/$subdir"
  huggingface-cli download "$repo" --repo-type dataset \
    --local-dir "$CORPUS_DIR/$subdir" --local-dir-use-symlinks False
}

# Code/SWE
pull_hf princeton-nlp/SWE-bench_Verified swe_bench_verified
pull_hf ScaleAI/SWE-bench_Pro swe_bench_pro
pull_hf princeton-nlp/SWE-bench_Multimodal swe_bench_mm
pull_hf bigcode/bigcodebench bigcodebench
pull_hf tianyang/repobench_python_v1.1 repobench_py
pull_hf bigcode/commitpackft commitpackft

# Memory / long-context
pull_hf xiaowu0162/longmemeval-cleaned longmemeval
pull_hf RMT-team/babilong babilong
pull_hf xinrongzhang2022/InfiniteBench infinitebench

# Agentic
pull_hf HuggingFaceH4/tau2-bench-data tau2
pull_hf xlangai/ubuntu_osworld_verified_trajs osworld_ubuntu
pull_hf AssistantBench/AssistantBench assistantbench
pull_hf tasksource/planbench planbench
pull_hf gaia-benchmark/GAIA gaia

# Bio
pull_hf bigbio/med_qa medqa
pull_hf qiaojin/PubMedQA pubmedqa
pull_hf jablonkagroup/ChemBench chembench
pull_hf Idavidrein/gpqa gpqa  # WARNING: needs safe-logger, never log raw text
pull_hf TIGER-Lab/MMLU-STEM mmlu_stem

# Finance
pull_hf PatronusAI/financebench financebench
pull_hf ibm-research/finqa finqa
pull_hf MehdiHosseiniMoghadam/ConvFinQA convfinqa

# Legal
pull_hf nguha/legalbench legalbench

# Cybersec
pull_hf facebook/cyberseceval3-visual-prompt-injection cyberseceval3

# Reasoning
pull_hf yale-nlp/FOLIO folio

# Real-trace base (small subsets)
pull_hf allenai/WildChat-1M wildchat
[ "$STRATEGY" = "full" ] && pull_hf sentence-transformers/s2orc s2orc

# ---- 2. git-clone datasets ----
clone_git() {
  local url="$1" subdir="$2"
  echo "[git] $url -> $CORPUS_DIR/$subdir"
  if [ -d "$CORPUS_DIR/$subdir/.git" ]; then
    git -C "$CORPUS_DIR/$subdir" pull --ff-only
  else
    git clone --depth=1 "$url" "$CORPUS_DIR/$subdir"
  fi
}

clone_git https://github.com/JetBrains-Research/lca-baselines lca
clone_git https://github.com/sierra-research/tau-bench tau_bench
clone_git https://github.com/sierra-research/tau2-bench tau2_bench
clone_git https://github.com/xlang-ai/OSWorld osworld
clone_git https://github.com/web-arena-x/webarena webarena
clone_git https://github.com/web-arena-x/visualwebarena visualwebarena
clone_git https://github.com/StonyBrookNLP/appworld appworld
clone_git https://github.com/OpenBMB/ToolBench toolbench
clone_git https://github.com/Aider-AI/polyglot-benchmark aider_polyglot
clone_git https://github.com/NVIDIA/RULER ruler
clone_git https://github.com/snap-research/locomo locomo
clone_git https://github.com/mayubo2333/MMLongBench-Doc mmlongbench_doc
clone_git https://github.com/snap-stanford/biomni biomni
clone_git https://github.com/NYU-LLM-CTF/LLM_CTF_Database nyu_ctf
clone_git https://github.com/openai/SWELancer-Benchmark swe_lancer
clone_git https://github.com/openai/mle-bench mle_bench
clone_git https://github.com/chchenhui/mlrbench mlr_bench
clone_git https://github.com/victorvikram/ConceptARC conceptarc
clone_git https://github.com/freshllms/freshqa freshqa

# ---- 3. Bulk fetchers (only fast/full) ----
if [ "$STRATEGY" != "minimal" ]; then
  echo "[bulk] arXiv metadata (Kaggle)"
  if command -v kaggle >/dev/null 2>&1; then
    kaggle datasets download -d Cornell-University/arxiv \
      -p "$CORPUS_DIR/arxiv_meta" --unzip
  else
    echo "[bulk]   Kaggle CLI missing — skipping arXiv metadata"
  fi

  echo "[bulk] GH Archive (last 7 days)"
  mkdir -p "$CORPUS_DIR/gharchive"
  for d in $(seq 1 7); do
    date_iso=$(date -u -d "$d days ago" +%Y-%m-%d)
    for h in 0 6 12 18; do
      f="${date_iso}-${h}.json.gz"
      if [ ! -s "$CORPUS_DIR/gharchive/$f" ]; then
        wget -q -P "$CORPUS_DIR/gharchive" "https://data.gharchive.org/$f" || true
      fi
    done
  done
fi

# ---- 4. Full only — large bulk ----
if [ "$STRATEGY" = "full" ]; then
  echo "[bulk] Stack Overflow dump (April 2024 IA snapshot, ~80 GB)"
  mkdir -p "$CORPUS_DIR/stackoverflow"
  for f in stackoverflow.com-Posts.7z stackoverflow.com-Comments.7z \
           stackoverflow.com-PostHistory.7z stackoverflow.com-Users.7z \
           stackoverflow.com-Tags.7z; do
    [ ! -s "$CORPUS_DIR/stackoverflow/$f" ] && \
      wget -q -P "$CORPUS_DIR/stackoverflow" "https://archive.org/download/stackexchange/$f"
  done

  echo "[bulk] PubMed Central OA (commercial-use subset, ~110 GB filtered)"
  mkdir -p "$CORPUS_DIR/pmc_oa_commercial"
  wget -m -np -nH --cut-dirs=4 -q -A "*.tar.gz" \
    https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/ \
    -P "$CORPUS_DIR/pmc_oa_commercial"
fi

# ---- 5. Manifest (SHA256 every file in corpus/) ----
echo "[manifest] Generating SHA256 manifest"
find "$CORPUS_DIR" -type f -not -path "*/.git/*" \
  -exec sha256sum {} \; > "$CORPUS_DIR/_cache_manifest.txt" || true

echo "[pull_datasets] Done."
echo "[pull_datasets] Disk usage:"
du -sh "$CORPUS_DIR"
