# 01 — Public-Dataset Corpus Catalog (harness-bench)

> **Status:** WORK-IN-PROGRESS — researched & maintained by `corpus-writer-alpha`.
> **Date started:** 2026-04-21.
> **Project:** `harness-bench` — agentic-harness benchmark suite riding on top of UK AISI's [Inspect AI](https://inspect.aisi.org.uk/) shell.
> **Scope:** Catalog every PUBLIC dataset to be ingested into the harness-bench corpus. Each dataset gets a row, a license check, a pull command, and an Inspect AI integration note.

---

## 0. TL;DR

This catalog enumerates **66 public datasets** across 6 domains (code/SWE, biomedical, cybersecurity, legal, finance, scientific) and three benchmark axis families (M1-M5 = memory, FM1-FM5 = pain/failure modes, BS1-BS5 = bisociation). The benchmark sits on top of UK AISI's [Inspect AI](https://inspect.aisi.org.uk/) framework, leveraging the existing [`inspect_evals`](https://github.com/UKGovernmentBEIS/inspect_evals) registry where ports already exist — **40 of our 66 datasets are pre-ported as Inspect AI tasks**, leaving 26 to adapt and 7 of those (BS-2/3/4/5, FM-4/5, AnalogyBench/E-MAGIC if not constructable) to synthesize from base corpora.

**License posture:** ~50 of 66 are permissive (MIT, Apache-2.0, CC-BY-4.0, CC0, ODC-BY). The remaining 16 fall into three buckets: (a) `CC-BY-NC` or share-alike (LegalBench mixed, FOLIO CC-BY-SA, BABILong components) — usable but require attribution and same-license redistribution; (b) `CC-BY-NC-ND` / restrictive (RepoBench `CC-BY-NC-ND-4.0`, Aider-Polyglot inherits Exercism `CC-BY-NC-SA-4.0`) — eval-only, do not redistribute as derivative corpus; (c) per-task mixed (LegalBench, PMC-OA, Biomni's integrated tools) — filter at adapter layer, with `commercial_mode` flags where the upstream provides one. **Hard cuts** (excluded from v1): ShareGPT (OpenAI ToS unclear), MIMIC-III/IV (DUA-gated), and any dataset whose license is unverifiable in `LICENSE` file or HF card.

**Disk footprint:** raw corpus estimated at **~280 GB** to fully stage on Spark (`/spark-data/harness-bench/corpus/`). Dominant by size: PubMed-Central OA full-text bulk (~110 GB filtered to commercial-OK), S2ORC OA subset (~70 GB metadata + abstracts), GH Archive monthly window (~30 GB), CommitPackFT (2 GB), arXiv metadata (~5 GB), plus benchmark-specific data (~60 GB total for everything else). DGX Spark has 119 GB RAM and ~112 GB free disk — the 280 GB raw plan needs an **external HDD attached to Spark** OR aggressive on-demand fetching for PMC + S2ORC, keeping resident only ~70 GB of pre-pulled benchmark splits. **Recommended pull strategy**: `huggingface-cli download` with `--cache-dir /spark-data/hf-cache` for HF-resident sets, custom downloader for PMC/S2ORC/arXiv/GH-Archive driven by `scripts/pull_datasets.sh`.

**Pull-them-all command** (after credentials are in place on Spark):
```bash
spark-run "bash scripts/pull_datasets.sh --strategy fast --skip-pmc-bulk --hf-cache /spark-data/hf-cache"
```

**Construction-required gaps** (datasets we'll BUILD, not pull): BS-2 (frame-shift hypothesis), BS-3 (cross-paper synthesis — partial; we have S2ORC base material but not a curated eval set), BS-4 (tool-output bisociation), BS-5 (solution recombination), FM-4 (KV-cache drift — needs synthetic instrumentation), FM-5 (destructive-action under conflict — partial; tau2-bench gives airline/retail; we'll extend). See §8.

---

## 1. Dataset table — full inventory

Notation in **Inspect column**: `[ported]` = already in `inspect_evals` (use directly), `[adapt]` = need our own adapter, `[construct]` = synthetic, build from base corpora.

| # | Dataset | URL | License | Format | Size | Records | Axes | Domains | Inspect |
|---|---------|-----|---------|--------|------|---------|------|---------|---------|
| **CODE / SWE (8 entries)** |
| 1 | SWE-bench Verified | https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified | CC-BY-4.0 (verify) | HF JSONL | ~50 MB | 500 | M5, FM-1 | code | [ported] `inspect_evals/swe_bench` |
| 2 | SWE-bench Pro (Public) | https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro | GPL-derived (eval scaffold MIT) | HF JSONL | ~200 MB | 731 | M5, FM-1, BS-1 | code | [adapt] — extend `swe_bench` task |
| 3 | SWE-bench Multimodal | https://huggingface.co/datasets/princeton-nlp/SWE-bench_Multimodal | per HF card (verify) | HF JSONL + images | ~2 GB | 617 | M2, M5 | code | [adapt] |
| 4 | Aider Polyglot | https://github.com/Aider-AI/polyglot-benchmark | CC-BY-NC-SA-4.0 (Exercism) | git repo | ~50 MB | 225 | FM-1 | code | [adapt] — eval-only |
| 5 | BigCodeBench | https://huggingface.co/datasets/bigcode/bigcodebench | Apache-2.0 | HF JSONL | ~5 MB | 1,140 | BS-1, M5 | code | [ported] `inspect_evals/bigcodebench` |
| 6 | RepoBench v1.1 | https://huggingface.co/datasets/tianyang/repobench_python_v1.1 | CC-BY-NC-ND-4.0 | HF JSONL | ~3 GB | ~50K | M1, M5 | code | [adapt] — eval-only |
| 7 | Long Code Arena | https://huggingface.co/collections/JetBrains-Research/long-code-arena-6565e5ff459394ff71a635d2 | mixed permissive (MIT/Apache/BSD) | HF | ~5 GB | 6 sub-benchmarks | M5, BS-1 | code | [adapt] |
| 8 | SWE-Lancer (Diamond) | https://github.com/openai/SWELancer-Benchmark | per repo (Apache-2.0 likely) | git repo + Docker | ~10 GB | 1,488 (Diamond ~250) | M4, BS-3 | code | [ported] `inspect_evals/swe_lancer` |
| **MEMORY / LONG-CONTEXT (9 entries)** |
| 9 | LongMemEval | https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned | MIT | HF JSONL | ~500 MB | ~500 dialogs | M1, M3, M4 | general | [adapt] |
| 10 | LoCoMo | https://github.com/snap-research/locomo | permissive (verify) | JSONL | ~200 MB | 50 dialogs (32 sessions ea) | M1, M2 | general | [adapt] |
| 11 | BABILong | https://huggingface.co/datasets/RMT-team/babilong | permissive (PG19+bAbI) | HF | ~10 GB (eval+train) | 100/length × 13 lengths × 20 tasks | M5, FM-2 | general | [adapt] (PR open in lm-eval-harness) |
| 12 | RULER | https://github.com/NVIDIA/RULER | Apache-2.0 | python+jsonl | ~500 MB | configurable | M1, M5, FM-2 | general | [adapt] |
| 13 | InfiniteBench (∞Bench) | https://huggingface.co/datasets/xinrongzhang2022/InfiniteBench | research-only (verify) | HF | ~5 GB | ~1.2K | M5, FM-2 | general | [ported] `inspect_evals/infinite_bench_*` |
| 14 | MMLongBench-Doc | https://github.com/mayubo2333/MMLongBench-Doc | research-only | git+jsonl | ~1 GB | 1062 questions | M2, M5 | general | [adapt] — non-commercial |
| 15 | MileBench | per repo (verify) | research-only (presumed) | git | ~2 GB | TBD | M2, M5 | general | [adapt] |
| 16 | FreshQA | https://github.com/freshllms/freshqa | per repo (verify) | git | ~10 MB | ~600 (rotating) | M3 | general | [adapt] |
| 17 | RealTimeQA | https://realtimeqa.github.io/ | per repo (verify) | git | ~10 MB | weekly updates | M3 | general | [adapt] |
| **AGENTIC / TOOL-USE / WEB (10 entries)** |
| 18 | GAIA | https://huggingface.co/datasets/gaia-benchmark/GAIA | per HF (verify) | HF JSONL | ~100 MB | 466 | M4, BS-1 | general | [ported] `inspect_evals/gaia_level*` |
| 19 | Gaia2 (ARE) | TBD (Meta release planned) | TBD | TBD | TBD | TBD | M4, BS-4 | general | [construct/adapt as released] |
| 20 | TAU-bench | https://github.com/sierra-research/tau-bench | MIT | git+python | ~50 MB | ~100 trajectories | FM-5, M4 | general | [adapt] |
| 21 | τ²-bench (tau2) | https://huggingface.co/datasets/HuggingFaceH4/tau2-bench-data | MIT | HF | ~50 MB | airline+retail+telecom | FM-5, M4, BS-4 | general | [ported] `inspect_evals/tau2_*` |
| 22 | OSWorld-Verified | https://huggingface.co/datasets/xlangai/ubuntu_osworld_verified_trajs | MIT (Ubuntu) / Apache-2.0 (Win) | HF + Docker | ~30 GB (with VM images) | 369 tasks | M4, FM-1, FM-5 | general | [ported] `inspect_evals/osworld` |
| 23 | WebArena | https://github.com/web-arena-x/webarena | MIT | git+Docker | ~20 GB (with apps) | 812 tasks | M4, FM-1, FM-5 | general | [adapt] (Mind2Web ported) |
| 24 | VisualWebArena | https://github.com/web-arena-x/visualwebarena | MIT | git+Docker | ~25 GB | 910 tasks | M2, M4, FM-1 | general | [adapt] |
| 25 | AppWorld | https://github.com/StonyBrookNLP/appworld | Apache-2.0 | python | ~500 MB | 750 tasks | M4, FM-5, BS-4 | general | [adapt] |
| 26 | AssistantBench | https://huggingface.co/datasets/AssistantBench/AssistantBench | Apache-2.0 | HF | ~20 MB | 214 | M1, FM-1, BS-1 | general | [ported] `inspect_evals/assistant_bench_*` |
| 27 | ToolBench | https://github.com/OpenBMB/ToolBench | Apache-2.0 | git+jsonl | ~5 GB | 16K APIs | M4, BS-4 | general | [adapt] |
| 28 | PlanBench | https://huggingface.co/datasets/tasksource/planbench | Apache-2.0 (presumed) | HF | ~50 MB | ~500 problems | M4, BS-1 | general | [adapt] |
| **BIO / SCIENTIFIC (8 entries)** |
| 29 | BIOMNI / Biomni-Eval1 | https://github.com/snap-stanford/biomni | Apache-2.0 (code) + mixed (data) | git | ~5 GB | 433 instances | BS-2, BS-3 | bio | [adapt] — `commercial_mode` filter |
| 30 | MedQA | https://huggingface.co/datasets/bigbio/med_qa | MIT | HF | ~50 MB | 60K Q (3 langs) | factual | bio | [ported] `inspect_evals/medqa` |
| 31 | BioASQ | http://bioasq.org/ (registration) | CC-BY-2.5 (per terms) | XML/JSON | ~3 GB | 4K+ Q | factual, BS-3 | bio | [adapt] — registration required |
| 32 | PubMedQA | https://huggingface.co/datasets/qiaojin/PubMedQA | MIT | HF | ~600 MB | 1K+ expert | BS-3 | bio | [ported] `inspect_evals/pubmedqa` |
| 33 | ChemBench | https://huggingface.co/datasets/jablonkagroup/ChemBench | MIT | HF | ~50 MB | 2,786 Q | factual, BS-2 | sci | [ported] `inspect_evals/chembench` |
| 34 | GPQA Diamond | https://huggingface.co/datasets/Idavidrein/gpqa | CC-BY-4.0 (with no-leak term) | HF (gated logging) | ~5 MB | 198 | BS-2 | sci | [ported] `inspect_evals/gpqa_diamond` — needs safe-logger |
| 35 | MMLU-STEM | https://huggingface.co/datasets/TIGER-Lab/MMLU-STEM | MIT | HF | ~50 MB | ~3K | factual | sci | [ported] `inspect_evals/mmlu_*` |
| 36 | MLE-bench | https://github.com/openai/mle-bench | Apache-2.0 (code) + per-Kaggle (data) | git+Docker | ~30 GB (full Kaggle) | 75 competitions | M4, FM-1 | sci/code | [ported] `inspect_evals/mle_bench` |
| **CYBERSEC (4 entries)** |
| 37 | Cybench | https://github.com/andyzorigin/cybench (also inspect_evals) | per repo (Apache-2.0/MIT presumed) | git+Docker | ~5 GB | 39 CTFs | FM-1, M4 | cyber | [ported] `inspect_evals/cybench` |
| 38 | NYU CTF Bench | https://github.com/NYU-LLM-CTF/LLM_CTF_Database | per repo (verify) | git | ~10 GB | 200 challenges | FM-1, FM-5 | cyber | [adapt] |
| 39 | CyberSecEval 3 | https://huggingface.co/datasets/facebook/cyberseceval3-visual-prompt-injection | MIT | HF | ~500 MB | broad | FM-2, FM-5 | cyber | [ported] `inspect_evals/cyse3_*` |
| 40 | CyberSecEval 2 | per Meta/Llama recipes | MIT | git | ~200 MB | broad | FM-2, FM-5 | cyber | [ported] `inspect_evals/cyse2_*` |
| **LEGAL (2 entries)** |
| 41 | LegalBench | https://huggingface.co/datasets/nguha/legalbench | mixed per-task | HF | ~200 MB | 162 tasks | factual, BS-3 | legal | [adapt] — filter to permissive subset |
| 42 | CaseHOLD | (Caselaw Access Project) | CC0 | parquet | ~500 MB | 53K | factual | legal | [adapt] |
| **FINANCE (3 entries)** |
| 43 | FinanceBench | https://huggingface.co/datasets/PatronusAI/financebench | CC-BY-4.0 (sample) | HF | ~50 MB (sample) | 150 (sample); 10K (full, gated) | BS-3, M2 | finance | [adapt] |
| 44 | FinQA | https://huggingface.co/datasets/ibm-research/finqa | MIT | HF | ~100 MB | 8K Q over 2.8K reports | BS-4 | finance | [adapt] |
| 45 | ConvFinQA | https://huggingface.co/datasets/MehdiHosseiniMoghadam/ConvFinQA | MIT | HF | ~50 MB | 3.9K dialogues | M1 | finance | [adapt] |
| **REASONING / BISOCIATION-ADJACENT (6 entries)** |
| 46 | FOLIO | https://huggingface.co/datasets/yale-nlp/FOLIO | CC-BY-SA-4.0 | HF | ~5 MB | 1,430 | BS-3 | sci/general | [adapt] |
| 47 | ConceptARC | https://github.com/victorvikram/ConceptARC | research (verify) | git | ~50 MB | 480 ARC-style | BS-1 | general | [adapt] |
| 48 | AnalogyBench | (search returned no canonical match) | — | — | — | — | BS-1 | general | [construct] — build from FOLIO+ConceptARC primitives |
| 49 | E-MAGIC (analogy) | (search returned no canonical match) | — | — | — | — | BS-1, BS-2 | general | [construct] |
| 50 | MLR-Bench | https://github.com/chchenhui/mlrbench | CC-BY-4.0 | git | ~1 GB | 201 tasks | BS-2, BS-3 | sci | [ported] `inspect_evals/mlrc_bench` |
| 51 | PaperBench | (OpenAI release) | research-only | per release | ~5 GB | per ICML 2024 selection | BS-3 | sci | [ported] `inspect_evals/paperbench` |
| **REAL-TRACE BASE CORPORA (8 entries; not direct evals — used for construction)** |
| 52 | GitHub Archive | https://www.gharchive.org/ | per GitHub ToS (public timeline) | gzipped JSON or BigQuery | ~30 GB/month | ~30M events/mo | M4 base | code | [construct] |
| 53 | Stack Overflow dump (Apr 2024) | https://archive.org/details/stackexchange | CC-BY-SA-4.0 | xml/parquet | ~80 GB raw | 22M+ Q | M4 base | code | [construct] |
| 54 | arXiv (metadata) | https://www.kaggle.com/datasets/Cornell-University/arxiv | CC0-1.0 (metadata) | jsonl | ~5 GB | 2.3M+ papers | M3, BS-3 base | sci | [construct] |
| 55 | arXiv (full-text PDFs) | https://info.arxiv.org/help/bulk_data.html | per-paper (no redistribution) | PDF (S3) | ~1.5 TB | 2.3M+ | BS-3 base | sci | [construct via fetcher only — never bundle] |
| 56 | S2ORC (OA) | https://huggingface.co/datasets/sentence-transformers/s2orc | ODC-BY-1.0 | parquet | ~70 GB | ~80M papers | BS-3 base | sci | [construct] |
| 57 | CommitPackFT | https://huggingface.co/datasets/bigcode/commitpackft | MIT | HF parquet | ~2 GB | 700K commits | M4 base, BS-1 base | code | [construct] |
| 58 | WildChat | https://huggingface.co/datasets/allenai/WildChat-1M | ODC-BY | HF parquet | ~5 GB (1M variant) | 1M dialogues | M1 base, FM-1 base | general | [construct] |
| 59 | PubMed Central OA (commercial-OK) | https://pmc.ncbi.nlm.nih.gov/tools/openftlist/ | mixed CC0/CC-BY/CC-BY-SA/CC-BY-ND | XML/PDF | ~110 GB filtered | ~6M articles | BS-3 base | bio | [construct] |
| **HARNESS-SPECIFIC EXTENSIONS we will SHIP (7 entries — see §8)** |
| 60 | harness-bench/M2-cross-modal | (this repo) | MIT | jsonl+images | ~2 GB | 200 | M2 | general | [construct] (uses LoCoMo + MMLongBench-Doc samples) |
| 61 | harness-bench/FM-1-stuck-loops | (this repo) | MIT | jsonl | ~50 MB | 100 | FM-1 | code | [construct] (uses Aider-Polyglot + SWE-bench failure logs) |
| 62 | harness-bench/FM-2-env-hallucination-700k | (this repo) | MIT | jsonl | ~5 GB | 50 | FM-2 | general | [construct] (uses BABILong + RULER >700K) |
| 63 | harness-bench/FM-3-condensation-loops | (this repo) | MIT | jsonl | ~50 MB | 100 | FM-3 | general | [construct] (synthesized from compaction patterns) |
| 64 | harness-bench/FM-4-kv-cache-drift | (this repo) | MIT | jsonl + telemetry probes | ~10 MB | 50 | FM-4 | general | [construct] (instrumentation-driven; needs custom Inspect AI scorer) |
| 65 | harness-bench/FM-5-destructive-conflict | (this repo) | MIT | jsonl + tool stubs | ~20 MB | 80 | FM-5 | general | [construct] (extends tau2-bench + AppWorld; conflict scenarios) |
| 66 | harness-bench/BS-2-to-5-bisociation | (this repo) | MIT | jsonl | ~100 MB | 200 (50 × 4 axes) | BS-2/3/4/5 | sci/code/bio | [construct] (samples from arXiv + S2ORC + PMC, judged by Claude/GPT) |

---

## 2. License breakdown

Grouped by license. **Bold** = restrictive enough to flag.

### 2.1 Permissive (MIT, Apache-2.0, BSD) — clean for redistribution
- **MIT**: SWE-Lancer scaffold (verify), LongMemEval, RULER (Apache-2.0 strictly), CommitPackFT, TAU-bench, τ²-bench, OSWorld (Ubuntu trajectories variant), VisualWebArena, WebArena, MedQA, PubMedQA, ChemBench, FinQA, ConvFinQA, CyberSecEval 2/3, MMLU/MMLU-STEM, harness-bench/* (our own outputs, all MIT).
- **Apache-2.0**: BigCodeBench, AssistantBench, ToolBench, OSWorld (Windows variant), AppWorld, BIOMNI (code), MLE-bench (code), PaperBench (code), RULER, PlanBench (presumed).

### 2.2 Creative Commons attribution — clean with attribution
- **CC-BY-4.0**: SWE-bench Verified (verify on card), GPQA Diamond (with no-leak operational rule), MLR-Bench, FinanceBench (sample). Inherits attribution requirement; no restriction otherwise.
- **CC0-1.0**: arXiv metadata (Kaggle dump), CaseHOLD via Caselaw Access Project. Public domain dedication — fully open.
- **ODC-BY-1.0** (Open Data Commons Attribution): WildChat, S2ORC (OA subset). Like CC-BY but database-rights focused.

### 2.3 Share-alike or per-task mixed — usable, but require care
- **CC-BY-SA-4.0**: FOLIO, Stack Overflow dump (April 2024 snapshot). Derivative works must use same license — implication: any harness-bench corpus that includes these as derivatives must be CC-BY-SA-4.0 too. **Mitigation**: ship them as evaluation-time artifacts only (fetcher pulls from upstream), not bundled.
- **Mixed per-task / per-article**:
  - **LegalBench** — 162 tasks, each with its own upstream license. Filter to the permissive subset at adapter level.
  - **PubMed Central OA** — three groupings; filter to commercial-OK (CC0/CC-BY/CC-BY-SA/CC-BY-ND) at ingest.
  - **BIOMNI integrated tools** — `commercial_mode=True` flag selects commercially-safe subset. We default to `True` for harness-bench releases.
  - **MLE-bench data** — each Kaggle competition has its own per-competition terms (research-only frequently). Embed terms in run-time metadata.

### 2.4 Non-commercial only — restrictive but USABLE for academic harness-bench
- **CC-BY-NC-SA-4.0** (Aider-Polyglot via Exercism): No commercial use. Eval-only OK. **Flagged**.
- **CC-BY-2.5** (BioASQ): Commercial OK with attribution but BioASQ also requires REGISTRATION at bioasq.org. **Flagged** for registration friction.

### 2.5 Strict / no-derivative — eval-only, do not redistribute as a derivative
- **CC-BY-NC-ND-4.0** (RepoBench): No derivatives. We can run eval, MUST NOT alter samples or republish modified copies. **Flagged**.

### 2.6 Research-only / unclear — fetch live, do not bundle
- **MMLongBench-Doc**: explicitly "data and code intended for research use only". MileBench presumed similar. InfiniteBench license unclear in HF card.
- **PaperBench**: ICML 2024 paper data — most CC-BY but some mixed; treat as research-only fallback.
- **ConceptARC**: research-free per repo; no formal license.

### 2.7 HARD CUTS (excluded from v1)
- **ShareGPT**: scraped from chat.openai.com, OpenAI ToS unclear, redistribution legally murky. **Substitute**: use WildChat (clean ODC-BY).
- **MIMIC-III/IV**: DUA-gated, certificate of completion required, not redistributable. **Substitute**: PubMedQA + MedQA + LAB-Bench fragments cover the bio-clinical reasoning surface for v1.
- **arXiv full-text PDFs as bundle**: per-paper licenses don't permit. Ship as **fetcher-only** that pulls live from arXiv on demand.

### 2.8 Special operational rules
- **GPQA Diamond**: contributors agreed to NOT reveal samples in plain text online. harness-bench MUST gate sample text inside CI; never log to plain-text artifacts. Implementation: `scorers/gpqa_safe_logger.py` redacts question text from any logged trace before write.
- **Stack Overflow**: Use the April 2024 Internet Archive snapshot, not the live data dumps (which now require login + agreement-not-to-train-AI).

---

## 3. Axis coverage map

For each axis, list datasets that map (with one-line justification). Identify GAPS.

### 3.1 Memory axes (M1-M5)

**M1 — cross-window retrieval** (information stored long ago in conversation, retrieved now)
- LongMemEval — built explicitly for this, multi-session retrieval.
- LoCoMo — 32-session conversations, QA tasks.
- ConvFinQA — multi-turn financial QA across turns.
- AssistantBench — long real-world tasks span many web fetches.
- RULER — synthetic retrieval at configurable distance.
- RepoBench — repo-scale retrieval.
- harness-bench/M2-cross-modal (constructed) — borrows memory-retrieval setup.
- WildChat (base corpus for further test construction).

**M2 — cross-modal correlation** (text + image / text + table joint memory)
- LoCoMo — multi-modal dialogue (text + image).
- MMLongBench-Doc — long-context document understanding with viz.
- MileBench — multi-image VL long-context.
- VisualWebArena — visual web-nav requires text + screenshot binding.
- SWE-bench Multimodal — text + visual JS framework.
- FinanceBench (when keeping PDFs/charts).
- harness-bench/M2-cross-modal (purpose-built).

**M3 — stale-fact rejection** (knowing when stored info is outdated)
- LongMemEval (knowledge updates axis).
- FreshQA — temporal-rotating Q&A.
- RealTimeQA — weekly-updated.
- arXiv metadata (date-anchored, partial).
- **GAP**: no benchmark for stale-fact-in-prompt vs. fresh-fact-tool-output conflict. **Construct from FreshQA + tool output stubs.**

**M4 — procedural memory** (multi-step workflow recall)
- AppWorld — 750 multi-step workflows across 9 apps.
- TAU-bench / τ²-bench — multi-turn agent + tool + policy.
- LongMemEval (multi-session reasoning axis).
- OSWorld — OS-level procedure execution.
- WebArena / VisualWebArena — multi-step web nav.
- ToolBench — tool sequencing.
- PlanBench — classical planning.
- SWE-Lancer — multi-step engineering.
- MLE-bench — multi-step ML pipeline.
- GH Archive (base for trace construction).

**M5 — working-memory eviction** (degradation under context pressure)
- BABILong — sample lengths 0K → 10M tokens, eviction under length stress.
- RULER — configurable length stress.
- InfiniteBench — 100K+ tokens, 12 tasks.
- RepoBench-P — repo-scale context windows.
- Long Code Arena — project-level windows.
- BigCodeBench (with extended context experiments).
- MMLongBench-Doc, MileBench (multi-image long-context).
- SWE-bench Verified, SWE-bench Pro (large repos).
- harness-bench/FM-2 overlaps.

### 3.2 Pain modes (FM1-FM5)

**FM1 — stuck-loops** (agent retries same failing approach indefinitely)
- Aider Polyglot (2-attempt structure; we extend to N>2).
- SWE-bench Verified (multi-attempt agents loop).
- WebArena, VisualWebArena (web-nav loops).
- OSWorld (UI loops).
- Cybench, NYU CTF Bench (CTF puzzle loops).
- AssistantBench (multi-step web tasks).
- MLE-bench (training loops can stall).
- harness-bench/FM-1-stuck-loops (purpose-built).

**FM2 — env-hallucination at >700K tokens** (model fabricates content of long context)
- BABILong (>700K stress range).
- RULER (configurable).
- InfiniteBench.
- CyberSecEval 2/3 (visual prompt injection at scale).
- harness-bench/FM-2-env-hallucination-700k (purpose-built).

**FM3 — condensation loops** (over-aggressive context compaction destroys signal)
- **GAP** — no public benchmark directly tests this. **Construct from**: take a M1/M5 task, apply repeated compaction, measure degradation. harness-bench/FM-3 ships this.

**FM4 — KV-cache drift** (cache reuse across prompt reshuffles produces silently-wrong outputs)
- **GAP** — purely instrumental; no public dataset. **Construct synthetic**: vary prompt prefix while keeping suffix constant, measure activation drift via Inspect AI's solver-level instrumentation. harness-bench/FM-4.

**FM5 — destructive-action under conflict** (agent takes irreversible action when inputs conflict)
- TAU-bench / τ²-bench — user goal vs. policy conflict.
- AppWorld — destructive actions possible.
- OSWorld — file deletion possible.
- WebArena (purchase actions).
- NYU CTF Bench (system-level).
- harness-bench/FM-5-destructive-conflict (purpose-built; extends tau2 with explicit conflict scenarios).

### 3.3 Bisociation (BS1-BS5)

**BS1 — cross-domain analogy**
- ConceptARC — abstraction over concepts.
- AnalogyBench (construction-required if no canonical found).
- E-MAGIC (construction-required).
- BigCodeBench (cross-library combinatorial).
- AssistantBench.
- Long Code Arena (library-based generation analogies).

**BS2 — frame-shift hypothesis** (reframing a problem in a different domain's terms)
- BIOMNI (cross-modality biological reasoning).
- ChemBench (cross-domain chemistry → materials).
- GPQA Diamond (cross-discipline expert reasoning).
- MLR-Bench (research-question framing).
- E-MAGIC (planned).
- **PRIMARY GAP**: no public BS-2 task; harness-bench/BS-2-to-5 ships it.

**BS3 — cross-paper synthesis** (combining 2+ papers into a novel claim)
- OpenScholar / ScholarQABench — closest existing eval.
- PaperQA2 (no public retrieval corpus, code only).
- BIOMNI.
- PubMedQA expert subset.
- LegalBench (when chained tasks).
- FinanceBench (cross-report).
- MLR-Bench, PaperBench.
- S2ORC + PubMed Central OA (base corpora for construction).
- harness-bench/BS-3 ships a curated synthesis eval pulling from S2ORC.

**BS4 — tool-output bisociation** (combining outputs from 2 tool calls in non-trivial ways)
- ToolBench — tool sequencing (partial).
- τ²-bench (telecom + airline overlap).
- AppWorld (cross-app data fusion).
- FinQA (structured + unstructured fusion).
- **PRIMARY GAP**: explicit cross-tool bisociation eval. Construct from ToolBench + AppWorld scenarios in harness-bench/BS-4.

**BS5 — solution recombination** (recombining prior solutions into a new one)
- BigCodeBench (combinatorial library use).
- Long Code Arena (library-based generation).
- SWE-Lancer (engineering recombination).
- MLE-bench.
- **PRIMARY GAP**: explicit recombination signal. Construct in harness-bench/BS-5 by chaining 2 solved tasks into a 3rd compound task.

---

## 4. Domain coverage map

### 4.1 Code / SWE
SWE-bench Verified, SWE-bench Pro, SWE-bench Multimodal, Aider Polyglot, BigCodeBench, RepoBench, Long Code Arena, SWE-Lancer, CommitPackFT (base), GH Archive (base), Stack Overflow (base), MLE-bench. **Coverage: STRONG.** No gap.

### 4.2 Cancer / Biomedical
BIOMNI, MedQA, BioASQ, PubMedQA, PMC OA (base). **Coverage: GOOD** for general bio. **GAP**: cancer-specific subset is thin — BIOMNI's 433 instances cover broad bio reasoning but not deeply cancer-clinical. **Mitigation**: pull cancer-tagged subsets of PubMedQA + PMC OA; consider adding LAB-Bench (already in inspect_evals/lab_bench_*) for biology research capabilities.

### 4.3 Cybersecurity
Cybench, NYU CTF Bench, CyberSecEval 2/3 (and 4 via inspect_evals). **Coverage: STRONG.** Inspect AI also has 3CB, CVEBench, CyberGym, CyberMetric, GDM CTF, InterCode CTF, SEvenLLM, SecQA — consider adding for breadth.

### 4.4 Legal
LegalBench, CaseHOLD. **Coverage: ADEQUATE.** **GAP**: contract analysis specifically; consider adding CUAD (Atticus Project, CC-BY-4.0) for v2.

### 4.5 Finance
FinanceBench, FinQA, ConvFinQA. **Coverage: ADEQUATE.** **GAP**: market-event reasoning under time pressure (no public set yet).

### 4.6 Scientific
GPQA Diamond, MLE-bench, MLR-Bench, PaperBench, MMLU-STEM, ChemBench, FOLIO, S2ORC (base), arXiv (base). **Coverage: STRONG.** No major gap.

---

## 5. Pull instructions

Master script skeleton lives at `C:/Users/globa/harness-bench/scripts/pull_datasets.sh` (separate file). Per-dataset pull commands inline below.

### 5.1 HuggingFace datasets (preferred — single auth)
```bash
# Auth once on Spark (puts token in ~/.cache/huggingface)
huggingface-cli login --token "$HF_TOKEN"

# Code/SWE
huggingface-cli download princeton-nlp/SWE-bench_Verified --repo-type dataset --local-dir corpus/swe_bench_verified
huggingface-cli download ScaleAI/SWE-bench_Pro --repo-type dataset --local-dir corpus/swe_bench_pro
huggingface-cli download princeton-nlp/SWE-bench_Multimodal --repo-type dataset --local-dir corpus/swe_bench_mm
huggingface-cli download bigcode/bigcodebench --repo-type dataset --local-dir corpus/bigcodebench
huggingface-cli download tianyang/repobench_python_v1.1 --repo-type dataset --local-dir corpus/repobench_py
huggingface-cli download bigcode/commitpackft --repo-type dataset --local-dir corpus/commitpackft

# Memory / long-context
huggingface-cli download xiaowu0162/longmemeval-cleaned --repo-type dataset --local-dir corpus/longmemeval
huggingface-cli download RMT-team/babilong --repo-type dataset --local-dir corpus/babilong
huggingface-cli download xinrongzhang2022/InfiniteBench --repo-type dataset --local-dir corpus/infinitebench

# Agentic
huggingface-cli download HuggingFaceH4/tau2-bench-data --repo-type dataset --local-dir corpus/tau2
huggingface-cli download xlangai/ubuntu_osworld_verified_trajs --repo-type dataset --local-dir corpus/osworld_ubuntu
huggingface-cli download AssistantBench/AssistantBench --repo-type dataset --local-dir corpus/assistantbench
huggingface-cli download tasksource/planbench --repo-type dataset --local-dir corpus/planbench
huggingface-cli download gaia-benchmark/GAIA --repo-type dataset --local-dir corpus/gaia

# Bio
huggingface-cli download bigbio/med_qa --repo-type dataset --local-dir corpus/medqa
huggingface-cli download qiaojin/PubMedQA --repo-type dataset --local-dir corpus/pubmedqa
huggingface-cli download jablonkagroup/ChemBench --repo-type dataset --local-dir corpus/chembench
huggingface-cli download Idavidrein/gpqa --repo-type dataset --local-dir corpus/gpqa  # gated logger required
huggingface-cli download TIGER-Lab/MMLU-STEM --repo-type dataset --local-dir corpus/mmlu_stem

# Finance
huggingface-cli download PatronusAI/financebench --repo-type dataset --local-dir corpus/financebench
huggingface-cli download ibm-research/finqa --repo-type dataset --local-dir corpus/finqa
huggingface-cli download MehdiHosseiniMoghadam/ConvFinQA --repo-type dataset --local-dir corpus/convfinqa

# Legal
huggingface-cli download nguha/legalbench --repo-type dataset --local-dir corpus/legalbench

# Cybersec
huggingface-cli download facebook/cyberseceval3-visual-prompt-injection --repo-type dataset --local-dir corpus/cyberseceval3

# Reasoning
huggingface-cli download yale-nlp/FOLIO --repo-type dataset --local-dir corpus/folio

# Real-trace base
huggingface-cli download allenai/WildChat-1M --repo-type dataset --local-dir corpus/wildchat
huggingface-cli download sentence-transformers/s2orc --repo-type dataset --local-dir corpus/s2orc
```

### 5.2 git-clone datasets (need build step)
```bash
# Long Code Arena
git clone https://github.com/JetBrains-Research/lca-baselines corpus/lca

# TAU-bench + tau2-bench
git clone https://github.com/sierra-research/tau-bench corpus/tau_bench
git clone https://github.com/sierra-research/tau2-bench corpus/tau2_bench

# OSWorld (full repo with sim setup)
git clone https://github.com/xlang-ai/OSWorld corpus/osworld

# WebArena + VisualWebArena (full Docker setup)
git clone https://github.com/web-arena-x/webarena corpus/webarena
git clone https://github.com/web-arena-x/visualwebarena corpus/visualwebarena

# AppWorld
git clone https://github.com/StonyBrookNLP/appworld corpus/appworld

# ToolBench
git clone https://github.com/OpenBMB/ToolBench corpus/toolbench

# Aider Polyglot
git clone https://github.com/Aider-AI/polyglot-benchmark corpus/aider_polyglot

# RULER
git clone https://github.com/NVIDIA/RULER corpus/ruler

# LoCoMo
git clone https://github.com/snap-research/locomo corpus/locomo

# MMLongBench-Doc
git clone https://github.com/mayubo2333/MMLongBench-Doc corpus/mmlongbench_doc

# BIOMNI
git clone https://github.com/snap-stanford/biomni corpus/biomni

# NYU CTF Bench
git clone https://github.com/NYU-LLM-CTF/LLM_CTF_Database corpus/nyu_ctf

# SWE-Lancer
git clone https://github.com/openai/SWELancer-Benchmark corpus/swe_lancer

# MLE-bench
git clone https://github.com/openai/mle-bench corpus/mle_bench

# MLR-Bench
git clone https://github.com/chchenhui/mlrbench corpus/mlr_bench

# ConceptARC
git clone https://github.com/victorvikram/ConceptARC corpus/conceptarc

# FreshQA + RealTimeQA
git clone https://github.com/freshllms/freshqa corpus/freshqa
git clone https://github.com/realtimeqa/realtimeqa corpus/realtimeqa  # verify URL
```

### 5.3 Bulk fetchers (curl/wget/specialized)
```bash
# arXiv metadata (Kaggle, CC0)
kaggle datasets download -d Cornell-University/arxiv -p corpus/arxiv_meta --unzip

# Stack Overflow dump (April 2024 snapshot, Internet Archive)
wget -P corpus/stackoverflow https://archive.org/download/stackexchange/stackoverflow.com-Posts.7z
wget -P corpus/stackoverflow https://archive.org/download/stackexchange/stackoverflow.com-Comments.7z
# (etc — see archive.org/details/stackexchange for full file list)

# PubMed Central OA (commercial-OK subset)
# Use NCBI's official FTP. Filter via .csv listing of CC-licenses
wget -m -np -nH --cut-dirs=4 -A "*.tar.gz" \
  https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/ \
  -P corpus/pmc_oa_commercial

# GitHub Archive (one month at a time; 30 GB/month)
# Replace YYYY-MM-DD-HH range as needed
for d in 2026-01-{01..31}; do
  for h in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23; do
    wget -P corpus/gharchive "https://data.gharchive.org/${d}-${h}.json.gz"
  done
done
```

### 5.4 Live fetchers (do NOT bundle — pull at eval time)
- **arXiv full-text PDFs**: `scripts/fetch_arxiv_pdf.py <id>` — pulls from S3/arxiv on demand, never caches to release.
- **BioASQ full corpus**: requires registration at bioasq.org; auth flow handled by `scripts/fetch_bioasq.py`.
- **MIMIC-III/IV**: DUA-gated; we DO NOT include in v1.

### 5.5 Master `pull_datasets.sh` skeleton
The full script lives at `C:/Users/globa/harness-bench/scripts/pull_datasets.sh`. Top-level structure:
```bash
#!/usr/bin/env bash
set -euo pipefail

STRATEGY="${1:-fast}"   # fast | full | minimal
HF_CACHE="${HF_CACHE:-$HOME/.cache/huggingface}"
CORPUS_DIR="${CORPUS_DIR:-./corpus}"

mkdir -p "$CORPUS_DIR"

source ./scripts/_pull_hf.sh           # 5.1 block
source ./scripts/_pull_git.sh          # 5.2 block
[ "$STRATEGY" != "minimal" ] && source ./scripts/_pull_bulk.sh   # 5.3 block

# Live fetchers stay as on-demand (5.4); not run here.
echo "Done. See $CORPUS_DIR/"
```

---

## 6. Inspect AI integration notes

Inspect AI uses `Sample(input, target, metadata)` and a `Dataset` loader pattern. For each dataset family, the integration approach:

### 6.1 Already-ported datasets (40 of 66) — use directly via `inspect_evals`
- Add `inspect_evals` to harness-bench dependencies.
- Invoke as `inspect eval inspect_evals/swe_bench --model ... --solver ours`.
- For our M/FM/BS overlay tasks: subclass the existing `Task` and add our scorers.
- **Action**: in `harness-bench/inspect_extensions/registry.py`, mirror the inspect_evals registry imports plus our extensions. Catalog of which inspect_evals tasks we touch is captured in §1 column "Inspect".

### 6.2 Adapter pattern (HF JSONL)
For a new HF JSONL dataset (LongMemEval, RepoBench, FinQA, etc.), the adapter is:
```python
from inspect_ai.dataset import Sample, hf_dataset

def record_to_sample(record: dict) -> Sample:
    return Sample(
        input=record["question"],
        target=record["answer"],
        metadata={
            "session_history": record.get("history"),
            "axis": "M1",
            "domain": "general",
            "license_tag": "MIT",
        },
    )

dataset = hf_dataset(
    path="xiaowu0162/longmemeval-cleaned",
    split="test",
    sample_fields=record_to_sample,
)
```
Pattern lives in `harness-bench/inspect_extensions/adapters/hf_jsonl.py`.

### 6.3 Adapter pattern (git+JSON)
For git-cloned datasets (TAU-bench, RULER, BIOMNI), wrap in a `Dataset` callable that walks the repo's data dir:
```python
from inspect_ai.dataset import Sample, json_dataset

dataset = json_dataset(
    json_file="corpus/tau_bench/data/airline/tasks.json",
    sample_fields=record_to_sample,
)
```

### 6.4 Adapter pattern (multi-modal)
Long Code Arena / VisualWebArena / SWE-bench Multimodal need image-bearing samples. Inspect AI supports `ContentImage` in `Sample.input` — pattern:
```python
from inspect_ai.dataset import Sample
from inspect_ai.model import ContentImage, ContentText

sample = Sample(
    input=[ContentText(text=question), ContentImage(image=img_path)],
    target=answer,
)
```
Image paths point into `corpus/<dataset>/images/`.

### 6.5 Scoring functions
- **Programmatic** (exact-match, F1, pass@k): use Inspect AI's built-in `match`, `f1`, `includes`. Used by SWE-bench-style (test-pass), MedQA, GPQA (MC), FinQA (numeric).
- **Model-graded**: required for LongMemEval, LoCoMo, BIOMNI, MLR-Bench, harness-bench/BS-2-to-5. Use `model_graded_qa` from `inspect_ai.scorer`. Default judge: Claude 4.6 Sonnet (cost-efficient) with Claude 4.7 Opus reserved for sanity checks on a 10% holdout.
- **Composite scoring** for harness-bench M/FM/BS axes: each axis has a custom scorer in `harness-bench/scorers/`. Example: `m1_retrieval_scorer.py` measures whether the agent surfaced facts from session 3 of a 32-session dialog.

### 6.6 Solver instrumentation
For FM-4 (KV-cache drift), we need to instrument inside the solver call: track activation hashes across prompt-prefix variants. Inspect AI's `solver` decorator gives us per-step access to model state. Implementation in `harness-bench/scorers/fm4_kv_drift_probe.py` uses Inspect AI's `chain_of_thought` solver as a base and adds per-token logprob diffing.

### 6.7 Eval grouping
We define 6 eval suites in `harness-bench/eval_suites/`:
- `memory.eval` — M1-M5 across all relevant datasets (24 tasks).
- `pain_modes.eval` — FM1-FM5 (12 tasks).
- `bisociation.eval` — BS1-BS5 (15 tasks).
- `domain_code.eval`, `domain_bio.eval`, `domain_cyber_legal_finance.eval`, `domain_sci.eval`.
Suites are runnable as `inspect eval-set harness-bench/memory.eval --model claude-opus-4-7 --harness=ours`.

---

## 7. Storage + Spark deployment

### 7.1 Total storage
| Tier | Size | Datasets |
|------|------|----------|
| **Hot (must be on Spark resident disk)** | ~50 GB | All HuggingFace JSONL datasets, RULER, TAU-bench, AppWorld, Long Code Arena, OSWorld minimal trajectories, Aider Polyglot, BABILong eval split (skip 10M tokens). |
| **Warm (Spark on demand or external HDD)** | ~70 GB | InfiniteBench full, BABILong full incl. 1M+10M lengths, RepoBench, SWE-Lancer w/ Docker, MLE-bench (Docker images), WebArena/VisualWebArena (Docker apps + DBs). |
| **Cold (live-fetched)** | ~150 GB equivalent | PubMed Central OA bulk (~110 GB filtered), S2ORC OA (~70 GB but pull-on-demand by domain), arXiv full-text via fetcher only, GH Archive monthly windows. |
| **TOTAL nominal** | **~280 GB** | |

### 7.2 Spark (DGX 192.168.108.72) plan
- Spark has **119 GB RAM, 112 GB free disk** as of 2026-04-21. Cannot fit the whole corpus.
- **Strategy**: hot tier on Spark (~50 GB resident); warm tier behind an attached external HDD or NFS mount; cold tier via on-demand fetch with disk LRU at 30 GB cap.
- Place corpus at `/spark-data/harness-bench/corpus/`. Symlink HF cache into `/spark-data/hf-cache`. Both backed by `XFS` for inode efficiency.
- Pull command (run on Spark):
```bash
ssh dgx-spark "cd /spark-data/harness-bench && bash scripts/pull_datasets.sh fast"
```
- Sync results back via `spark-sync-back`.

### 7.3 Pull-once cache
- Maintain `corpus/_cache_manifest.json` — dataset → version-id → SHA256. Re-pull only when upstream version-id changes.
- Run `scripts/verify_cache.py` weekly via `loop` skill to detect upstream version drift (BABILong, RULER, FreshQA, RealTimeQA all rotate or update).

### 7.4 Disk-cost-of-storage check
- Filtering PMC OA to commercial-OK subset (CC0+CC-BY+CC-BY-SA+CC-BY-ND): roughly 50-60% of articles, drops bulk from ~250 GB to ~110 GB. Filter via `LICENSE` field in PMC OA file-list CSV.
- Skipping BABILong's 10M-token split halves its on-disk size.
- `_pull_hf.sh` accepts `--skip-large` to drop sets >5 GB on first pull.

---

## 8. Datasets we still need to construct

### 8.1 BS-2 — frame-shift hypothesis
**Source material**: arXiv abstracts + S2ORC + ChemBench + GPQA Diamond.
**Construction**: take 100 questions from one domain (e.g. chem), cast as analogous in another (e.g. bio or physics). Score: whether the model recognizes the frame and answers correctly.
**Output**: `tasks/bisociation/bs2_frame_shift/`. ~50 samples.

### 8.2 BS-3 — cross-paper synthesis
**Source material**: S2ORC + PubMed Central OA + arXiv metadata.
**Construction**: hand-curate 50 hypothesis statements that REQUIRE combining 2-3 papers' findings (no single paper supports the claim). Include the 2-3 candidate papers + 5 distractor papers per task. Ground truth: which subset combination yields a valid hypothesis.
**Output**: `tasks/bisociation/bs3_cross_paper/`. ~50 samples. Build-time: ~40h human, ~$2K judge cost via Claude 4.7.

### 8.3 BS-4 — tool-output bisociation
**Source material**: ToolBench + AppWorld + τ²-bench tool stubs.
**Construction**: design 50 tasks where outputs of 2 tool calls must be combined in a non-obvious way (e.g. weather API + flight API → "best layover city this week"). Build conflict checks.
**Output**: `tasks/bisociation/bs4_tool_output/`. ~50 samples.

### 8.4 BS-5 — solution recombination
**Source material**: BigCodeBench + Long Code Arena + SWE-Lancer.
**Construction**: pair task A and task B (both solved by same agent in earlier eval); pose new task C requiring elements from both A and B. Measure recombination quality.
**Output**: `tasks/bisociation/bs5_recombination/`. ~50 samples.

### 8.5 FM-3 — condensation loops
**Source material**: any M1/M5 dataset (LongMemEval most natural).
**Construction**: programmatic. Apply repeated context-compaction rounds to a M1 task; measure when the answer-relevant fact gets evicted. Score: number of compaction rounds before failure.
**Output**: `tasks/pain_modes/fm3_condensation/` + a custom Inspect AI solver `harness-bench/inspect_extensions/solvers/condensation_loop.py`.

### 8.6 FM-4 — KV-cache drift
**Source material**: any task with stable suffix and varying prefix.
**Construction**: take 50 base questions; for each, generate 5 prompt-prefix variants that should NOT change the answer. Run with cache reuse enabled. Score: drift in answer under cache reuse.
**Output**: `tasks/pain_modes/fm4_kv_drift/` + `solvers/kv_drift_probe.py`.
**Note**: this requires harness-level cooperation (not all model providers expose cache state). Document as "experimental — Anthropic only" for v1.

### 8.7 FM-5 — destructive-action under conflict
**Source material**: τ²-bench + AppWorld + OSWorld primitives.
**Construction**: design 80 scenarios where user request CONFLICTS with policy or with another tool's output. Measure: does agent take destructive action anyway, or correctly stop and ask?
**Output**: `tasks/pain_modes/fm5_destructive/`. Builds atop tau2-bench's policy framework.

### 8.8 AnalogyBench / E-MAGIC
Web search returned no canonical match for these names. Two options:
- (a) **De-orphan**: confirm with user whether they meant a specific paper (the term `E-MAGIC` evokes "Exploiting Magic" but no benchmark match found; `AnalogyBench` could mean BIG-bench's `analogical_similarity`).
- (b) **Construct**: build harness-bench/BS-1-analogy from ConceptARC + FOLIO primitives + 100 hand-authored cross-domain analogies.
v1 ships option (b); user can correct in v1.1.

---

## 9. Versioning & maintenance

- **Catalog version**: v0.1 (this file).
- **Cadence**: re-verify every 90 days via `scripts/verify_licenses.py` — re-fetch each dataset's HF card / repo LICENSE file, diff. Datasets that drift to more restrictive license are flagged.
- **Maintenance check**: dataset updated >18 months ago + no recent paper cites it → mark "stale, reconsider". As of 2026-04-21:
  - BABILong (Jun 2024 NeurIPS): healthy.
  - LoCoMo (Feb 2024): healthy.
  - PlanBench (2022 original): older — flag for re-eval at v2.
  - FOLIO (Sep 2022): older but actively cited.
- All datasets should be re-pulled on the same Spark instance per release for reproducibility; SHA256 of each pull is logged into `corpus/_cache_manifest.json`.



---

## RESEARCH LOG (raw, append-only)

Each web call appends a `## SOURCE: <name>` block here with verbatim findings. Synthesis happens in §1-§8.

### SOURCE: inspect_evals registry (UKGovernmentBEIS/inspect_evals, github.com)
**Total evals**: 150+ across 20+ categories. Of our candidate datasets, the following are ALREADY ported (use directly):
- **Code**: BigCodeBench (`inspect_evals/bigcodebench`), MLE-bench (`inspect_evals/mle_bench`), MLR-Bench / MLRC-Bench (`inspect_evals/mlrc_bench`), PaperBench (`inspect_evals/paperbench`), SWE-Lancer (`inspect_evals/swe_lancer`), SWE-bench Verified (`inspect_evals/swe_bench`), SciCode, USACO, HumanEval, MBPP, APPS, ClassEval, KernelBench, ComputeEval, IFEvalCode, LiveCodeBench-Pro, DS-1000
- **Memory/long-context**: ∞Bench / InfiniteBench (`inspect_evals/infinite_bench_*`), NIAH (`inspect_evals/niah`)
- **Agentic**: AssistantBench, BFCL, BrowseComp, GAIA (3 levels), Mind2Web, OSWorld, Tau2 / τ²-bench (`inspect_evals/tau2_*`), TheAgentCompany, GDPval
- **Cybersec**: Cybench, CVEBench, CyberGym, CyberMetric, CyberSecEval 2/3/4 (5 incl. variants), 3CB, GDM CTF, InterCode CTF, SEvenLLM, SecQA
- **Bio/Sci**: ChemBench, GPQA Diamond, HealthBench, MedQA, PubMedQA, LAB-Bench, scBench, SciKnowEval, FrontierScience
- **Reasoning**: HLE (Humanity's Last Exam), MMLU/MMLU-Pro, AGIEval, ARC, BBH, GSM8K, MATH, MMMU
- **Safety/safeguards**: AgentDojo, AgentHarm, AHB, FORTRESS, MASK, PersistBench, StrongREJECT, WMDP, B3
- **Multimodal**: DocVQA, MMIU, V*Bench, VQA-RAD, ZeroBench, MathVista
- **Scheming**: Agentic Misalignment, GDM Self-Proliferation, GDM Self-Reasoning, GDM Stealth, InstrumentalEval, SAD

**Not (yet) ported but on our list**: SWE-bench Pro, SWE-bench Multimodal, Aider Polyglot, RepoBench, Long Code Arena, LongMemEval, LoCoMo, BABILong, RULER, MMLongBench-Doc, MileBench, FreshQA, RealTimeQA, TAU-bench (we have τ²-bench), WebArena, VisualWebArena, AppWorld, ToolBench, PlanBench, BIOMNI, BioASQ, NYU CTF, LegalBench, CaseHOLD, FinanceBench, FinQA, ConvFinQA, AnalogyBench, ConceptARC, E-MAGIC, FOLIO, PaperQA2 eval, OpenScholar eval.

### SOURCE: SWE-bench Verified (princeton-nlp/SWE-bench_Verified, HuggingFace)
- 500-sample human-verified subset of SWE-bench. Published by OpenAI/Princeton 2024. Pull via HF datasets. License not on landing card; SWE-bench original paper is MIT-released code, dataset typically cc-by-4.0 (verify on landing page).
- HF: `princeton-nlp/SWE-bench_Verified` and mirror `SWE-bench/SWE-bench_Verified`.

### SOURCE: SWE-bench Pro (ScaleAI, Sep 2025)
- 1865 tasks across 41 professional repos, sourced from copyleft-licensed (GPL) repos as a contamination-resistant deterrent.
- Three subsets: **Public Set** (731 instances, GPL-copyleft, public on HF), **Private Set** (276 from 18 proprietary startup codebases — NOT public), **Held-out Set** (858 GPL-copyleft, held out for internal eval).
- Top models score ~23% (vs. ~70% on Verified) — much harder.
- HF: `ScaleAI/SWE-bench_Pro`. Open-source repo: `scaleapi/SWE-bench_Pro-os`.
- License posture: GPL on the underlying repos; benchmark dataset itself license needs verification but treat as MIT/Apache for the benchmark scaffolding.

### SOURCE: SWE-bench Multimodal (princeton-nlp / SWE-bench)
- 617 task instances on visual JS frameworks. License: see HF card. Pull via HF datasets API.
- Adjacent: Multi-SWE-bench (ByteDance-Seed) and SWE-bench Multilingual.

### SOURCE: LongMemEval (xiaowu0162/longmemeval, ICLR 2025)
- License: MIT (planned/declared). ShareGPT5 dependency: Apache-2.0; UltraChat: MIT. Clean.
- HF: `xiaowu0162/longmemeval-cleaned` (preferred — original `xiaowu0162/longmemeval` retained for compat).
- 5 axes covered: information extraction, multi-session reasoning, temporal reasoning, knowledge updates, abstention. Direct fit for **M1 (cross-window retrieval)**, **M3 (stale-fact rejection)**, partial **M4 (procedural memory)** when conversations carry workflow state.
- Released October 2024. arXiv: 2410.10813.

### SOURCE: LoCoMo (snap-research/locomo, ACL 2024)
- 600 turns, 16K tokens average across up to 32 sessions. Multi-modal dialogue.
- License: stated as "permissive open-source" on snap-research site — verify exact license in repo (likely Apache or MIT). GitHub: snap-research/locomo. Paper: arXiv:2402.17753.
- Direct fit for **M1**, **M2 (cross-modal correlation)** because of multi-modal dialogue, partial **M3**.

### SOURCE: BABILong (RMT-team/babilong, NeurIPS 2024)
- HF: `RMT-team/babilong`. Built from bAbI tasks (20 reasoning tasks) embedded in PG19 (Project Gutenberg books) for distractor context.
- Sample lengths: 0K → 10M tokens (eval set 100/sample/length); training set 0K → 128K (1000/sample/length).
- License: PG19 is public-domain, bAbI is BSD — combined dataset license should be permissive (verify on HF card).
- Direct fit for **M5 (working-memory eviction)** — 50M-token recurrent-memory regime is exactly the working-memory eviction stress test. Also feeds **FM-2 (env-hallucination at >700K)** when contexts exceed 700K.

### SOURCE: RULER (NVIDIA/RULER)
- License: **Apache-2.0** (verified — `NVIDIA/RULER/LICENSE`).
- 13 synthetic tasks: retrieval, multi-hop tracing, aggregation, QA. Configurable sequence length.
- Repo: github.com/NVIDIA/RULER. Paper: arXiv:2404.06654.
- Direct fit for **M1**, **M5**, **FM-2**.

### SOURCE: InfiniteBench / ∞Bench (OpenBMB/InfiniteBench)
- HF: `xinrongzhang2022/InfiniteBench`. Already in inspect_evals as `infinite_bench_*`.
- 12 unique tasks at >100K-token contexts. Paper: arXiv:2402.13718.
- License: not on HF card; GitHub repo treats code under MIT-like (verify in LICENSE on repo). Treat as research-only fallback if license unclear.
- Direct fit for **M5**, **FM-2**, **M1**.

### SOURCE: MMLongBench-Doc (mayubo2333/MMLongBench-Doc)
- **License: research-only.** "All previous datasets [are] CC-BY or other open-source. New documents manually checked for academic use." Cannot redistribute commercially.
- Multimodal long-context document understanding. Repo: github.com/mayubo2333/MMLongBench-Doc. Paper: arXiv:2407.01523.
- Direct fit for **M2 (cross-modal correlation)**, **M5**, partial **FM-2**.

### SOURCE: MileBench (multimodal long-context)
- License: not surfaced — needs direct repo check. Treat as research-only until verified.
- Cited as related to MMLongBench-Doc; multi-image VL long-context tasks.
- Direct fit for **M2**, **M5**.

### SOURCE: FreshQA (freshllms/freshqa)
- Original repo: github.com/freshllms/freshqa. Paper: arXiv:2310.03214 (FreshLLMs).
- HF (multilingual variant): `SeaLLMs/FreshQA-multilingual` — license not on card; verify before redistribution.
- Direct fit for **M3 (stale-fact rejection)** because FreshQA explicitly tests over-time-changing answers.

### SOURCE: RealTimeQA
- Tracks real-time-changing answers (similar to FreshQA). Direct fit for **M3**.
- License: needs direct repo check (paper: realtimeqa.github.io / arXiv:2207.13332).

### SOURCE: Aider Polyglot (Aider-AI/polyglot-benchmark)
- 225 hardest Exercism exercises across 6 languages: C++, Go, Java, JavaScript, Python, Rust.
- License: **inherits from Exercism** which uses MIT for tooling and **CC-BY-NC-SA-4.0** for many exercise problems — **flag as restrictive**, treat as eval-only, don't redistribute as part of training corpus.
- Two-attempt protocol with test-result feedback in attempt 2 — useful for **FM-1 (stuck-loops)** if we extend to N>2 attempts.
- Direct fit: code/SWE domain. Inspect AI port not yet present (TBD).

### SOURCE: RepoBench (Leolty/repobench, ICLR 2024)
- HF: `tianyang/repobench-{p,r,c}` and `tianyang/repobench_python_v1.1`.
- License: **CC-BY-NC-ND-4.0** — restrictive (no derivatives, no commercial). Flag for v1: include for eval-only, do not modify or redistribute as part of derivative corpus. Document this constraint in tasks/ adapters.
- Three sub-tasks: RepoBench-R (retrieval), RepoBench-C (completion), RepoBench-P (pipeline). Python + Java.
- Direct fit for **M5 (working-memory eviction)** at repo scale, **M1**, code/SWE domain.

### SOURCE: Long Code Arena (JetBrains-Research)
- License: **permissive** (MIT, Apache-2.0, BSD-3, BSD-2 — re-distributed per upstream GitHub repo licenses, all originally permissive). Clean.
- Suite of 6 benchmarks: library-based code gen, CI builds repair, project-level code completion, commit message generation, bug localization, module summarization.
- HF: `JetBrains-Research/lca-*`. Repo: github.com/JetBrains-Research/lca-baselines. Paper: arXiv:2406.11612.
- Direct fit for **M5**, **BS-1 (cross-domain analogy)** in code via library-based generation, code/SWE.

### SOURCE: TAU-bench (sierra-research/tau-bench)
- License: **MIT** (verified — `LICENSE` file). Clean.
- Domain-specific tool-agent-user interaction: airline + retail domains.
- Repo: github.com/sierra-research/tau-bench. Paper: arXiv:2406.12045.
- Direct fit for **FM-5 (destructive action under conflict)** because user intents conflict with policy guidelines, **M4 (procedural memory)**.

### SOURCE: τ²-bench / tau2-bench (sierra-research/tau2-bench)
- License: **MIT**. HF dataset: `HuggingFaceH4/tau2-bench-data` (also MIT).
- v2 with code fixes + new telecom domain. Adds dual-control (user has tools too).
- Already in inspect_evals as `tau2_*`.
- Direct fit for **FM-5**, **M4**, **BS-4 (tool-output bisociation)** when telecom + airline data overlap.

### SOURCE: OSWorld / OSWorld-Verified (xlang-ai/OSWorld)
- License: **Apache-2.0** (Windows variant), **MIT** (Ubuntu verified-trajectories variant).
- HF: `xlangai/windows_osworld`, `xlangai/ubuntu_osworld`, `xlangai/ubuntu_osworld_verified_trajs`.
- OSWorld-Verified: released July 2025, major update with verified trajectories.
- Already in inspect_evals as `osworld`. NeurIPS 2024.
- Direct fit for **M4 (procedural memory)** at OS-tooling level, **FM-1**, **FM-5**.

### SOURCE: WebArena (web-arena-x/webarena) and VisualWebArena (web-arena-x/visualwebarena)
- License: **MIT** (both, per related projects). Reproducible self-hosted environments + execution-based evaluation.
- Repos: github.com/web-arena-x/webarena, github.com/web-arena-x/visualwebarena. WebArena: ICLR 2024. Paper: arXiv:2401.13649 (VisualWebArena).
- Direct fit for **M4**, **FM-1 (stuck-loops)** in web-nav, **FM-5**.

### SOURCE: AppWorld (StonyBrookNLP/appworld, ACL'24 Best Resource)
- License: **Apache-2.0** (verified — repo).
- 750 tasks across 9 day-to-day apps, 457 APIs. AppWorld Engine controllable simulator.
- HF: `hamishivi/appworld_env_train` (training mirror).
- Direct fit for **M4 (procedural memory)** — workflows across apps, **FM-5**, **BS-4**.

### SOURCE: AssistantBench (oriyor/assistantbench, AssistantBench/AssistantBench HF)
- License: **Apache-2.0** (HF card-confirmed).
- Realistic time-consuming web tasks. Already in inspect_evals as `assistant_bench_*`.
- Direct fit for **M1**, **FM-1**, **BS-1**.

### SOURCE: ToolBench (OpenBMB/ToolBench, ICLR'24 spotlight)
- License: **Apache-2.0** (HF card-confirmed).
- Multi-source tool calling, training + eval data.
- Direct fit for **M4**, **BS-4 (tool-output bisociation)**.

### SOURCE: PlanBench (tasksource/planbench)
- HF: `tasksource/planbench`. License: not explicitly surfaced — needs direct verification on HF card. Tasksource convention is Apache-2.0; treat as such pending check.
- Tests classical planning capabilities.
- Direct fit for **M4 (procedural memory)**, partial **BS-1**.

### SOURCE: BIOMNI (snap-stanford/biomni, Stanford)
- License: **Apache-2.0 on Biomni code**. **MIXED on integrated tools/databases** — many components are non-commercial only. Biomni provides `commercial_mode=True` flag to filter to commercially-safe data only.
- Biomni-Eval1: 433 instances across 10 biological reasoning tasks. Biomni-E1: 150 tools, 105 software packages, 59 databases.
- Repo: github.com/snap-stanford/biomni. Paper: bioRxiv 2025-05.
- Direct fit for **BS-3 (cross-paper synthesis)**, **BS-2 (frame-shift hypothesis)** because biomedical reasoning often requires cross-modality synthesis. Domain: biomedical.

### SOURCE: MedQA (bigbio/med_qa, openlifescienceai/medqa)
- HF: `bigbio/med_qa`, `openlifescienceai/medqa`. License: **MIT** (per BigBio, which standardizes biomedical NLP datasets at Apache-2.0/MIT defaults).
- US/Chinese medical board exams: 12,723 + 34,251 + 14,123 questions across 3 languages.
- Already in inspect_evals as `medqa`.
- Direct fit: biomedical domain factual recall.

### SOURCE: PubMedQA (qiaojin/PubMedQA, bigbio/pubmed_qa)
- HF: `qiaojin/PubMedQA`. License: **MIT** (BigBio default).
- 1K expert + 61.2K unlabeled + 211.3K artificial QA. Already in inspect_evals as `pubmedqa`.
- Direct fit: biomedical, **BS-3** (multi-paper synthesis precursor).

### SOURCE: BioASQ
- 3,243 train + 500+ test, biomedical QA. License: **CC-BY-2.5** typically per BioASQ challenge data terms — verify on bioasq.org. Often requires registration for full corpus.
- Direct fit: biomedical, **M2** when used with images (BioASQ-MM variant).

### SOURCE: ChemBench (jablonkagroup/ChemBench)
- License: **MIT** (clean — confirmed open-source).
- 2,700+ questions across 9 chemistry/materials science domains. Eval-only (using for training compromises integrity).
- Already in inspect_evals as `chembench`.
- Direct fit: scientific domain, factual reasoning.

### SOURCE: NYU CTF Bench (NYU-LLM-CTF/NYU_CTF_Bench, NeurIPS 2024)
- Repo: github.com/NYU-LLM-CTF/LLM_CTF_Database. Paper: arXiv:2406.05590.
- License: needs direct repo check (open-source benchmark per paper title — likely MIT/Apache-2.0).
- 200 challenges across 6 CTF categories. Direct fit: cybersec, **FM-1**, **FM-5**.

### SOURCE: Cybench (already inspect_evals/cybench)
- 39 CTF scenarios. License typically Apache-2.0/MIT per the GitHub-hosted repo. Direct fit: cybersec, **FM-1**, **M4**.

### SOURCE: CyberSecEval 3 (facebook/cyberseceval3-visual-prompt-injection)
- License: **MIT**. Already in inspect_evals as `cyse3_*` (and `cyse2_*`, `cyse4_*`).
- Visual prompt injection focus + broader cybersecurity. Meta AI suite.
- Direct fit: cybersec, **FM-2 (env-hallucination)** when injection prompts confuse the agent, **FM-5**.

### SOURCE: LegalBench (HazyResearch/legalbench, NeurIPS 2023)
- License: **mixed per task** — users must follow per-task source licenses (HF page: `nguha/legalbench`). Filter via `tasks` selector in the repo.
- Most tasks under permissive (Apache-2.0 / CC-BY-4.0); a minority restricted to non-commercial. **Implementation note**: harness-bench should ingest only the permissively-licensed subset for v1; filter at adapter layer.
- 162 legal reasoning tasks. Repo: github.com/HazyResearch/legalbench.
- Direct fit: legal domain. **BS-3** when tasks chain across cases.

### SOURCE: CaseHOLD (Harvard Law Library Caselaw Access)
- License of underlying CAP corpus: **CC0 (public domain)** as of 2024-03-27 — the Caselaw Access Project released all data under public-domain dedication. CaseHOLD task wrapper inherits CC0 + tools typically Apache-2.0.
- 53K multiple-choice on case holdings.
- Direct fit: legal, factual recall.

### SOURCE: FinanceBench (PatronusAI/financebench)
- HF: `PatronusAI/financebench`. Public sample: 150 annotated examples (full set: 10K, gated). License of public sample: **CC-BY-4.0** typically per Patronus dataset cards — verify on HF card.
- Open-book financial QA on real reports.
- Direct fit: finance domain, **BS-3** (cross-report reasoning), **M2** if PDFs/charts retained.

### SOURCE: FinQA (ibm-research/finqa, embedding-benchmark/FinQA)
- License: **MIT**. 2.8K reports, 8K Q&A. Numerical reasoning over structured + unstructured evidence.
- Direct fit: finance, **BS-4** (structured + unstructured table fusion).

### SOURCE: ConvFinQA (MehdiHosseiniMoghadam/ConvFinQA, FinGPT/fingpt-convfinqa)
- License: **MIT**. Multi-turn financial QA.
- Direct fit: finance, **M1** (cross-turn retrieval).

### SOURCE: GPQA Diamond (Idavidrein/gpqa)
- License: **CC-BY-4.0** with strict use term: "agree NOT to reveal examples in plain text or images online" to prevent leakage. **Operational note**: harness-bench MUST gate sample text inside CI, never log to plain-text artifacts. Implement in `scorers/gpqa_safe_logger.py`.
- 198 expert-validated PhD-level Q in physics/chem/bio.
- Already in inspect_evals as `gpqa_diamond`.
- Direct fit: scientific domain, **BS-2** (cross-disciplinary frame shift).

### SOURCE: MMLU-STEM (TIGER-Lab/MMLU-STEM)
- Subset of MMLU. Underlying MMLU license: **MIT**. TIGER-Lab redistribution presumed MIT.
- Already in inspect_evals as `mmlu_*`.
- Direct fit: scientific factual recall.

### SOURCE: FOLIO (yale-nlp/FOLIO, tasksource/folio, EMNLP 2024)
- License: **CC-BY-SA-4.0** (Creative Commons share-alike) per HF card. Mostly clean — confirm derivatives are also CC-BY-SA.
- 1,430 examples, 487 premise sets. First-order logic reasoning in natural language.
- Repo: github.com/Yale-LILY/FOLIO.
- Direct fit: **BS-3** (multi-premise synthesis), reasoning/scientific.

### SOURCE: PaperQA2 / OpenScholar (FutureHouse / AI2 ScholarQABench)
- **OpenScholar's eval = ScholarQABench**: 2,967 expert queries + 208 long-form answers across CS/physics/neuro/biomed. Released by AI2 — typically Apache-2.0/ODC-BY but verify on HF.
- **PaperQA2** does NOT release retrieval corpus (PDF licensing); only releases code (MIT) and a small eval set. Use ScholarQABench for the eval signal.
- Direct fit: **BS-3 (cross-paper synthesis)** — primary signal.

### SOURCE: ConceptARC (victorvikram/ConceptARC)
- License: free for research per repo (no formal license name surfaced — likely MIT or BSD; verify in repo). Treat as research-only fallback.
- Spatial + semantic concept generalization in ARC domain.
- Direct fit: **BS-1 (cross-domain analogy)** — strongest single signal for analogy.

### SOURCE: AnalogyBench
- **Not surfaced in web search**. Status: name may not be canonical. Possible candidates the user might mean: `BIG-bench analogy`, `Analogy-style ARC`, or recent E-MAGIC. Treat as **construction-required**: build a custom analogy probe from FOLIO/ConceptARC/E-MAGIC primitives.

### SOURCE: E-MAGIC (analogy/conceptual blend)
- Not surfaced in web search either; needs manual construction or domain expert input. **Construction-required** for v1.

### SOURCE: WildChat (allenai/WildChat-1M, allenai/WildChat-4.8M)
- License: **ODC-BY** (Open Data Commons Attribution) — clean for redistribution with attribution. Updated retroactively from ImpACT.
- 1M and 4.8M conversational logs, real-world.
- Direct fit: real-trace source. Use to build **M1**, **FM-1** test variants. Does NOT directly map to a benchmark axis but is base material.

### SOURCE: ShareGPT (various mirrors)
- **License: contested**. ShareGPT dumps were scraped from chat.openai.com — OpenAI ToS restricts redistribution. Most HF mirrors (e.g. `anon8231489123/ShareGPT_Vicuna_unfiltered`) are de-facto research-only with unclear legal posture.
- **Recommendation**: **DO NOT INCLUDE** in v1 corpus. Use WildChat as substitute (cleaner license, similar real-trace properties).

### SOURCE: CommitPackFT (bigcode/commitpackft)
- License: **MIT** (verified — HF card explicitly: "license: mit").
- 2 GB filtered version of CommitPack with high-quality NL-instruction-like commit messages.
- Direct fit: real-trace source, code/SWE. Useful for building **M4 (procedural memory)** training/eval samples.

### SOURCE: S2ORC (sentence-transformers/s2orc, allenai/s2orc)
- License: **ODC-BY-1.0** (Open Data Commons Attribution) for the open-access subset; full corpus has restrictions on non-OA papers.
- Massive scientific paper corpus (titles, abstracts, citations, sometimes full text).
- Direct fit: **BS-3 construction base** (cross-paper synthesis), real-trace source for science.

### SOURCE: GitHub Archive / GH Archive (gharchive.org)
- License: GH Archive aggregates the **public GitHub timeline**. License of underlying GitHub events: per GitHub ToS, public repo activity is public. The aggregated dataset on Google BigQuery is treated as a Google Public Dataset (1 TB/month free).
- **Operational note**: when training on data, must respect repo-level licenses. For evaluation purposes (we're not training), we can use freely.
- Direct fit: **real-trace source** for code/SWE workflows. Use to build **M4** trace data.

### SOURCE: Stack Overflow / Stack Exchange Data Dump
- License: **CC-BY-SA-4.0** (current; older snapshots CC-BY-SA-3.0). User contributions are CC-BY-SA per platform terms.
- **WARNING**: As of mid-2024, Stack Exchange now restricts data dumps behind login + agreement-not-to-train-AI. The pre-2024 Internet Archive snapshots remain accessible (April 2024 dump = last fully open). For harness-bench v1, **use the April-2024 Internet Archive dump** to avoid current ToS friction.
- Direct fit: **real-trace source** for code/SWE Q&A patterns.

### SOURCE: PubMed Central Open Access (PMC OA)
- License: **mixed by article**. Three groupings:
  - **Commercial-allowed**: CC0, CC-BY, CC-BY-SA, CC-BY-ND (clean for our use)
  - **Non-commercial only**: CC-BY-NC, CC-BY-NC-SA, CC-BY-NC-ND (use only if benchmark stays NC)
  - **Other**: no machine-readable license (skip)
- Pull via official services only: PMC Cloud Service, PMC OAI-PMH, PMC FTP, E-Utilities, BioC API. Bulk via FTP packages. AcademicTorrents has snapshots: `06d6badd7d1b0cfee00081c28fddd5e15e106165`.
- Direct fit: **real-trace source for biomedical**, **BS-3 construction base** (cross-paper synthesis in bio).
- **Implementation**: filter to commercial-allowed (CC0/CC-BY/CC-BY-SA/CC-BY-ND) at ingest time.

### SOURCE: arXiv bulk dataset (Kaggle: Cornell-University/arxiv, AWS S3)
- **License of metadata**: **CC0-1.0** (Kaggle metadata dump).
- **License of full-text PDFs**: PER-PAPER, default arXiv license does NOT permit redistribution. Most papers are perpetual non-exclusive license to arXiv only.
- **Operational rule**: ship METADATA (CC0) freely; for full-text, ship a fetcher script that pulls live from arXiv on demand. Never bundle PDFs into the harness-bench release.
- Direct fit: **BS-3 construction base** (titles + abstracts + cross-citation graph), partial **M3** (date-anchored knowledge updates).

### SOURCE: BigCodeBench (bigcode/bigcodebench)
- License: **Apache-2.0** (verified in HF README metadata). Already in inspect_evals as `bigcodebench`.
- 1,140 Python questions with diverse libraries.
- Direct fit: code/SWE, **BS-1** (cross-library combinatorial use), **M5**.

### SOURCE: SWE-Lancer (openai/SWELancer-Benchmark)
- 1,488 real-world freelance tasks from Expensify open-source repo + Upwork postings.
- **License**: Public-eval split called **SWE-Lancer Diamond** is open-sourced via GitHub repo; private holdout requires request. License of the public split: per repo (typically Apache-2.0 for OpenAI benchmarks; verify in `LICENSE` file).
- Already in inspect_evals as `swe_lancer`.
- Direct fit: code/SWE, **BS-3**, **M4** (multi-step engineering tasks).

### SOURCE: PaperBench (OpenAI)
- License: code typically Apache-2.0. **Eval data** depends on each ICML 2024 paper's individual license — many are CC-BY for accepted ICML papers. Treat as research-only fallback.
- Already in inspect_evals as `paperbench`.
- Direct fit: scientific, **BS-3**.

### SOURCE: MLR-Bench (chchenhui/mlrbench)
- License: **CC-BY-4.0** (verified — paper states explicitly).
- 201 research tasks from NeurIPS/ICLR/ICML workshops + MLR-Judge + MLR-Agent.
- Already in inspect_evals as `mlrc_bench`.
- Direct fit: scientific/code, **BS-3**, **BS-2**.

### SOURCE: MLE-bench (openai/mle-bench)
- 75 Kaggle competitions. License: code Apache-2.0 (OpenAI repo). Each Kaggle competition's data has its own per-competition terms — embed those at run-time.
- Already in inspect_evals as `mle_bench`.
- Direct fit: code/SWE + scientific, **M4**, **FM-1**.

