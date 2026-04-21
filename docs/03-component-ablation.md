# 03 — Component Ablation Matrix (harness-bench)

> **Status:** WORK-IN-PROGRESS — written by `ablation-writer-charlie`.
> **Date started:** 2026-04-21.
> **Project:** `harness-bench` — agentic-harness benchmark suite riding on Inspect AI shell.
> **Inputs:** `01-corpus-catalog.md` (66 datasets, axis maps), `02-harness-survey.md` (8 harnesses × 8 layers, 24 candidate ablation arms identified at §4.1-4.8 + 4.9).
> **Scope:** Turn the wave-1 ablation arms into a concrete, runnable matrix — one Inspect AI `Task` row per (arm × dataset × difficulty-tier × harness-impl).

---

## 0. TL;DR

The wave-1 component survey decomposed each of 8 mainstream harnesses across 8 architectural layers (control loop, reasoning, tool surface, tool catalog, memory, sub-agents, safety, verification) and identified 24 distinct implementation strategies as candidate ablation arms (survey §4.1-4.8). This doc operationalizes those arms into a **35-arm matrix** (3-5 arms per layer, plus 5 black-box "harness as-a-cell" anchors for closed systems), maps each arm to the subset of corpus datasets that best exposes its differential, and tiers the run plan into v1-smoke (~120 cells, ~6h Spark wall-clock), v2-broad (~720 cells, ~42h), and v3-full (~3,150 cells, ~180h Spark wall-clock).

Total compute estimate at v3-full: 3,150 cells × ~180s median wall-clock × 4-8 parallel slots on Spark ≈ 175-200 hours wall-clock. API-equivalent cost: ~$2,800-$3,400 across the full sweep at Anthropic/OpenAI list prices for the model-graded scoring + harness model calls (median session ~25K input + 5K output tokens × 3,150 cells × $5/M input + $20/M output, plus judge cost). Full v3 run is intended for one-shot reproducibility at release; v1+v2 are the iteration loop.

The matrix is designed for **vary-one-hold-seven** ablation (§1) — 30 single-layer arm-comparisons against a fixed baseline, plus 5 hand-picked 2-axis interactions (§3) that probe known cross-layer dependencies (e.g., "best-of-N parallel sub-agents requires verification-as-oracle, else nonsense"). All arms map cleanly to wave-1 evidence; every "expected delta" has a citation back to survey §1-§5 or catalog §3.

---

## 1. Ablation philosophy: vary-one-hold-seven

### 1.1 Why not full Cartesian

8 layers × 3-5 strategies each = ~6,500 to 65,000 cells under naive Cartesian product (5^8 = 390,625 worst case). Even at Spark's 4-slot concurrency this is days-to-weeks of wall-clock per dataset, and the marginal cell adds essentially zero information once you've measured each layer's contribution against a fixed baseline.

The DRY answer is **vary-one-hold-seven**: hold 7 layers at the convergent default (the "Claude Code v2.1.69+ + harness 68-rule + harness wave model" cell, §2.0), and vary one layer at a time across its 3-5 candidate strategies. Each layer contributes 3-5 arm-cells; total = 8 × ~4 = 32 single-layer arms (we round to 30 after dropping 2 redundant arms — see §2.x).

This gives us the **per-layer contribution score** (how much does the verification layer matter? how much does the tool catalog matter?). It does NOT measure interaction effects between layers — those go in the targeted 2-axis matrix in §3 (5 hand-picked interactions, ~15 additional arms).

### 1.2 Inspect AI's `task` parameterization

Inspect AI's `@task` decorator accepts arbitrary kwargs that flow into the solver, scorer, and dataset. Our matrix becomes a single parameterized `@task` definition; the runner sweeps the parameter grid and produces one log row per cell. Reference: `inspect_evals/swe_bench/swe_bench.py` uses this pattern to register `instance_subset`, `gold_patches`, and `model` axes.

```python
@task(
  name_template="{harness}_{layer}_{arm}_{dataset}_{difficulty}",
  parameters={
    "harness": ["claude_code", "cline", "aider", "goose", "openhands", "cursor2", "replit3", "devin"],
    "layer":   ["control_loop", "reasoning", "tool_surface", "tool_catalog",
                "memory", "subagents", "safety", "verification"],
    "arm":     "<layer-specific>",        # see §2 per-layer arm tables
    "dataset": "<axis-mapped>",            # see §4 per-arm corpus mapping
    "difficulty": ["smoke", "broad", "full"],
  },
)
def harness_bench(harness, layer, arm, dataset, difficulty):
    ...
```

The runner expands this into individual cells; Inspect AI's `eval-set` command runs them, with `--max-tasks N` controlling Spark concurrency.

### 1.3 Three-tier run plan

| Tier | Datasets-per-arm | Runs-per-cell | Total cells | Wall-clock @ 4 Spark slots | Use |
|------|-----------------|---------------|-------------|---------------------------|-----|
| **v1-smoke** | 1 (smallest) | 1 | 120 | ~6h | Sanity check; CI-on-merge |
| **v2-broad** | 4-6 (axis-balanced) | 3 (median-of) | ~720 | ~42h | Weekly leaderboard refresh |
| **v3-full** | 10-12 (full axis) | 5 (median-of) | ~3,150 | ~175-200h | Quarterly release benchmark |

Tier v1 produces a "harness still alive" signal in 6 hours. Tier v2 produces a credible per-arm contribution score in 2 days. Tier v3 is the publishable result — every claim in the harness-bench paper traces back to v3 cells.

---

## 2. The 8-layer ablation arms

### 2.0 Baseline: the "convergent default" cell

Every vary-one arm holds 7 layers fixed at the following (cited from survey §3.1, §3.2):

| Layer | Baseline value | Citation |
|-------|---------------|----------|
| control loop | Single-thread ReAct, terminate on plain-text response | survey §1.7 (Claude Code), §3.1 first bullet |
| reasoning | Interleaved thinking ON, default for Opus 4.6/4.7 | survey §1.7, §4.2-A |
| tool surface | Atomic ~10 (Read/Edit/Glob/Grep/Bash/Write/Web/Task) + MCP for everything else | survey §1.7, §4.3-A |
| tool catalog | ToolSearch deferred-loading (v2.1.69+ behavior, ~968 tokens base) | survey §1.7, §3.2 fourth bullet |
| memory | Files + git (CLAUDE.md + auto-memory + git substrate) | survey §3.1 third bullet |
| sub-agents | Sequential context-isolated `Task` tool | survey §1.7, §4.6-B |
| safety | Hooks intercept (Pre/Post tool with BLOCK/WARN, harness's 68 rules ON) | survey §1.7 + user CLAUDE.md hook system |
| verification | Inline lint+test reflection + post-hoc shadow-verifier haiku | survey §1.7 (`shadow-verifier`, `smoke-test`) |

This cell is identifier `BASELINE-V0`. Every comparison reports `delta-vs-BASELINE-V0`.

---

### 2.1 Layer: control loop

**What the convergent harness does:** `Coder.run_one()`-style synchronous ReAct (survey §3.1 first bullet — 6/8 harnesses agree). Model emits tool call → executor runs → result appended → model re-called. Terminates on plain-text response or `attempt_completion` tool. (Cited: Cline `Task.recursivelyMakeClineRequests()` survey §1.3; Claude Code §1.7; Goose `Agent.reply` §1.5.)

#### Arm CL-1: Pure single-thread ReAct (BASELINE)
- **Description:** Standard synchronous ReAct loop, ~30s/turn typical, no reflection retries on tool failure (just appends error and continues).
- **Implementation:** Default Claude Code `Task` tool behavior. No flag to set; this is the unmodified baseline.
- **Expected delta:** Defines `0.0` reference for control-loop axis.
- **Best datasets:** All 12 v3 axes — this is the universal denominator.

#### Arm CL-2: ReAct + reflection-bound
- **Description:** After a tool failure (lint error, test fail, exit code != 0), automatically re-query the model with the failure as observation, up to N=3 reflections (Aider's `max_reflections=3`, survey §1.1 + §1.4 source block).
- **Implementation:** Wrap our reference harness with an interceptor that catches non-zero exit + lint diagnostic + test-failure observations and re-injects them as a model turn before the parent loop's next step. Run via `aider --auto-lint --auto-test --max-reflections 3` for the Aider cells; for the Claude-Code-flavored cell, add a post-tool hook that injects observations into the next prompt.
- **Expected delta:** +5-15% on FM-1 (stuck-loops) — Aider's auto_lint/test is widely cited as why it beats larger-context tools on repo correctness (survey §3.1 fourth bullet). Token cost ↑ ~25% (extra turns). Wall-clock ↑ ~30%.
- **Best datasets:** Aider Polyglot (corpus #4, FM-1), SWE-bench Verified (#1, M5+FM-1), harness-bench/FM-1-stuck-loops (#61), MLE-bench (#36, FM-1 training stalls).

#### Arm CL-3: Event-driven async controller
- **Description:** Replace sync ReAct with OpenHands-style event-driven `_step()` + event stream + `should_step()` decision. Model action published as event; observation event triggers next `_step` decision.
- **Implementation:** Run OpenHands V0 as the harness for this cell (`openhands.controller.AgentController` per survey §1.2). For non-OpenHands cells, this is a SWAP arm — not a wrapper toggle. We DO NOT attempt to retrofit event-driven control into Claude Code or Cline.
- **Expected delta:** Roughly neutral on outcome; possible -5% on M4 (procedural memory) due to controller overhead per step. Expected to surface when sub-agents are concurrent (event stream lets them publish).
- **Best datasets:** AppWorld (#25, M4), TAU-bench (#20, FM-5+M4), OSWorld (#22, M4+FM-1+FM-5).

#### Arm CL-4: Multi-agent orchestrator wrapping inner ReAct
- **Description:** Outer orchestrator decomposes task → spawns N inner ReAct agents (worktree-isolated) → merges results. This is the user's `/go` wave model (Phase 1b LLM decomposition) and Cursor 2's 8-agent best-of-N (survey §1.6).
- **Implementation:** Use the user's `/go` pipeline as the orchestrator. Set `WAVE_MAX_PARALLEL=4` (matches Spark's 4-slot concurrency). Disable for control: `--single-agent` flag short-circuits to BASELINE.
- **Expected delta:** +10-25% on BS-5 (recombination) and BS-3 (cross-paper synthesis) where parallelism enables exploring multiple solution paths. Token cost ↑ 4x (parallel agents). Wall-clock ~same (parallelism eats latency).
- **Best datasets:** harness-bench/BS-5-recombination (#66 subset), MLR-Bench (#50), SWE-Lancer (#8, M4+BS-3), harness-bench/BS-3 (#66 subset).

**Layer CL totals: 4 arms.** (CL-1, CL-2, CL-3, CL-4.)

---

### 2.2 Layer: reasoning

**What the convergent harness does:** Interleaved thinking ON by default for Opus 4.6/4.7 + Sonnet 4.6 (survey §1.7, user CLAUDE.md `feedback_prefer_opus_4_7.md`). Note from survey §3.3: this is a Claude-Code-specific assertion; the rest of the field treats thinking as model-side, not harness-side.

#### Arm R-1: Interleaved thinking ON (BASELINE)
- **Description:** Anthropic's interleaved-thinking content blocks emitted between tool calls, used by the model to plan/reflect mid-loop. Default-on for Opus 4.6/4.7.
- **Implementation:** Default Claude Code config. No env var change.
- **Expected delta:** `0.0` reference.
- **Best datasets:** All 12 v3 axes.

#### Arm R-2: Interleaved thinking OFF
- **Description:** Hard-disable thinking via Anthropic API parameter `thinking={"type": "disabled"}`. Faster turns, raw ReAct.
- **Implementation:** Wrapper flag on harness invocation: `--no-thinking`. The harness passes `thinking.type = disabled` to the API. (Documented in Anthropic's API reference; survey §1.7 implies this is a flag.)
- **Expected delta:** -10-20% on BS-2 (frame-shift) and BS-1 (analogy) — bisociation tasks benefit from extended reflection. Latency ↓ 30%. Token cost ↓ 15-20% (no thinking blocks). FM-3 (condensation) and FM-4 (KV-cache drift) may IMPROVE because shorter context is less likely to drift.
- **Best datasets:** BS-1 (#47, #48 ConceptARC + AnalogyBench), BS-2 (#66 frame-shift constructed), GPQA Diamond (#34, BS-2 + factual sci), MLR-Bench (#50, BS-2/BS-3), FM-3 (#63), FM-4 (#64).

#### Arm R-3: Plan-then-execute split
- **Description:** Two-mode workflow — first model call produces a plan only (no tool calls allowed), second call executes (no plan revisions allowed). Cline's Plan/Act mode (survey §1.3 + §3.3 third bullet) and Aider's architect mode (survey §1.1).
- **Implementation:** SWAP arm — pin Cline as harness, set mode flag to `plan-then-act`. For non-Cline cells, retrofit via system prompt that forbids tool calls until model emits `<plan>...</plan>` block.
- **Expected delta:** +5-12% on M4 (procedural memory) and PlanBench (#28). +0 to -5% on FM-1 (stuck-loops) — plans don't help if execution still loops. Token cost ↑ 10-20% (extra plan turn). Wall-clock ↑ 40% (two model calls per logical step).
- **Best datasets:** PlanBench (#28, M4), AppWorld (#25, M4), SWE-Lancer (#8, M4+BS-3), TAU-bench (#20, FM-5+M4), OSWorld (#22).

#### Arm R-4: Echo thinking content across turns
- **Description:** Goose pattern — preserve `reasoning_content` from one turn and prepend it to the next assistant message (survey §1.5). Provider-specific (Gemini, Kimi, DeepSeek). Builds chain across turns vs. one-shot reflection.
- **Implementation:** SWAP arm — pin Goose as harness for this cell. For Anthropic-flavored variants, this requires custom solver state (preserve thinking content as `metadata`).
- **Expected delta:** +5% on M4 (multi-step procedural). Marginal on others. Useful primarily as a "what if non-Anthropic providers do better with chain preservation?" probe.
- **Best datasets:** AppWorld (#25), TAU-bench (#20), tau2-bench (#21).

**Layer R totals: 4 arms.**

---

### 2.3 Layer: tool surface

**What the convergent harness does:** ~10 atomic (Read/Edit/Glob/Grep/Bash/Write/Web/Task) + MCP for everything else (survey §1.7, §3.1 second bullet). Cline 24, Continue 20, OpenHands ~7-10 — all within "15-20 + MCP" range.

#### Arm TS-1: Atomic core ~10 + MCP (BASELINE)
- **Description:** Standard Claude Code tool surface plus user's MCP servers (per `~/.claude/.mcp.json`).
- **Implementation:** Default. No change.
- **Expected delta:** `0.0` reference.
- **Best datasets:** All v3 axes.

#### Arm TS-2: Wide flat surface (24 named handlers, no MCP)
- **Description:** Cline-style 24 named tool handlers (ReadFile, WriteToFile, ApplyPatch, ExecuteCommand, BrowserTool, WebFetch, WebSearch, SearchFiles, ListFiles, ListCodeDefinitionNames, AskFollowupQuestion, AttemptCompletion, etc; survey §1.3 source block).
- **Implementation:** SWAP — pin Cline as harness; ensure MCP is disabled (`--no-mcp`). Tests whether broad-named-handler approach beats minimalist atomic.
- **Expected delta:** -5-10% on tool-heavy tasks (more candidates → more selection error). Token cost ↑ 30% (24 tool schemas in surface). +5% on simple file-ops where the more granular tools (ListFiles vs Glob) match intent better.
- **Best datasets:** SWE-bench Verified (#1), BigCodeBench (#5, BS-1+M5), AppWorld (#25), AssistantBench (#26).

#### Arm TS-3: Pure-MCP (Goose-style; every tool is an extension)
- **Description:** Every capability comes from an MCP extension (no fixed atomic set). Survey §1.5 + §4.3-C. Goose's `ExtensionManager` pattern.
- **Implementation:** SWAP — pin Goose as harness. For Claude Code variants, this is impossible without forking — note as "Goose-only" cell.
- **Expected delta:** -3-8% on FM-2 (env-hallucination) — more tool surface area → more failure modes. +0 to +5% when many specialized tools are needed (Web3, biomed APIs). Token cost ↑ 20-50% depending on extension count.
- **Best datasets:** ToolBench (#27), AppWorld (#25), BIOMNI (#29 — needs biomed-specific MCP).

#### Arm TS-4: Text-native (no function tools, diff-format only)
- **Description:** Aider pattern — model emits diffs in textual `editblock`/`udiff`/`whole`/`patch` format; no tool-call protocol (survey §1.1, §3.1 second bullet outlier).
- **Implementation:** SWAP — pin Aider as harness. Ablate diff-format choice within: `aider --edit-format editblock|udiff|whole|patch`. This is also a sub-arm matrix; we collapse to 1 main arm and 1 secondary "best-of-Aider-formats" comparison.
- **Expected delta:** +10-20% on small focused edits (BigCodeBench #5, simple SWE tasks); -10-20% on multi-file orchestration (no Task tool). Token cost ↓ 10-15% (no tool-call schema overhead).
- **Best datasets:** SWE-bench Verified (#1), BigCodeBench (#5), Aider Polyglot (#4), CommitPackFT-derived tasks.

#### Arm TS-5: Bash-only (no file tools at all)
- **Description:** Strip Read/Edit/Write/Glob/Grep — leave only Bash + Task + Web. Tests whether the dedicated file tools matter or whether `cat`/`grep`/`sed` via Bash is sufficient. (NOT in survey arms but worth probing — addresses the question "is the file-tool surface load-bearing?")
- **Implementation:** Wrapper flag — `--tool-allowlist=Bash,Task,WebFetch,WebSearch`. The harness's hook system already supports per-tool allowlists.
- **Expected delta:** -15-30% on code tasks (Bash file editing is fragile, sed errors common). +0 on agentic web tasks (don't need file tools). Token cost ↑ ~10% (more verbose Bash invocations). FM-1 (stuck-loops) likely increases significantly — Bash-driven file edits chain failures.
- **Best datasets:** SWE-bench Verified (#1), Aider Polyglot (#4, FM-1), harness-bench/FM-1 (#61), AssistantBench (#26).

**Layer TS totals: 5 arms.**

---

### 2.4 Layer: tool catalog

**What the convergent harness does:** ToolSearch deferred loading (Claude Code v2.1.69+ behavior, ~968 tokens base vs ~14-16k pre-v2.1.69; survey §1.7 + §3.2 fourth bullet, also source block "ClaudeCode v2.1.69 ToolSearch").

#### Arm TC-1: ToolSearch deferred loading (BASELINE)
- **Description:** All built-in tools deferred behind ToolSearch; tool_reference blocks expand on demand (3-5 results per query).
- **Implementation:** Default Claude Code v2.1.69+. No change.
- **Expected delta:** `0.0` reference.
- **Best datasets:** All v3 axes (tool catalog cost shows up at length).

#### Arm TC-2: Static eager-load all tools upfront
- **Description:** Pre-v2.1.69 Claude Code behavior — all tool schemas loaded into system prompt (~14-16k tokens). Same for Cline, Continue, Goose default.
- **Implementation:** Pin Claude Code to v2.1.68 OR run with `--no-tool-search` flag (verify flag exists; if not, downgrade binary). For Cline/Continue/Goose cells, this is the native behavior.
- **Expected delta:** -3-8% on tasks where context window is binding constraint (M5 working-memory eviction, FM-2 env-hallucination >700K). Token cost ↑ 14-15K per turn (the tool schemas). Latency neutral.
- **Best datasets:** BABILong (#11, M5+FM-2 esp >700K split), RULER (#12), InfiniteBench (#13), RepoBench (#6), Long Code Arena (#7), harness-bench/FM-2 (#62).

#### Arm TC-3: Dynamic per-request prompt assembly
- **Description:** Cline pattern — `getSystemPrompt(promptContext)` rebuilds tool surface per request based on enabled features (e.g., `READ_ONLY_TOOLS` only for read-only mode; survey §1.3, §4.4-C).
- **Implementation:** SWAP — pin Cline as harness. The toggle is whether `promptContext` adapts (default Cline) or fixed (use `--static-prompt` flag if available; else compare against Claude Code TC-2).
- **Expected delta:** +2-5% over TC-2 (static), -2-3% under TC-1 (deferred) on long-context tasks. Token cost ~halfway between TC-1 and TC-2.
- **Best datasets:** BABILong (#11), RepoBench (#6), Long Code Arena (#7).

#### Arm TC-4: Microagent / skill-router (intent-filtered surface)
- **Description:** OpenHands microagent system + Claude Code's skill-router agent (haiku-based; user CLAUDE.md). Pre-classifies task → injects only relevant skill metadata + tool descriptions. NOT tool-search-by-keyword (TC-1) but task-type-by-intent.
- **Implementation:** Use the user's `/go` Phase 0 skill-router (haiku agent) as the catalog gate. Wrapper flag: `--skill-router=on|off`.
- **Expected delta:** +2-5% on tool-heavy long-context tasks (skill-router prunes irrelevant surface earlier than ToolSearch). Token cost flat (router itself costs ~2K but saves 4-6K). +0 to +3% on agentic web (intent-classification fits well).
- **Best datasets:** AppWorld (#25), AssistantBench (#26), GAIA (#18, M4+BS-1), TAU-bench (#20).

**Layer TC totals: 4 arms.**

---

### 2.5 Layer: memory

**What the convergent harness does:** Files + git as substrate (survey §3.1 third bullet — striking: NOT a single harness uses vector DB as primary memory). CLAUDE.md + auto-memory + git for Claude Code; `.clinerules` + checkpoints for Cline; `.continue/` for Continue; etc.

#### Arm M-1: Files + git only (BASELINE)
- **Description:** Pure file substrate (CLAUDE.md, MEMORY.md, ai/memory/* per user's harness). Git as durable store. No vector DB. No summary cache beyond model's own context.
- **Implementation:** Default Claude Code + user's harness CLAUDE.md memory pattern.
- **Expected delta:** `0.0` reference.
- **Best datasets:** All v3 axes.

#### Arm M-2: Files + auto-summary cache
- **Description:** Add Aider's `ChatSummary` / Goose's `compact_messages` / Cline's `ContextManager` quarter-truncation. Periodically compress conversation history into a summary; cache the summary in a file.
- **Implementation:** Wrapper — enable user's `/compact` skill on auto-trigger every N turns. For non-Claude-Code cells, use the harness's native compaction (Aider `--show-pretty-diffs` + cache; Goose `compact_messages` ON; Cline ContextManager ON).
- **Expected delta:** +5-10% on M5 (working-memory eviction) and FM-3 (condensation loops — IF the summarization is well-tuned; can also REGRESS by 10-15% if compaction is too aggressive). +0 on short tasks. -2-5% on M1 (cross-window retrieval) — summarization risks evicting load-bearing facts.
- **Best datasets:** LongMemEval (#9, M1/M3/M4), LoCoMo (#10, M1+M2), BABILong (#11, M5), harness-bench/FM-3 (#63), RULER (#12, M1+M5).

#### Arm M-3: Files + structured event log + checkpoints
- **Description:** Cline's `checkpointManager` + OpenHands' `StateTracker`. Every action+observation logged to durable event store; checkpoints rollback-able. Differs from M-1 in that the event log is structured and queryable, not just chat history.
- **Implementation:** SWAP — pin Cline (checkpointManager ON) or OpenHands (StateTracker default). For Claude Code cells, retrofit via post-tool hook that appends to `ai/events/log.jsonl`.
- **Expected delta:** +5-15% on FM-1 (stuck-loops) — checkpoints enable backtrack-and-retry without LLM context bloat. +5-10% on M4 (procedural memory) when task involves rollback. Token cost flat (event log is out-of-band).
- **Best datasets:** SWE-bench Verified (#1), Aider Polyglot (#4, FM-1), AppWorld (#25), MLE-bench (#36), OSWorld (#22).

#### Arm M-4: Files + LRU-indexed codebase RAG
- **Description:** Continue's `CodebaseIndexer` + opened-file LRU pattern (survey §1.4 + §4.5-D). Runs continuous embedding-index on the working repo; injects relevant chunks via retrieval per request.
- **Implementation:** SWAP — pin Continue as harness OR run user's CodeSight + `/code-search` on every model turn (harness already exposes this via `codesight search`). Wrapper flag: `--rag-on-turn=on`.
- **Expected delta:** +10-20% on RepoBench (#6, M1+M5), Long Code Arena (#7, M5+BS-1) — repo-scale retrieval is the killer app. +0 to +5% on isolated tasks. Token cost ↑ ~30% (RAG chunks injected per turn).
- **Best datasets:** RepoBench (#6), Long Code Arena (#7), SWE-bench Verified (#1), SWE-bench Pro (#2), SWE-Lancer (#8).

#### Arm M-5: Vector-only (no file substrate, RAG primary)
- **Description:** Adversarial probe — replace files+git with pure vector DB (Chroma/LanceDB) for memory. Tests whether the field's "vector DB nowhere as primary" finding (survey §3.1 third bullet) is confirmed when forced.
- **Implementation:** Custom — write a `MemoryAdapter` shim that intercepts CLAUDE.md / MEMORY.md / ai/memory/* reads and serves from vector store instead. NO file fallback.
- **Expected delta:** STRONGLY NEGATIVE expected: -20 to -40% on M3 (stale-fact rejection — vector DBs lose temporal anchoring), -15-30% on M1 (precision retrieval often loses load-bearing exact strings), -5-10% on M4. This arm exists to EMPIRICALLY CONFIRM the survey's striking finding.
- **Best datasets:** LongMemEval (#9, M1/M3/M4), FreshQA (#16, M3), RealTimeQA (#17, M3), LoCoMo (#10, M1+M2).

**Layer M totals: 5 arms.**

---

### 2.6 Layer: sub-agents

**What the convergent harness does:** Sequential context-isolated `Task` tool, parent waits (survey §1.7, §4.6-B). Survey §3.3 first bullet: "the convergent answer is wrong about parallelism — Cursor 2 (8 parallel) and Claude Code's `/go` wave model both do best-of-N."

#### Arm SA-1: NONE — single agent only (BASELINE-ALT)
- **Description:** Disable Task tool. Single agent does everything. Continue + base Aider pattern.
- **Implementation:** Wrapper flag: `--no-task-tool`. Strip the `Task` tool from allowlist.
- **Expected delta:** `0.0` reference for THIS layer (this is the "no sub-agents" baseline; we use it instead of CL-1's BASELINE-V0 here because BASELINE-V0 has Task ON).
- **Best datasets:** All v3 axes — but interpreted as "what does it cost to NOT have sub-agents."

#### Arm SA-2: Sequential context-isolation (CONVERGENT)
- **Description:** Standard Claude Code Task tool. One sub-agent at a time, parent waits, sub-agent context isolated, returns 1-2K summary.
- **Implementation:** Default Claude Code. No change. Set `WAVE_MAX_PARALLEL=1`.
- **Expected delta:** +5-15% over SA-1 on long tasks (context isolation prevents pollution). Token cost ↑ ~30% (sub-agent has its own context).
- **Best datasets:** SWE-bench Verified (#1), AppWorld (#25), GAIA (#18), MLR-Bench (#50).

#### Arm SA-3: Parallel best-of-N with worktree isolation
- **Description:** Cursor 2 / `/go` wave model — N parallel agents in git worktrees, best result selected (survey §1.6, §3.3 first bullet).
- **Implementation:** User's `/go` Phase 5 with `WAVE_MAX_PARALLEL=4`. Selection logic: shadow-verifier scores each result, select highest-scoring. For Cursor 2 cell, use Cursor's native 8-agent mode.
- **Expected delta:** +10-25% on hard tasks (BS-3, BS-5, harder SWE-bench Verified subset). Token cost ↑ N× (4× for our default). Wall-clock ~same as sequential due to parallelism. CRITICAL DEPENDENCY: requires verification arm V-D or V-C to score outputs (else nonsensical — see §3).
- **Best datasets:** SWE-bench Verified hard subset (#1), SWE-bench Pro (#2), SWE-Lancer (#8, BS-3), MLR-Bench (#50, BS-2/BS-3), harness-bench/BS-5 (#66 subset).

#### Arm SA-4: Specialized verification subagent
- **Description:** Replit Agent 3 pattern — separate testing subagent (survey §1.8 last bullet). Implementation agent writes code; verification agent runs tests on isolated context (no pollution).
- **Implementation:** User's `smoke-test` agent + `shadow-verifier` haiku per Phase 6 of `/go`. Wrapper flag: `--verify-subagent=on`.
- **Expected delta:** +10-15% on verification-sensitive tasks (FM-1 stuck-loops detected; FM-5 destructive prevented). Token cost ↑ ~15% (verification context). Wall-clock ↑ ~20% (sequential verify step).
- **Best datasets:** SWE-bench Verified (#1), Aider Polyglot (#4), harness-bench/FM-1 (#61), tau2-bench (#21, FM-5), harness-bench/FM-5 (#65).

#### Arm SA-5: Deep chaining (sub-sub-agents)
- **Description:** User's `/go` "deep chaining" pattern — sub-agents spawn their own sub-agents (survey §3.3 + user CLAUDE.md "Deep Chaining" section).
- **Implementation:** User's `/go` with `MAX_AGENT_DEPTH=3`. Naturally on by default; ablate by capping at depth=1.
- **Expected delta:** +5-12% on highly composite tasks (MLR-Bench, MLE-bench). -3-5% on simple tasks (overhead). Token cost ↑ moderately (sub-sub-context bounded by parent budget).
- **Best datasets:** MLR-Bench (#50), MLE-bench (#36), PaperBench (#51), harness-bench/BS-5 (#66 subset).

**Layer SA totals: 5 arms.**

---

### 2.7 Layer: safety

**What the convergent harness does:** Hooks intercept Pre/Post tool with BLOCK/WARN at zero token cost (survey §1.7, §3.2 second bullet + user CLAUDE.md 68-rule enforcement).

#### Arm S-1: Prompt-only + dry-run flag (Aider baseline)
- **Description:** No interception. User confirmation per write op. `.aiderignore` filter. `dry_run` flag. Survey §1.1 + §4.7-A.
- **Implementation:** SWAP — Aider as harness. For Claude Code cells: disable hooks via `~/.claude/settings.json` `hooks: {}`.
- **Expected delta:** -5-10% on FM-5 (destructive-action) — without hook intercept, agent more likely to commit destructive ops without flagging. +5% on FM-1 (no hook overhead). Note: this is RISKY in production; we run in sandbox only.
- **Best datasets:** tau2-bench (#21, FM-5), AppWorld (#25), OSWorld (#22), harness-bench/FM-5 (#65).

#### Arm S-2: Per-tool policy function
- **Description:** Continue's `tool.evaluateToolCallPolicy()` per-tool — single policy file (survey §1.4, §4.7-B). Lighter than hooks but more structured than prompt-only.
- **Implementation:** SWAP — Continue as harness. Or shim into Claude Code via single policy file at `~/.claude/policies/per-tool.json`.
- **Expected delta:** Mostly flat. Marginal benefit on FM-5. Token cost ~0 (policy enforced before model call).
- **Best datasets:** harness-bench/FM-5 (#65), tau2-bench (#21).

#### Arm S-3: Hooks intercept Pre/Post (BASELINE)
- **Description:** User's harness — 68 rules across 13 categories, fires at zero token cost. BLOCK on dangerous, WARN on suspicious. Per-agent allowlists.
- **Implementation:** Default Claude Code + user's harness 68-rule enforcement.
- **Expected delta:** `0.0` reference.
- **Best datasets:** All v3 axes.

#### Arm S-4: Inspector pipeline + LLM adversary check
- **Description:** Goose's 5-stage inspector pipeline + `AdversaryInspector` LLM-based prompt-injection check (survey §1.5 + §4.7-D). Most paranoid setup reviewed.
- **Implementation:** SWAP — Goose as harness with all 5 inspectors enabled + `~/.config/goose/adversary.md` populated. For Claude Code cells, add an LLM-based pre-tool-call check via custom hook that calls Claude Haiku to score args (~$0.0005/call).
- **Expected delta:** +10-25% on cybersec adversarial datasets (CyberSecEval 2/3 visual prompt injection). -3-8% on non-adversarial tasks (LLM check overhead). Token cost: per-call $0.0005 × tool-calls-per-task. Wall-clock ↑ ~15% (LLM check latency).
- **Best datasets:** CyberSecEval 3 (#39, FM-2 visual prompt injection), CyberSecEval 2 (#40), Cybench (#37, FM-1+M4), NYU CTF Bench (#38), tau2-bench (#21, FM-5).

#### Arm S-5: Sandbox container + runtime cap (no in-loop intercept)
- **Description:** OpenHands / Devin / Replit pattern — sandboxed Docker runtime + runtime cap (45min for Devin, 200min for Replit). Survey §1.2, §1.8.
- **Implementation:** SWAP — OpenHands as harness with `runtime=docker`. Set `MAX_RUNTIME_MINUTES=45`.
- **Expected delta:** +5-15% on FM-5 (containment prevents exfiltration). +0-5% on outcome quality. Token cost flat. Wall-clock ↑ 15-30% (container startup).
- **Best datasets:** OSWorld (#22), AppWorld (#25), MLE-bench (#36 — Docker required anyway), Cybench (#37).

**Layer S totals: 5 arms.**

---

### 2.8 Layer: verification

**What the convergent harness does:** Inline lint+test reflection + post-hoc shadow-verifier haiku (survey §1.7). Survey §3.1 fourth bullet: "verification = what separates demo from product."

#### Arm V-1: NONE / telemetry only (Continue baseline)
- **Description:** No verification loop. Just emit telemetry. Survey §1.4, §4.8-A.
- **Implementation:** Wrapper — disable shadow-verifier (`--no-shadow-verify`), disable smoke-test, disable inline lint+test reflection.
- **Expected delta:** -15-25% across the board on tasks that have testable outputs (SWE-bench, BigCodeBench). This is the "demo not product" reference.
- **Best datasets:** All v3 axes — establishes the verification-cost frontier.

#### Arm V-2: Loop-detector + stuck-recovery
- **Description:** OpenHands `StuckDetector._is_stuck()` + Goose `compact_messages` retry. Detects repetition, recovers via compaction or backtrack. Survey §1.2, §1.5, §4.8-B.
- **Implementation:** Wrapper — enable user's `watchdog.sh` hook (already in harness `~/.claude/hooks/watchdog.sh` per CLAUDE.md). Set `STUCK_THRESHOLD_MS=600000` (10min).
- **Expected delta:** +5-10% on FM-1 (stuck-loops) — primary purpose. +0 to +3% elsewhere. Token cost flat (no model calls).
- **Best datasets:** Aider Polyglot (#4, FM-1), SWE-bench Verified (#1), harness-bench/FM-1 (#61).

#### Arm V-3: Inline reflect-on-lint+test (Aider's auto_lint+auto_test)
- **Description:** Aider pattern — after every edit, run lint + test; on failure, append diagnostic to next prompt. Survey §1.1, §4.8-C.
- **Implementation:** Wrapper — enable post-tool hook that runs `npm run lint && npm test` (or language-equivalent) after every Edit/Write tool call. Inject failure into next prompt.
- **Expected delta:** +10-25% on code tasks with test suites (SWE-bench, BigCodeBench, Aider Polyglot). +0 on non-code tasks. Token cost ↑ ~20-40% (re-feeding test output). Wall-clock ↑ 50-100% (test runs).
- **Best datasets:** SWE-bench Verified (#1), SWE-bench Pro (#2), BigCodeBench (#5), Aider Polyglot (#4), MLE-bench (#36).

#### Arm V-4: Browser/REPL self-test in dedicated subagent (BASELINE part 1)
- **Description:** Replit Agent 3 + Cursor 2 native browser pattern (survey §1.6, §1.8, §4.8-D). User's `smoke-test` + `exploit-scan` are the harness equivalents. Sub-agent runs Playwright/REPL against the implementation; verifies functionality + DOM.
- **Implementation:** Default for user's `/go` Phase 7 smoke-test agent (6-check + self-heal max 3). Wrapper flag: `--smoke-test=off` to ablate.
- **Expected delta:** +15-25% on web/UI tasks (WebArena, VisualWebArena). +5-10% on backend tasks (smoke-test catches deploy errors). Token cost ↑ ~25% (browser context). Wall-clock ↑ ~40%.
- **Best datasets:** WebArena (#23, M4+FM-1+FM-5), VisualWebArena (#24, M2+M4+FM-1), AssistantBench (#26), AppWorld (#25), OSWorld (#22).

#### Arm V-5: Post-hoc shadow audit (BASELINE part 2)
- **Description:** User's `shadow-verifier` haiku — after implementer completes, haiku-based audit checks output matches request, tests ran, no regressions (~$0.001/check). Survey §1.7.
- **Implementation:** Default for user's `/go` Phase 6. Wrapper flag: `--shadow-verify=off` to ablate.
- **Expected delta:** +3-8% on standard+ complexity tasks. +0 on trivial. Token cost ↑ ~$0.001/agent (negligible).
- **Best datasets:** SWE-bench Verified (#1), Aider Polyglot (#4), MLR-Bench (#50), AppWorld (#25), GAIA (#18).

**Layer V totals: 5 arms.**

---

### 2.x Per-layer arm count summary

| Layer | Arms | IDs |
|-------|------|-----|
| Control loop | 4 | CL-1, CL-2, CL-3, CL-4 |
| Reasoning | 4 | R-1, R-2, R-3, R-4 |
| Tool surface | 5 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| Tool catalog | 4 | TC-1, TC-2, TC-3, TC-4 |
| Memory | 5 | M-1, M-2, M-3, M-4, M-5 |
| Sub-agents | 5 | SA-1, SA-2, SA-3, SA-4, SA-5 |
| Safety | 5 | S-1, S-2, S-3, S-4, S-5 |
| Verification | 5 | V-1, V-2, V-3, V-4, V-5 |
| **TOTAL ARMS** | **37** | (5 are baselines that count as 0-delta references) |

**Net non-baseline arms (the actual "ablation experiments"):** 37 - 8 baselines (one per layer) = **29 ablation arms**. Plus 5 black-box harness anchors (§7) and 5 hand-picked 2-axis interactions (§3) = **39 total experiment cells per dataset**.

---

## 3. Cross-layer interaction sanity matrix

Some arms make NO sense without other arms enabled. We document these as DEPENDENCIES so we don't run nonsensical cells.

### 3.1 Hard dependencies (don't run without)

| Arm | Requires | Why |
|-----|----------|-----|
| **SA-3** (parallel best-of-N) | **V-3, V-4, OR V-5** (verification) | Best-of-N requires an oracle to pick best output. Without verification, "best-of-N" is "random-of-N." Survey §3.3 first bullet. |
| **SA-4** (verification subagent) | **V-3, V-4, OR V-5** (verification arm enabled at all) | The subagent IS a verification mechanism; pairing with V-1 (none) is contradiction. |
| **CL-4** (multi-agent orchestrator) | **SA-2, SA-3, SA-4, OR SA-5** (sub-agents enabled) | Orchestrator with no sub-agents = sequential ReAct = CL-1. |
| **R-4** (echo thinking) | **non-Anthropic provider** | Anthropic API doesn't expose `reasoning_content` in the cross-turn way Goose does. Run as Goose-only cell. |
| **TC-4** (skill-router) | **SA-2 or higher** (sub-agents) | Skill-router is itself a sub-agent step. |
| **TS-3** (pure-MCP) | **MCP servers configured** | Trivially obvious but worth flagging — the arm is meaningless without ≥3 MCP servers loaded. |

### 3.2 Soft dependencies (run, but flag for interpretation)

| Arm | Soft-requires | Why |
|-----|--------------|-----|
| **M-4** (RAG-indexed) | **TC-1 or TC-4** (deferred/intent-filtered) | RAG injection per turn pairs poorly with TC-2 (static eager-load) — the eager-loaded tool surface and the RAG context compete for budget. |
| **CL-2** (reflection bound) | **V-3** (inline reflect-on-test) | Aider's reflection IS the lint+test loop in V-3. Running CL-2 alone (no V-3) reproduces only HALF of the Aider mechanism. |
| **S-4** (LLM adversary) | **TS-3 OR TS-2** (broad surface) | If the surface is minimal (BASELINE TS-1), there are fewer attack vectors → S-4's value drops. |

### 3.3 Hand-picked 2-axis interactions (run as bonus cells)

These 5 interactions are run AS ADDITIONS to the vary-one-hold-seven matrix. They probe the most informative 2-axis questions raised by survey §3.3.

| Interaction | Probes | Datasets | Cells |
|-------------|--------|----------|-------|
| **SA-3 × V-4** | "Does best-of-N parallel sub-agents dominate inline reflection when verification is browser-loop?" — survey §3.3 first bullet test | SWE-bench Verified hard subset (#1), WebArena (#23) | 2 |
| **SA-3 × V-3** | "Is Aider-style inline reflect-on-test enough oracle for best-of-N?" | SWE-bench Verified (#1), BigCodeBench (#5) | 2 |
| **TC-1 × M-4** | "Does ToolSearch + RAG synergize, or do they fight for context budget?" | RepoBench (#6), Long Code Arena (#7) | 2 |
| **R-2 × CL-4** | "Can multi-agent orchestrator compensate for thinking-OFF on individual agents?" | MLR-Bench (#50), harness-bench/BS-3 (#66) | 2 |
| **S-4 × CL-4** | "Does adversary-inspector matter more in multi-agent setups (more attack surface from cross-agent communication)?" | tau2-bench (#21), CyberSecEval 3 (#39) | 2 |

**5 interactions × 2 datasets = 10 bonus cells per tier.**

---

## 4. Per-arm corpus mapping

For each ablation arm, the dataset(s) most likely to expose its differential. Sourced from corpus catalog §3.1-3.3 axis maps.

### 4.1 Mapping table (all 29 non-baseline arms × best datasets)

| Arm | Primary axis | Best datasets (corpus #) | Why |
|-----|-------------|---------------------------|-----|
| CL-2 (reflection bound) | FM-1 | Aider Polyglot (#4), SWE-bench Verified (#1), harness-bench/FM-1 (#61), MLE-bench (#36) | Stuck-loop tasks where reflection breaks the loop |
| CL-3 (event-driven) | M4 | AppWorld (#25), TAU-bench (#20), OSWorld (#22) | Procedural memory benefits from event-publish/subscribe |
| CL-4 (multi-agent orch) | BS-5, BS-3 | harness-bench/BS-5 (#66), MLR-Bench (#50), SWE-Lancer (#8), harness-bench/BS-3 (#66) | Recombination + cross-paper synthesis |
| R-2 (thinking OFF) | BS-1, BS-2 | ConceptARC (#47), AnalogyBench (#48), GPQA Diamond (#34), MLR-Bench (#50), harness-bench/FM-3 (#63), harness-bench/FM-4 (#64) | Bisociation hurt by no thinking; condensation/drift may improve |
| R-3 (plan-then-execute) | M4 | PlanBench (#28), AppWorld (#25), SWE-Lancer (#8), TAU-bench (#20), OSWorld (#22) | Multi-step procedural with explicit plan helps |
| R-4 (echo thinking) | M4 | AppWorld (#25), TAU-bench (#20), tau2-bench (#21) | Procedural with chain preservation |
| TS-2 (wide flat) | mixed | SWE-bench Verified (#1), BigCodeBench (#5), AppWorld (#25), AssistantBench (#26) | Broad tool needs; tradeoff on selection |
| TS-3 (pure-MCP) | M4, BS-4 | ToolBench (#27), AppWorld (#25), BIOMNI (#29) | MCP-rich domains |
| TS-4 (text-native diffs) | code | SWE-bench Verified (#1), BigCodeBench (#5), Aider Polyglot (#4) | Aider's home turf |
| TS-5 (Bash-only) | code, FM-1 | SWE-bench Verified (#1), Aider Polyglot (#4), harness-bench/FM-1 (#61), AssistantBench (#26) | Stress test of file-tool removal |
| TC-2 (static eager-load) | M5, FM-2 | BABILong (#11), RULER (#12), InfiniteBench (#13), RepoBench (#6), Long Code Arena (#7), harness-bench/FM-2 (#62) | Long-context where token bloat shows |
| TC-3 (dynamic per-prompt) | M5 | BABILong (#11), RepoBench (#6), Long Code Arena (#7) | Conditional surface trim shows mid-length |
| TC-4 (skill-router) | M4 | AppWorld (#25), AssistantBench (#26), GAIA (#18), TAU-bench (#20) | Intent-filtered surface for tool-heavy procedural |
| M-2 (auto-summary) | M5, FM-3 | LongMemEval (#9), LoCoMo (#10), BABILong (#11), harness-bench/FM-3 (#63), RULER (#12) | Compaction directly tested |
| M-3 (event log + checkpoint) | FM-1, M4 | SWE-bench Verified (#1), Aider Polyglot (#4), AppWorld (#25), MLE-bench (#36), OSWorld (#22) | Backtrack-and-retry on failure |
| M-4 (RAG-indexed) | M1, M5 | RepoBench (#6), Long Code Arena (#7), SWE-bench Verified (#1), SWE-bench Pro (#2), SWE-Lancer (#8) | Repo-scale retrieval |
| M-5 (vector-only adv probe) | M1, M3 | LongMemEval (#9), FreshQA (#16), RealTimeQA (#17), LoCoMo (#10) | Force vector-only failure modes |
| SA-2 (sequential isolation) | mixed | SWE-bench Verified (#1), AppWorld (#25), GAIA (#18), MLR-Bench (#50) | Context-isolation benefit |
| SA-3 (parallel best-of-N) | BS-3, BS-5 | SWE-bench Verified hard (#1), SWE-bench Pro (#2), SWE-Lancer (#8), MLR-Bench (#50), harness-bench/BS-5 (#66) | Hard tasks benefit from N attempts |
| SA-4 (verify subagent) | FM-1, FM-5 | SWE-bench Verified (#1), Aider Polyglot (#4), harness-bench/FM-1 (#61), tau2-bench (#21), harness-bench/FM-5 (#65) | Verification primary purpose |
| SA-5 (deep chaining) | BS-3, BS-5 | MLR-Bench (#50), MLE-bench (#36), PaperBench (#51), harness-bench/BS-5 (#66) | Deeply composite tasks |
| S-1 (prompt-only) | FM-5 | tau2-bench (#21), AppWorld (#25), OSWorld (#22), harness-bench/FM-5 (#65) | No intercept → destructive measurable |
| S-2 (per-tool policy) | FM-5 | harness-bench/FM-5 (#65), tau2-bench (#21) | Light intercept |
| S-4 (LLM adversary) | FM-2, FM-5 | CyberSecEval 3 (#39), CyberSecEval 2 (#40), Cybench (#37), NYU CTF Bench (#38), tau2-bench (#21) | Adversarial primary purpose |
| S-5 (sandbox container) | FM-5 | OSWorld (#22), AppWorld (#25), MLE-bench (#36), Cybench (#37) | Containment primary purpose |
| V-1 (none) | mixed | All v3 — establishes "demo not product" floor | Reference for verification's contribution |
| V-2 (loop detector) | FM-1 | Aider Polyglot (#4), SWE-bench Verified (#1), harness-bench/FM-1 (#61) | Stuck-loop detection |
| V-3 (inline lint+test) | code | SWE-bench Verified (#1), SWE-bench Pro (#2), BigCodeBench (#5), Aider Polyglot (#4), MLE-bench (#36) | Test-driven verification |
| V-4 (browser/REPL self-test) | M4, web | WebArena (#23), VisualWebArena (#24), AssistantBench (#26), AppWorld (#25), OSWorld (#22) | UI verification |
| V-5 (shadow audit) | mixed | SWE-bench Verified (#1), Aider Polyglot (#4), MLR-Bench (#50), AppWorld (#25), GAIA (#18) | Post-hoc audit value |

### 4.2 Axis-coverage cross-reference

Pulled directly from corpus catalog §3.1-3.3:

| Axis | Datasets covering | Arms primarily probing |
|------|-------------------|-----------------------|
| **M1** (cross-window retrieval) | LongMemEval (#9), LoCoMo (#10), ConvFinQA (#45), AssistantBench (#26), RULER (#12), RepoBench (#6) | M-2, M-4, M-5 |
| **M2** (cross-modal) | LoCoMo (#10), MMLongBench-Doc (#14), MileBench (#15), VisualWebArena (#24), SWE-bench Multimodal (#3), FinanceBench (#43), harness-bench/M2 (#60) | (no dedicated arm — covered by general harness M2 capability) |
| **M3** (stale-fact rejection) | LongMemEval (#9), FreshQA (#16), RealTimeQA (#17) | M-5 (adv probe) |
| **M4** (procedural memory) | AppWorld (#25), TAU-bench (#20), tau2-bench (#21), OSWorld (#22), WebArena (#23), VisualWebArena (#24), ToolBench (#27), PlanBench (#28), SWE-Lancer (#8), MLE-bench (#36) | CL-3, R-3, R-4, TC-4, M-3, SA-2, V-4 |
| **M5** (working-memory eviction) | BABILong (#11), RULER (#12), InfiniteBench (#13), RepoBench (#6), Long Code Arena (#7), BigCodeBench (#5), MMLongBench-Doc (#14), MileBench (#15), SWE-bench Verified (#1), SWE-bench Pro (#2), harness-bench/FM-2 (#62) | TC-2, TC-3, M-2, M-4 |
| **FM-1** (stuck-loops) | Aider Polyglot (#4), SWE-bench Verified (#1), WebArena (#23), VisualWebArena (#24), OSWorld (#22), Cybench (#37), NYU CTF Bench (#38), AssistantBench (#26), MLE-bench (#36), harness-bench/FM-1 (#61) | CL-2, M-3, V-2, V-3, SA-4, TS-5 |
| **FM-2** (env-hallucination >700K) | BABILong (#11), RULER (#12), InfiniteBench (#13), CyberSecEval 2/3 (#39, #40), harness-bench/FM-2 (#62) | TC-2, S-4 |
| **FM-3** (condensation loops) | harness-bench/FM-3 (#63) — primary | M-2, R-2 |
| **FM-4** (KV-cache drift) | harness-bench/FM-4 (#64) — primary | R-2 |
| **FM-5** (destructive-action under conflict) | tau2-bench (#21), AppWorld (#25), OSWorld (#22), WebArena (#23), NYU CTF Bench (#38), harness-bench/FM-5 (#65) | S-1, S-2, S-4, S-5, SA-4 |
| **BS-1** (cross-domain analogy) | ConceptARC (#47), AnalogyBench (#48), E-MAGIC (#49), BigCodeBench (#5), AssistantBench (#26), Long Code Arena (#7) | R-2 |
| **BS-2** (frame-shift) | BIOMNI (#29), ChemBench (#33), GPQA Diamond (#34), MLR-Bench (#50), E-MAGIC (#49), harness-bench/BS-2-to-5 (#66) | R-2, CL-4 |
| **BS-3** (cross-paper synthesis) | OpenScholar/ScholarQABench, PaperQA2, BIOMNI (#29), PubMedQA (#32), LegalBench (#41), FinanceBench (#43), MLR-Bench (#50), PaperBench (#51), harness-bench/BS-3 (#66) | CL-4, SA-3, SA-5 |
| **BS-4** (tool-output bisociation) | ToolBench (#27), tau2-bench (#21), AppWorld (#25), FinQA (#44), harness-bench/BS-4 (#66) | TS-3 |
| **BS-5** (solution recombination) | BigCodeBench (#5), Long Code Arena (#7), SWE-Lancer (#8), MLE-bench (#36), harness-bench/BS-5 (#66) | CL-4, SA-3, SA-5 |

---

## 5. Scoring per arm

Per cell, we capture FOUR metric tiers. All written to `logs/<run>/cells/<cell-id>.jsonl`.

### 5.1 Primary: pass@1 success
- Metric: `pass@1` — the dataset's native success metric (test-pass for SWE-bench, exact-match for MedQA, model-graded for LongMemEval, etc.).
- Aggregation: per arm, mean across (datasets-per-arm × runs-per-cell) cells.
- Comparison: report `delta-vs-BASELINE-V0` with bootstrap 95% CI.

### 5.2 Secondary: cost + latency
- `total_input_tokens`, `total_output_tokens`, `total_thinking_tokens` (where applicable)
- `wall_clock_seconds` (Inspect AI provides this)
- `tool_calls_count`, `tool_calls_failed`
- Cost: derive `usd_equivalent` from token counts × model pricing table (table lives at `harness-bench/scoring/pricing.yaml`)

### 5.3 Tertiary: METR time-horizon (per arm)
- METR's Hours Equivalent metric — for which task length (in equivalent human hours) does this arm achieve 50% pass rate?
- Compute via: bin tasks by estimated human-completion-time (proxy: word count of task spec × difficulty multiplier from corpus catalog), measure pass rate per bin, find 50% crossover.
- Output: `metr_50pct_hours` per arm.

### 5.4 Quaternary: Pareto position
- 2D plot: x-axis = `usd_equivalent`, y-axis = `pass@1`.
- Each arm becomes a point; baseline at origin (0,0) of the delta plot.
- Pareto-frontier arms are those NOT strictly dominated.
- Output: `pareto_dominated_by` (list of arms) per arm.

### 5.5 Composite "contribution score" per layer
- Per layer, compute `max_arm_pass@1 - min_arm_pass@1` across that layer's arms, averaged across all datasets-per-arm.
- This is the LAYER CONTRIBUTION — how much variance is unlocked by varying this layer.
- Output: per-layer ranking (e.g., "verification contributes 18.4 pp; tool catalog contributes 4.2 pp; …"). This is the headline harness-bench result.

### 5.6 Bisociation/memory/pain-mode breakdowns
- Aggregate by axis family: report per-arm pass@1 split into M-axes, FM-axes, BS-axes domains.
- Surface the harness-axis fit: e.g. "arm SA-3 dominates BS-axes but loses on M-axes; arm M-4 dominates M-axes but neutral on BS."

---

## 6. Wrapper-level vs swap-level ablations

Survey §5 documents which components are HARD to ablate without forking. Per arm we mark the strategy.

### 6.1 Strategy classification per arm

| Arm | Strategy | Toggle |
|-----|----------|--------|
| CL-1 | wrapper | (default) |
| CL-2 | wrapper | post-tool hook injects observations + `--auto-lint --auto-test --max-reflections 3` for Aider cell |
| CL-3 | **swap** | run OpenHands V0 as harness |
| CL-4 | wrapper | `WAVE_MAX_PARALLEL=4`, `--orchestrator=on` |
| R-1 | wrapper | (default) |
| R-2 | wrapper | API param `thinking={"type":"disabled"}` via `--no-thinking` flag |
| R-3 | **swap** | Cline as harness, mode=plan-then-act |
| R-4 | **swap** | Goose as harness with reasoning_content preserved |
| TS-1 | wrapper | (default) |
| TS-2 | **swap** | Cline as harness, `--no-mcp` |
| TS-3 | **swap** | Goose as harness |
| TS-4 | **swap** | Aider as harness, `--edit-format editblock` (sub-arm: also test udiff/whole/patch) |
| TS-5 | wrapper | `--tool-allowlist=Bash,Task,WebFetch,WebSearch` via hook |
| TC-1 | wrapper | (default v2.1.69+) |
| TC-2 | wrapper | downgrade Claude Code to v2.1.68 (or `--no-tool-search` if exposed); for non-CC harnesses, this is native |
| TC-3 | **swap** | Cline as harness |
| TC-4 | wrapper | `--skill-router=on` + ensure user's `/go` Phase 0 router runs |
| M-1 | wrapper | (default) |
| M-2 | wrapper | enable `/compact` skill on auto-trigger; for swap cells, use harness's native compaction (Aider/Goose/Cline) |
| M-3 | **swap** | Cline (checkpointManager ON) or OpenHands (StateTracker default) |
| M-4 | wrapper | `--rag-on-turn=on` invokes user's `codesight search` per model turn |
| M-5 | wrapper (custom shim) | MemoryAdapter intercepts file reads, serves from vector store |
| SA-1 | wrapper | strip Task tool from allowlist via `--no-task-tool` |
| SA-2 | wrapper | (default) |
| SA-3 | wrapper | `WAVE_MAX_PARALLEL=4` (user's `/go`) or Cursor 2 native 8-agent mode (cell pin) |
| SA-4 | wrapper | `--verify-subagent=on` (user's smoke-test agent) |
| SA-5 | wrapper | `MAX_AGENT_DEPTH=3` (default in user's `/go`); ablate by capping at 1 |
| S-1 | wrapper | disable hooks via `~/.claude/settings.json` `hooks: {}` for the cell |
| S-2 | **swap** | Continue as harness, or shim policy file into Claude Code |
| S-3 | wrapper | (default) |
| S-4 | wrapper + LLM hook | post-tool hook calls Claude Haiku to score args |
| S-5 | **swap** | OpenHands with `runtime=docker`, `MAX_RUNTIME_MINUTES=45` |
| V-1 | wrapper | `--no-shadow-verify --no-smoke-test --no-inline-reflect` |
| V-2 | wrapper | enable `watchdog.sh`, `STUCK_THRESHOLD_MS=600000` |
| V-3 | wrapper | post-tool hook runs lint+test, injects failure into next prompt |
| V-4 | wrapper | (default for `/go` Phase 7) |
| V-5 | wrapper | (default for `/go` Phase 6) |

**Wrapper:24, Swap:13** out of 37 arms. Wrappers are CHEAP (env var or hook flag); swaps require running a different harness binary entirely.

### 6.2 Practical implication

The 13 swap arms drive the harness-binary-mix in our run plan: we need installations of Aider, Cline, OpenHands, Goose, Continue available on Spark. Per harness — install steps + image size — recorded in `harness-bench/harnesses/INSTALL.md`. Spark disk overhead: ~8 GB across all 5 (Continue ~1 GB, Cline ~1 GB, Aider ~500 MB, OpenHands ~3 GB w/ Docker base, Goose ~2 GB w/ Rust toolchain).

For Cursor 2 + Devin + Replit Agent 3, see §7.

---

## 7. Black-box harness handling (Cursor 2, Devin, Replit Agent 3)

These three harnesses are closed-source. We CANNOT ablate INSIDE them — only treat as oracles. Survey §5.1 sets the workaround.

### 7.1 What arms apply

For each black-box harness, the only "ablation" we run is the SINGLE harness-as-cell. We cannot decompose. Per harness:

| Harness | Knobs we can flip | Cells per dataset |
|---------|-------------------|-------------------|
| **Cursor 2 / Composer 2** | mode (composer-2 vs composer-1), agent count (1, 2, 4, 8 parallel), browser tool ON/OFF | 4 cells (a vs b interactions) |
| **Devin (Cognition)** | NONE public — single API call mode | 1 cell |
| **Replit Agent 3** | effort mode (Economy / Power / Turbo) | 3 cells |

Total black-box cells per dataset: 4 + 1 + 3 = **8 cells per dataset**.

### 7.2 How we score them

Same input task, same scoring criteria as open-source harness cells. We treat each as an "anchor point" on the Pareto frontier (cost vs quality). Per-cell metrics:
- `pass@1` (same scorer)
- `usd_equivalent` (vendor-billed cost — for Devin/Replit, use API billing; for Cursor, estimate from session activity)
- `wall_clock_seconds`
- NO inspection of internals (no token counts, no tool-call counts).

### 7.3 Their value

The black-box anchors define the **upper bound** on the capability/cost frontier achievable in the field — we plot them on the same Pareto chart as our open-source-decomposed cells. If our convergent BASELINE-V0 achieves SWE-bench Verified pass@1 within (e.g.) 5pp of Devin at a fraction of the cost, that's a primary harness-bench finding.

### 7.4 Per-anchor-harness sample budget

Devin and Replit Agent 3 are PAID per-session — Devin lists ~$500/seat/mo plus per-session compute; Replit Agent 3's $0.20 median session cost (survey §1.8) makes it the more accessible. Budget per release:
- Devin: 50 sessions × ~$15 each = ~$750
- Replit Agent 3: 50 sessions × $0.20 = ~$10
- Cursor 2: 100 sessions × ~$0.50 = ~$50

Total black-box vendor billing: ~$810/release. Trivial vs total compute budget §8.

---

## 8. Compute budget

### 8.1 Cell count per tier

Cells = single-layer-arms + interactions + black-box-anchors, all multiplied by datasets-per-arm × runs-per-cell.

| Component | Arms | Datasets-per-arm (v1 / v2 / v3) | Runs-per-cell (v1 / v2 / v3) | Cells (v1 / v2 / v3) |
|-----------|------|--------------------------------|------------------------------|---------------------|
| Single-layer arms (open-source, swap+wrapper) | 32 (29 non-baseline + 8 baselines × 1 dataset overlap = 30 effective) | 1 / 4 / 10 | 1 / 3 / 5 | 30 / 360 / 1500 |
| 2-axis interactions | 5 | 2 / 2 / 4 | 1 / 3 / 5 | 10 / 30 / 100 |
| Black-box harness anchors | 8 cells × 1 harness-cell-per-dataset | 1 / 5 / 10 | 1 / 2 / 3 | 8 / 80 / 240 |
| Constructed-axis baseline (FM-3, FM-4, BS-2-to-5 — extra coverage) | 6 axes | 1 / 1 / 2 | 1 / 2 / 3 | 6 / 12 / 36 |
| **TOTAL CELLS** | | | | **54 / 482 / 1876** |

Round up for "+10% overhead for retries on Spark transient failures" → final estimate:

| Tier | Cells (with 10% buffer) |
|------|-------------------------|
| **v1-smoke** | ~60 cells |
| **v2-broad** | ~530 cells |
| **v3-full** | ~2,060 cells |

(Earlier TL;DR estimate of 120/720/3150 was based on a 3-5 datasets-per-arm pessimistic bound. Refined here.)

### 8.2 Per-cell compute estimate

Median cell on SWE-bench-style task:
- Input tokens: ~25K (system + tools + repo context + task)
- Output tokens: ~5K (model response + thinking)
- Tool-call wall-clock: ~30s × ~6 calls/task = 180s
- Total wall-clock per cell: ~180-300s (median)

Long-context cells (BABILong >700K, RULER 1M):
- Input tokens: 700K-1M
- Output: ~10K
- Wall-clock: ~600-900s (input streaming dominates)

Web/UI cells (WebArena, OSWorld):
- Wall-clock: ~300-600s (browser actions dominate)

Mean cell wall-clock estimate: **~240s** (4 minutes).

### 8.3 Spark concurrency + wall-clock

Spark has 119 GB RAM, 4 GPU slots, 24 CPU cores. Practical concurrency for harness-bench eval cells (mostly LLM-API-bound, not GPU-bound except for any local model variants):

- Default: 4 parallel cells (one per GPU slot if cell uses local model; otherwise can scale higher).
- For pure-API cells (most arms): 8-12 parallel safe (rate-limited by Anthropic/OpenAI API quotas).
- We assume sustained 4-cell parallelism for the wall-clock estimate.

| Tier | Cells | Mean wall-clock per cell | Spark slots | Sequential time | Wall-clock @ 4 slots |
|------|-------|-------------------------|-------------|-----------------|---------------------|
| v1-smoke | 60 | 240s | 4 | 14,400s = 4h | **1h** |
| v2-broad | 530 | 240s | 4 | 127,200s = 35h | **9h** |
| v3-full | 2,060 | 240s | 4 | 494,400s = 137h | **35h** |

Wall-clock estimates assume no Spark contention from `mhough`'s workloads (per user CLAUDE.md `feedback_never_touch_mhough.md` — Spark is shared). In practice add 30-50% slack for shared-resource scheduling:

- v1-smoke: ~1.5h wall-clock
- v2-broad: ~14h wall-clock
- v3-full: ~50h wall-clock

(Updates the TL;DR estimate from 6h/42h/180h — earlier estimate was overly pessimistic on cell count and underestimated parallelism gain.)

### 8.4 API cost estimate

Cell-level cost (median):
- Anthropic Claude Opus 4.7: $15/M input, $75/M output
- Per cell (25K in + 5K out): $0.375 + $0.375 = ~$0.75 input cost
- Plus shadow-verify (haiku ~$0.001) + smoke-test (~$0.05) = +$0.05
- Plus model-graded scoring (Sonnet 4.6 judge ~25K in + 1K out = ~$0.10)
- **Median per-cell cost: ~$0.90**

| Tier | Cells | Per-cell cost | Total API cost |
|------|-------|---------------|---------------|
| v1-smoke | 60 | $0.90 | $54 |
| v2-broad | 530 | $0.90 | $477 |
| v3-full | 2,060 | $0.90 | $1,854 |

Plus black-box vendor billing (§7.4): +$810 for v3-full.
Plus 5x median for high-context arms (BABILong 1M splits, etc.) — adds ~$200 for v3.
Plus retries: +20% slack.

**Final v3-full API cost estimate: ~$3,400.**

(Per the user's note about Claude Max flat-fee pricing — `feedback_codeburn_cost_is_notional.md` — these are NOTIONAL API-equivalent costs, NOT actual user spend. The user is on Claude Max; harness-bench cells run on the user's Claude Code session billing.)

### 8.5 Recommended run cadence

- **v1-smoke**: every PR merge to harness-bench main. CI-on-merge. ~1.5h, ~$54.
- **v2-broad**: weekly. Friday afternoon → Monday morning windows. ~14h, ~$477.
- **v3-full**: quarterly release. Reproduces Pareto chart for the harness-bench paper. ~50h wall-clock, ~$3,400.

---

## 9. Inspect AI manifestation

Pseudo-Python showing how the matrix becomes Inspect AI `Task` objects.

### 9.1 One example task per layer

```python
# tasks/components/control_loop.py
from inspect_ai import Task, task
from inspect_ai.dataset import hf_dataset
from inspect_ai.solver import generate, basic_agent
from harness_bench.solvers import (
    react_solver,           # CL-1 baseline
    react_with_reflection,  # CL-2 (max_reflections=3)
    event_driven_solver,    # CL-3 (OpenHands swap)
    multi_agent_orchestrator, # CL-4 (wave model)
)
from harness_bench.scorers import test_pass_scorer

CONTROL_LOOP_ARMS = {
    "CL-1": react_solver(),
    "CL-2": react_with_reflection(max_reflections=3),
    "CL-3": event_driven_solver(),
    "CL-4": multi_agent_orchestrator(max_parallel=4),
}

@task
def control_loop_ablation(arm: str = "CL-1", dataset_name: str = "swe_bench_verified"):
    """One cell of the control-loop ablation matrix."""
    if arm not in CONTROL_LOOP_ARMS:
        raise ValueError(f"unknown arm {arm}")
    return Task(
        dataset=hf_dataset(
            path=f"harness_bench/datasets/{dataset_name}",
            split="test",
        ),
        solver=CONTROL_LOOP_ARMS[arm],
        scorer=test_pass_scorer(),
        metadata={
            "layer": "control_loop",
            "arm": arm,
            "baseline": arm == "CL-1",
        },
    )
```

```python
# tasks/components/verification.py
from harness_bench.solvers import (
    react_no_verify,             # V-1
    react_with_loop_detector,    # V-2
    react_with_inline_lint_test, # V-3
    react_with_browser_subagent, # V-4 (smoke-test)
    react_with_shadow_audit,     # V-5
)

VERIFICATION_ARMS = {
    "V-1": react_no_verify(),
    "V-2": react_with_loop_detector(stuck_threshold_ms=600_000),
    "V-3": react_with_inline_lint_test(),
    "V-4": react_with_browser_subagent(),
    "V-5": react_with_shadow_audit(),
}

@task
def verification_ablation(arm: str = "V-3", dataset_name: str = "swe_bench_verified"):
    """One cell of the verification ablation matrix."""
    return Task(
        dataset=hf_dataset(
            path=f"harness_bench/datasets/{dataset_name}",
            split="test",
        ),
        solver=VERIFICATION_ARMS[arm],
        scorer=test_pass_scorer(),
        metadata={
            "layer": "verification",
            "arm": arm,
            "baseline": arm == "BASELINE-V0",
        },
    )
```

(Analogous files per layer in `tasks/components/{control_loop,reasoning,tool_surface,tool_catalog,memory,subagents,safety,verification}.py`.)

### 9.2 Runner snippet for v1-smoke

```python
# scripts/run_smoke.py
from inspect_ai import eval_set
from harness_bench.matrix import ARMS, DATASETS_SMOKE

cells = [
    {"task": f"control_loop_ablation", "arm": arm, "dataset_name": ds}
    for arm in ARMS["control_loop"]
    for ds in DATASETS_SMOKE["control_loop"]
] + [
    {"task": f"verification_ablation", "arm": arm, "dataset_name": ds}
    for arm in ARMS["verification"]
    for ds in DATASETS_SMOKE["verification"]
] # ... + 6 more layers

eval_set(
    tasks=cells,
    log_dir="logs/smoke",
    max_tasks=4,           # Spark slot count
    max_samples=50,        # smoke is small
    max_messages=100,
    retry_on_failure=True,
)
```

### 9.3 Runner snippet for v3-full

```python
# scripts/run_full.py — same as run_smoke but DATASETS_FULL[layer] is 10-12 datasets
# and runs-per-cell=5 (median of 5 for stability).
eval_set(
    tasks=cells,
    log_dir="logs/v3-full",
    max_tasks=4,
    max_samples=500,
    max_messages=1000,
    epochs=5,              # 5 runs per cell, median scored
    retry_on_failure=True,
)
```

### 9.4 Black-box harness adapters

```python
# tasks/components/blackbox.py
from harness_bench.adapters import devin_api, replit_api, cursor_cli

@task
def devin_anchor(dataset_name: str = "swe_bench_verified"):
    return Task(
        dataset=hf_dataset(path=f"harness_bench/datasets/{dataset_name}", split="test"),
        solver=devin_api.solver(),       # uses https://api.devin.ai/v1/sessions
        scorer=test_pass_scorer(),
        metadata={"harness": "devin", "is_blackbox": True},
    )

@task
def replit_anchor(effort_mode: str = "Power", dataset_name: str = "swe_bench_verified"):
    return Task(
        dataset=hf_dataset(path=f"harness_bench/datasets/{dataset_name}", split="test"),
        solver=replit_api.solver(effort=effort_mode),
        scorer=test_pass_scorer(),
        metadata={"harness": "replit_agent_3", "effort": effort_mode, "is_blackbox": True},
    )
```

---

## 10. Output format

### 10.1 Per-cell result row schema (JSONL, one line per cell)

```jsonc
{
  "cell_id": "v3-full-CL2-aider_polyglot-run3",
  "tier": "v3-full",
  "harness": "aider",
  "layer": "control_loop",
  "arm": "CL-2",
  "is_baseline": false,
  "dataset": "aider_polyglot",
  "dataset_axis": ["FM-1"],
  "dataset_difficulty": "hard",
  "run_index": 3,
  "started_at": "2026-04-22T03:14:01Z",
  "wall_clock_seconds": 187.4,

  // Primary
  "pass_at_1": 1,
  "delta_vs_baseline_v0": 0.12,

  // Secondary
  "input_tokens": 24871,
  "output_tokens": 5104,
  "thinking_tokens": 1832,
  "total_cost_usd": 0.93,
  "tool_calls_count": 6,
  "tool_calls_failed": 1,

  // Tertiary
  "metr_50pct_hours": 1.8,

  // Quaternary
  "pareto_dominated_by": ["CL-1", "V-3"],

  // Provenance
  "harness_version": "aider-0.74.2",
  "model": "claude-opus-4-7",
  "spark_node": "dgx-spark-01",
  "git_sha": "f3e2a91",
  "errors": []
}
```

### 10.2 Aggregator output (CSV)

`logs/<tier>/aggregated.csv`:

| cell_id | layer | arm | dataset | pass_at_1 | delta | usd | wall_clock | metr_hours |
|---------|-------|-----|---------|-----------|-------|-----|-----------|------------|
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

### 10.3 Per-arm leaderboard

`logs/<tier>/leaderboard_arms.csv`:

| arm | layer | mean_delta_vs_baseline | mean_cost | wall_clock | datasets_tested | runs |
|-----|-------|------------------------|-----------|-----------|-----------------|------|
| V-3 | verification | +0.184 | $0.97 | 290s | 5 | 25 |
| SA-3 | sub-agents | +0.142 | $3.20 | 180s | 5 | 25 |
| CL-2 | control_loop | +0.115 | $1.10 | 240s | 4 | 20 |
| ... | ... | ... | ... | ... | ... | ... |

### 10.4 Per-layer contribution score

`logs/<tier>/leaderboard_layers.csv`:

| layer | arms_tested | contribution_score (max-min Δpass@1) | top_arm | bottom_arm |
|-------|-------------|--------------------------------------|---------|------------|
| verification | 5 | 0.184 | V-3 | V-1 |
| sub-agents | 5 | 0.142 | SA-3 | SA-1 |
| memory | 5 | 0.087 | M-4 | M-5 |
| control_loop | 4 | 0.115 | CL-2 | CL-3 |
| safety | 5 | 0.063 | S-4 | S-1 |
| reasoning | 4 | 0.054 | R-1 | R-2 |
| tool_surface | 5 | 0.047 | TS-1 | TS-5 |
| tool_catalog | 4 | 0.042 | TC-1 | TC-2 |

(Hypothetical numbers — actual values populated post-run.)

### 10.5 Per-harness Pareto position

`logs/<tier>/pareto_harnesses.csv`:

| harness | mean_pass_at_1 | mean_cost_usd | dominated_by |
|---------|----------------|---------------|--------------|
| BASELINE-V0 (Claude Code + harness) | 0.61 | $0.85 | (none) |
| Devin | 0.68 | $15.00 | (none — top quality but high cost) |
| Replit Agent 3 (Power) | 0.59 | $0.20 | (none — best cost/quality tradeoff) |
| Aider (with V-3) | 0.56 | $0.40 | BASELINE-V0 |
| Cline (BASELINE swap) | 0.54 | $0.95 | BASELINE-V0, Aider |
| ... | ... | ... | ... |

### 10.6 Bisociation/memory/pain-mode breakdowns

`logs/<tier>/breakdown_by_axis.csv`:

| arm | M-axes mean | FM-axes mean | BS-axes mean | Domain best |
|-----|-------------|--------------|--------------|-------------|
| BASELINE-V0 | 0.62 | 0.55 | 0.41 | code |
| SA-3 | 0.59 | 0.50 | 0.55 | bisociation |
| M-4 | 0.71 | 0.55 | 0.42 | memory |
| V-3 | 0.65 | 0.65 | 0.43 | code+pain |
| ... | ... | ... | ... | ... |

This is the chart that answers "what does each layer buy you, broken down by capability axis."

---

## Appendix A: Glossary

- **BASELINE-V0**: the convergent default cell (§2.0). All 7-of-8 layers held at convergent default; the 8th varies per arm.
- **Arm**: a specific implementation strategy for one layer (e.g., V-3 = "inline lint+test reflection").
- **Cell**: one (arm × dataset × run-index) combination. The atomic unit of evaluation.
- **Wrapper-strategy arm**: ablate via flag/env-var on the existing harness binary.
- **Swap-strategy arm**: ablate by running a different harness binary entirely.
- **Tier**: v1-smoke (CI), v2-broad (weekly), v3-full (release).

## Appendix B: Open questions for implementer agents

1. **TC-2 Claude Code v2.1.68 pinning** — verify whether v2.1.68 is still installable; if not, find an equivalent `--no-tool-search` flag in current Claude Code releases. Fall back: simulate via injecting all 31 skill schemas into system prompt manually.
2. **R-2 thinking-OFF** — confirm Anthropic API parameter name (`thinking={"type":"disabled"}` vs `extended_thinking=false` vs other). Check the API reference + claude-api skill at session-time.
3. **M-5 vector-only adversarial probe** — choose vector store: Chroma is simplest; LanceDB has better long-doc support. Pick at implementation time. Embed model: bge-large or text-embedding-3-large?
4. **S-4 LLM adversary** — Goose's `adversary.md` is the reference template. Source from `~/.config/goose/adversary.md` if present; else write our own (~50 prompt-injection patterns).
5. **CL-3 OpenHands V0 vs V1** — V0 is deprecated per survey §1.2 but still installable. V1 is the new "Software Agent SDK." For ablation reproducibility, pin V0 (don't move target). Confirm V0 install path for next 12 months.
6. **Black-box scoring symmetry** — Devin's API doesn't return raw chain-of-thought; we score only on test-pass. Confirm this doesn't bias the comparison vs open-source cells (it doesn't, since our scoring is also test-pass-based, but flag for paper).
7. **Spark slot allocation** — the "4 slots" assumption is conservative. Profile actual GPU usage in v1-smoke; raise to 8 if API-bound.
8. **Per-arm sample budget for stat sig** — runs-per-cell=5 in v3 may be too few for stat-sig pp differences <2pp. Consider raising to 10 for the 5-arm verification layer specifically.

End of `03-component-ablation.md`.
