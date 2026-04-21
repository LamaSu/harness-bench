# 01 — Public-Dataset Corpus Catalog (harness-bench)

> **Status:** WORK-IN-PROGRESS — researched & maintained by `corpus-writer-alpha`.
> **Date started:** 2026-04-21.
> **Project:** `harness-bench` — agentic-harness benchmark suite riding on top of UK AISI's [Inspect AI](https://inspect.aisi.org.uk/) shell.
> **Scope:** Catalog every PUBLIC dataset to be ingested into the harness-bench corpus. Each dataset gets a row, a license check, a pull command, and an Inspect AI integration note.

---

## 0. TL;DR

(populated after table is complete — see §1 for canonical inventory)

This catalog enumerates **~70 candidate public datasets** across 6 domains (code/SWE, biomedical, cybersecurity, legal, finance, scientific) and three benchmark axis families (M = memory, FM = pain/failure modes, BS = bisociation). The benchmark sits on top of UK AISI's [Inspect AI](https://inspect.aisi.org.uk/) framework, leveraging the existing [`inspect_evals`](https://github.com/UKGovernmentBEIS/inspect_evals) registry where ports already exist (~40 of our datasets are pre-ported).

**License posture:** the corpus is dominated by permissive licenses (MIT, Apache-2.0, CC-BY-4.0). Items requiring DUA/registration (MIMIC-III/IV, some clinical sets) are flagged separately and shipped as fetch-script-only. Items more restrictive than CC-BY-NC are pruned from v1 unless an explicit exception is justified inline.

**Disk footprint:** ~250-400 GB total raw, dominated by InfiniteBench, S2ORC, RepoBench, and PubMed-Central OA bulk. Recommended deployment: stage all corpora once on the DGX Spark (192.168.108.72, /spark-data), pull via `huggingface-cli download`, and serve to harness-bench tasks through Inspect AI's `Dataset` interface.

**Construction-required gaps:** BS-2/BS-3/BS-4/BS-5 (cross-domain hypothesis tasks), FM-4 (KV-cache drift), FM-5 (destructive-action under conflict). These require synthetic generation from base corpora — see §8.

---

## 1. Dataset table — full inventory

| # | Dataset | URL | License | Format | Size | Records | Maps to axes (M/FM/BS) | Maps to domains | Inspect AI integration notes |
|---|---------|-----|---------|--------|------|---------|------------------------|-----------------|------------------------------|

(populated below as research completes — see "Section 1 entries" subsections)

---

## 2. License breakdown

(populated after §1 complete)

---

## 3. Axis coverage map

(populated after §1 complete)

---

## 4. Domain coverage map

(populated after §1 complete)

---

## 5. Pull instructions

(populated incrementally — see `scripts/pull_datasets.sh`)

---

## 6. Inspect AI integration notes

(populated after surveying `inspect_evals` repo)

---

## 7. Storage + Spark deployment

(populated after §1 complete)

---

## 8. Datasets we still need to construct

(populated after §1 complete)

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

