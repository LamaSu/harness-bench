# 02 — Agentic Harness Component Survey (harness-bench)

> **Status:** WORK-IN-PROGRESS — researched & maintained by `harness-survey-bravo`.
> **Date started:** 2026-04-21.
> **Project:** `harness-bench` — agentic-harness benchmark suite riding on Inspect AI shell.
> **Scope:** Component-by-component survey of 8 mainstream agentic-coding harnesses (Aider, OpenHands, Cline, Continue.dev, Goose, Cursor Composer 2, Claude Code, Devin/Replit Agent 3) decomposed across 8 architectural layers.

---

## 0. TL;DR

We surveyed 8 mainstream agentic-coding harnesses by decomposing each into the 8 architectural layers the user identified as the field's convergent answer. Six are open-source (Aider 43.6k stars, OpenHands 71.6k, Cline 60.5k, Continue 32.7k, Goose 42.9k, Claude Code public 116.4k — but Claude Code itself is a closed binary), and two are closed SaaS (Cursor 2 + Composer 2, Devin + Replit Agent 3). All six open-source repos are actively maintained (last push within 12 days of 2026-04-21).

The convergent answer holds STRONGLY for **control loop** (single-thread ReAct, 6/8), **memory** (files + git as substrate, 7/8 — vector DB nowhere as primary memory), and **verification = what separates demo from product** (Aider's auto_lint+test reflection and Replit Agent 3's REPL+browser self-test loop are the cited exemplars; harnesses lacking it — Continue, base OpenHands V0 — are widely seen as less reliable). The user's framing breaks down for **sub-agents** (Cursor 2 actually does parallel best-of-N with 8 agents in worktrees — context isolation is no longer the only use case) and **reasoning** (interleaved thinking is a Claude-Code-specific default; most harnesses treat it as model-side, not harness-side). The single most divergent layer is **tool catalog** — Claude Code v2.1.69 (Oct 2025) introduced ToolSearch deferred-loading and cut built-in tool overhead from ~14-16k to ~968 tokens; everyone else is still static. Top three surprising findings: (1) Goose runs an LLM-based AdversaryInspector — actually checks every tool arg against `~/.config/goose/adversary.md` for prompt-injection patterns — making it the most paranoid safety pipeline reviewed; (2) Replit Agent 3 explicitly delegates testing to a SEPARATE subagent for context-pollution avoidance, achieving 200-min autonomy at a $0.20 median cost per session; (3) Cursor 2's native browser tool is doing closed-loop verification "until it has produced the correct final result," sitting alongside Replit Agent 3 and Aider's auto_lint as the three harnesses that defines the verification frontier — though Cursor 2 also has the worst documented safety story (CVE-2026-22708 + deprecated denylist).



---

## 1. Per-harness profiles

---

### 1.1 Aider

- **Repo**: github.com/Aider-AI/aider — Apache-2.0, Python, 43,635 stars, last push 2026-04-09 [§6.1]
- **Production usage signal**: top open-source LLM-coding CLI by stars + downloads on PyPI; Paul Gauthier maintains.
- **Architecture summary**: single-process CLI with a `Coder` subclass per edit-format (16+ variants: `editblock`, `editblock_fenced`, `editor_diff_fenced`, `architect`, `patch`, `whole`, `udiff`). Synchronous send-message loop with optional reflection (max 3). Optional `editor_model` for architect mode. No native function-call tools — the model emits diffs in a textual format, and Aider parses+applies.

#### Layer-by-layer
- **control loop**: Single-thread sync. `Coder.run_one()` → `send_message()` with reflection up to `max_reflections=3`. File: `aider/coders/base_coder.py:~110, ~1670, ~1550`. Diverges from convergent: NOT ReAct-with-function-tools — uses TEXTUAL diff parsing as the "tool call", which constrains it to one model call per "turn" plus implicit lint/test reflections.
- **reasoning**: No interleaved thinking by default; supports `--reasoning-effort` flag and `--show-reasoning` for OpenAI o1/Claude thinking models. Architect mode = light plan-and-execute (architect plans, editor model writes).
- **tool surface**: NO function-calling tools. User-facing slash commands: `/add`, `/drop`, `/web`, `/diff`, `/undo`, `/run`, `/test`, `/lint`, `/clear` (~9). Implicit "tools" = diff-format edit + shell command suggestion + file auto-add on @-mention. NO MCP support as of latest release.
- **tool catalog**: N/A (no function tools). RepoMap is the closest analog — token-budgeted symbolic snapshot of the repo presented in the system prompt.
- **memory**: `done_messages` + `cur_messages` lists; `RepoMap` (line ~505); `ChatSummary` for compaction; `CONVENTIONS.md` user-defined rules file; git is the durable substrate (`dirty_commits=True` auto-commits pre-edit state).
- **sub-agents**: NONE proper. `editor_model` (architect mode) is one subordinate model call per edit, sequentially. NOT parallel. NOT context-isolated.
- **safety**: `allowed_to_edit()` user confirmation; `prepare_to_edit()` checks; `dry_run` flag; `.aiderignore`; token-limit warnings; `--auto-commits=false` to disable git writes. Prompt-level only — no hooks.
- **verification**: `auto_lint=True` → `lint_edited()` reflects errors; `auto_test=True` → reflects test failures; shell output integration. This is a FIRST-CLASS auto-feedback loop and is widely cited as why Aider beats much-larger-context tools on repo correctness.

---

### 1.2 OpenHands

- **Repo**: github.com/All-Hands-AI/OpenHands — MIT-ish (NOASSERTION), Python, 71,605 stars, 2026-04-20. [§6.2]
- **Production usage signal**: largest open-agent star count; official All Hands AI cloud product; CodeAct paper-driven (Wang et al, ICML 2024).
- **Architecture summary**: V0 = `AgentController` (deprecated). V1 = "Software Agent SDK" with new architecture. Multi-agent via `AgentDelegateAction`. Event-driven controller publishes actions/observations to a shared event stream. Sandboxed runtime container (Docker by default).

#### Layer-by-layer
- **control loop**: V0 `AgentController._step()` → `agent.step(state)` → returns Action → published to event stream → `on_event()` decides next step via `should_step()`. Event-driven, not pure sync ReAct. File: `openhands/controller/agent_controller.py`. Re-implementation underway (V1 = Software Agent SDK).
- **reasoning**: CodeActAgent — model emits Python or bash CODE which serves as the action ("act in code"). No explicit thinking-tag interleaving in the controller; relies on whatever the underlying model does.
- **tool surface**: V0 actions: `CmdRunAction`, `FileEditAction`, `IPythonRunCellAction`, `BrowseURLAction`, `MCPAction`, `AgentDelegateAction`, `AgentFinishAction` (~7-10). Native MCP support (`MCPAction`).
- **tool catalog**: Static tool registration; no deferred loading. Microagent system in `openhands/microagent/` provides skill-like dynamic context loading.
- **memory**: `State` class (`history`, `agent_state`, `inputs`, `outputs`, `iteration_flag`, `budget_flag`, `metrics`, `delegate_level`); `StateTracker` persists every change. `openhands/memory/` directory. NO single canonical project memory file (no CLAUDE.md equivalent), though microagents offer context injection.
- **sub-agents**: First-class. `AgentDelegateAction` → `start_delegate()` creates child `AgentController` with `is_delegate=True`; budget shared, sequential return. NOT parallel. NOT used for context isolation primarily — used for capability composition.
- **safety**: `_handle_security_analyzer()` + `ActionSecurityRisk`; HIGH/UNKNOWN → `AWAITING_USER_CONFIRMATION` in confirmation mode. Sandboxed Docker runtime by default (`openhands/runtime/`). Fail-safe to UNKNOWN if no analyzer.
- **verification**: `StuckDetector._is_stuck()` + `attempt_loop_recovery()` + `LoopDetectionObservation`. NO Playwright-style auto-feedback loop natively, but the sandboxed runtime allows tests to be run as `CmdRunAction`s with output appended.

---

### 1.3 Cline

- **Repo**: github.com/cline/cline — Apache-2.0, TypeScript, 60,500 stars, 2026-04-21. [§6.3]
- **Production usage signal**: top VS Code agent extension; Anthropic Claude-first design; rapid 2025-26 growth; spawned the Roo Code fork.
- **Architecture summary**: VS Code extension with `Task` class running a recursive request loop. Tool execution serialized one-at-a-time. Per-task `TaskState` + `MessageStateHandler`. Mature hook system, plan/act dual mode, native subagent tool, MCP support.

#### Layer-by-layer
- **control loop**: `Task.recursivelyMakeClineRequests()` → `attemptApiRequest()` (streams) → `presentAssistantMessage()` (executes tools sequentially). Continues until `attempt_completion` tool call OR no tools used. File: `src/core/task/index.ts`. STRONGLY CONVERGENT with the convergent answer (single-thread ReAct).
- **reasoning**: Native tool calling (`enableNativeToolCalls=true`) + parallel-tool-calling toggle (separately gated). Plan vs Act mode switch (two distinct system prompts in `src/core/prompts/system-prompt/` and `system-prompt-legacy/`).
- **tool surface**: 24 tool handlers in `src/core/task/tools/handlers/`: ReadFile, WriteToFile, ApplyPatch, ExecuteCommand, BrowserTool, WebFetch, WebSearch, SearchFiles, ListFiles, ListCodeDefinitionNames, UseMcpTool, AccessMcpResource, LoadMcpDocumentation, UseSkillTool, Subagent, NewTask, AskFollowupQuestion, AttemptCompletion, Condense, Summarize, PlanModeRespond, ActModeRespond, GenerateExplanation, ReportBug. ~24 tools — within "15-20 atomic + MCP for the rest" convergent range.
- **tool catalog**: `getSystemPrompt(promptContext)` dynamically builds the tool list per request based on enabled features (`READ_ONLY_TOOLS` constant, browser toggle, etc). NOT deferred-loading via search — but conditional surface trim. No ToolSearch equivalent.
- **memory**: `ContextManager` truncates history; auto "quarter" truncation on context-window error; checkpoint manager; `messageStateHandler.getApiConversationHistory()`. `.clinerules` directory (per the repo's own config) + per-task state on disk. Git-aware via checkpoints.
- **sub-agents**: `SubagentToolHandler.ts` + `subagent/{AgentConfigLoader, SubagentBuilder, SubagentRunner, SubagentToolName}.ts`. `subagentsEnabled` setting. Sequential, parent waits.
- **safety**: HOOK SYSTEM (10 files in `src/core/hooks/`): PreCompact, TaskStart, UserPromptSubmit, TaskResume, TaskCancel + cancellation support. `CommandPermissionController`. `maxConsecutiveMistakes` limit. YOLO mode toggle.
- **verification**: `checkpointManager.doesLatestTaskCompletionHaveNewChanges()` validates completion produced changes. Browser tool can validate UI output. No native Playwright self-test loop like Replit Agent 3.

---

### 1.4 Continue.dev

- **Repo**: github.com/continuedev/continue — Apache-2.0, TypeScript, 32,684 stars, 2026-04-21. [§6.4]
- **Production usage signal**: VS Code + JetBrains extensions, "open IDE-agent stack" positioning, less-autonomous than Cline by design.
- **Architecture summary**: IDE-extension-first reactive system. `Core` class registers message handlers via `messenger.on()`. Tools registered in `config.tools`, looked up by name. Less of an "agent" and more of an "AI-augmented IDE stack" with chat, autocomplete, next-edit, and codebase indexing as separate capabilities.

#### Layer-by-layer
- **control loop**: NOT a traditional agent ReAct loop. `Core.registerMessageHandlers()` + `messenger.on()` async event handlers. Reactive to IDE events. File: `core/core.ts`. Strong divergence from convergent — Continue is less "autonomous agent" and more "IDE extension with tools."
- **reasoning**: `config.selectedModelByRole.chat` for primary; `llmStreamChat()` for streaming. No interleaved thinking primitive in core.
- **tool surface**: 20 builtin tools in `core/tools/builtIn.ts` enum: ReadFile, ReadFileRange, EditExistingFile, SingleFindAndReplace, MultiEdit, ReadCurrentlyOpenFile, CreateNewFile, RunTerminalCommand, GrepSearch, FileGlobSearch, SearchWeb, ViewDiff, LSTool, CreateRuleBlock, RequestRule, FetchUrlContent, CodebaseTool, ReadSkill, ViewRepoMap, ViewSubdirectory. CONVERGENT ~20 atomic tools. Has MCP via `MCPManagerSingleton`. `CLIENT_TOOLS_IMPLS` (Edit/SingleFind/MultiEdit) execute in-IDE rather than via LLM tool call.
- **tool catalog**: Static config-based. `tool.preprocessArgs?.()` + per-tool `tool.evaluateToolCallPolicy()`. No deferred loading.
- **memory**: `GlobalContext` for session; `historyManager` for conversation; `prevFilepaths` + `openedFilesLruCache`. MCP context injection. `.continue/` dir for config + rules.
- **sub-agents**: NONE in `core/core.ts`. Capability composition: `CodebaseIndexer`, `CompletionProvider`, `NextEditProvider`, `DocsService`. STRONGLY DIVERGENT from convergent.
- **safety**: `tool.evaluateToolCallPolicy()` per tool; SINGLE policies file `core/tools/policies/fileAccess.ts`. Minimal safety surface vs Goose's 5-inspector pipeline or Claude Code's 68-rule hooks.
- **verification**: minimal; `Telemetry.capture()` only. NO auto-feedback loop, NO checkpoint-based verification.

---

### 1.5 Goose (Block)

- **Repo**: github.com/block/goose — Apache-2.0, Rust, 42,875 stars, 2026-04-21. [§6.5]
- **Production usage signal**: Block (Square)-funded, MCP-pioneering (collaborated on the protocol), strong recipe/extension ecosystem, also includes Electron desktop UI.
- **Architecture summary**: Workspace of crates with `goose` core, `goose-server` (goosed daemon backing desktop), `goose-cli`, `goose-mcp` extensions. Single shared Agent for chat sessions; scheduler spawns per-run Agents; dynamic tasks create subagents. Roadmap includes `AgentManager` to unify all execution paths under one pipeline.

#### Layer-by-layer
- **control loop**: `Agent.reply()` streams; `reply_internal()` runs up to `DEFAULT_MAX_TURNS = 1000` per turn calling `stream_response_from_provider()`. ReAct pattern. File: `crates/goose/src/agents/agent.rs`. CONVERGENT.
- **reasoning**: Echoes back thinking content from Gemini, Kimi, DeepSeek; `reasoning_content` preserved across turns and attached to assistant messages.
- **tool surface**: Tools come from MCP extensions (stdio / built-in / platform / streamable_http). Dispatch via `dispatch_tool_call()` → `ExtensionManager`. No fixed atomic set — fully MCP-driven.
- **tool catalog**: `categorize_tool_requests()` splits frontend vs backend tools. NO deferred-loading-via-search; static surface. `crates/goose-mcp/` packages built-ins.
- **memory**: `SessionManager` adds/replaces messages; auto-`compact_messages()` on threshold; `maybe_summarize_tool_pairs()`. No project-level memory file convention; relies on MCP extensions for persistent state. `.goosehints` dir (per repo `.goosehints` listing in /go's view).
- **sub-agents**: Dynamic tasks spawn subagents. Recipes/sub-recipes (yaml-defined). Discussion #4389 proposes unified `AgentManager` mapping `session_id → Agent`. Per-session ExtensionManager + ToolMonitor isolates state.
- **safety**: 5-INSPECTOR PIPELINE (best-in-class among reviewed): `SecurityInspector` → `EgressInspector` → `AdversaryInspector` (LLM-based, reads `~/.config/goose/adversary.md`) → `PermissionInspector` → `RepetitionInspector`. `ToolConfirmationRouter` queues approval. Chat mode skips execution entirely (`CHAT_MODE_TOOL_SKIPPED_RESPONSE`). Goose's `AdversaryInspector` is unique — actually runs an LLM prompt-injection check on tool args.
- **verification**: `ContextLengthExceeded` triggers compaction (max 2 attempts retry); `goose-self-test.yaml` recipe for self-validation. PostHog telemetry. Lacks Playwright-style closed UI loop.

---

### 1.6 Cursor (Composer 2 + 2.0)

- **Source**: docs at cursor.com/docs (closed binary, no public repo); blog post `cursor.com/blog/2-0` (Oct 29, 2025). [§6.6]
- **Production usage signal**: Cursor is the most-paid-for AI editor (~$300M+ ARR by 2025); Composer 2 launched with proprietary frontier model.
- **Architecture summary**: VS Code-fork IDE; Composer 2 is in-house MoE+RL "frontier model" optimized for agentic coding (4x faster than peers). 2.0 release pivots to "agent-centric" UI: up to 8 parallel agents, isolated via git worktrees or remote sandboxes. Native browser tool for self-test.

#### Layer-by-layer
- **control loop**: closed; documented as ReAct-like with Composer model emitting tool calls, executing, re-calling. "Most turns under 30s." Multi-agent orchestrator on top.
- **reasoning**: Composer-2 specific — MoE + RL trained for "low-latency agentic coding." Uses interleaved thinking when the underlying API supports it.
- **tool surface**: not exhaustively published. Documented: codebase-wide semantic search, native browser tool (Playwright-style), shell, file edit. MCP support added in 2025.
- **tool catalog**: not documented. Cursor likely uses tool-pruning at request time given the 30s turn target.
- **memory**: `.cursorrules` (legacy) + `.cursor/rules/*.mdc` with frontmatter (`globs:`, `alwaysApply:`). No auto-memory like Claude Code.
- **sub-agents**: Up to 8 PARALLEL agents per the 2.0 launch. STRONGLY DIVERGENT from convergent ("sub-agents for context isolation, not parallelism") — Cursor 2.0 actually does parallelism. Best-of-N strategy: "having multiple models attempt the same problem and picking the best result significantly improves the final output." Workspace isolation via git worktrees or remote workers.
- **safety**: known security issues — "officially deprecating the denylist feature in release 1.3" (Backslash report); CVE-2026-22708 — shell built-ins bypass safe mode. Auto-run mode + YOLO toggle. Compromised `.cursorrules` files have been a documented attack vector.
- **verification**: native browser tool "allows Cursor to test its work and iterate until it has produced the correct final result." First-class verification loop, similar to Replit Agent 3.

---

### 1.7 Claude Code (Anthropic) + the user's /go pipeline

- **Repo**: github.com/anthropics/claude-code — closed binary distributed via npm/install; `~/.claude/` user-extensible; plugins at github.com/anthropics/claude-code/tree/main/plugins (Apache-2.0); 116,410 stars. [§6.7]
- **Production usage signal**: Anthropic's first-party CLI; CC Desktop, VS Code, JetBrains, Web all hit same engine; user CLAUDE.md files + agents + skills are first-class extension surface; SDK released 2025.
- **Architecture summary**: ReAct loop in compiled binary; tool calls via Anthropic API native function-calling; `Read/Edit/Write/Glob/Grep/Bash/Task/WebFetch/WebSearch/NotebookEdit/MCP*` atomic tools + arbitrary MCP. CLAUDE.md = project memory. `Task` tool spawns sub-agents context-isolated. v2.1.69 introduced ToolSearch deferred loading.

#### Layer-by-layer
- **control loop**: Single-thread ReAct. Model emits tool calls → executor runs → results appended → model re-called → terminates on plain-text response. CONVERGENT (effectively defines the convergent answer).
- **reasoning**: Interleaved thinking on by default for Opus 4.6/4.7 + Sonnet 4.6 (per CLAUDE.md feedback note `feedback_prefer_opus_4_7.md`). Adaptive thinking budget.
- **tool surface**: Atomic tools = Read, Edit, Glob, Grep, Bash, Write, NotebookEdit, WebSearch, WebFetch, Task, ToolSearch + MCP for everything else. ~10-12 atomic. Within "15-20 + MCP" convergent.
- **tool catalog**: ToolSearch deferred loading since v2.1.69. Reduced built-in tool surface from ~14-16k to ~968 tokens. `tool_reference` blocks expand on demand. Originally MCP-only, generalized to all built-ins. CONVERGENT — defining example.
- **memory**: CLAUDE.md (project) + global `~/.claude/CLAUDE.md`; `MEMORY.md` per-project topic index. Auto-memory feature builds learnings across sessions. Files + git as substrate. The user's `/go` pipeline writes to `ai/supervisor/`, `ai/memory/WORKING_MEMORY.md`, `ai/memory/DECISIONS.md`.
- **sub-agents**: `Task` tool spawns sub-agent. Context-isolated (separate conversation, returns 1-2k summary). CONVERGENT (defining example). User's harness adds named agents (`role-qualifier`), `SUBAGENT_RULES.md` injection, atomic-commit enforcement, telemetry.
- **safety**: hooks system (PreToolUse, PostToolUse, SubagentStop, etc.) — fires at zero-token cost. User's harness adds 68 enforcement rules across 13 categories with WARN/BLOCK verdicts via `harness-enforce.sh`. Per Anthropic blog: 84% fewer permission prompts when sandbox+hooks combined.
- **verification**: Bash/lint/test calls in-loop; user's harness adds `shadow-verifier` haiku (post-implementer audit), `smoke-test` (6-check E2E + self-heal max 3), `exploit-scan` (Gate B runtime). Browser-side verification via `camoufox`/`playwright-cli` sub-skills.

---

### 1.8 Devin / Replit Agent 3 (closed-source duo)

#### Devin (Cognition AI)
- **Source**: cognition.ai/blog/introducing-devin (Mar 2024) + swe-bench-technical-report. Closed-source, hosted SaaS. [§6.8]
- **Architecture summary** (from public statements): "shell, code editor, browser within a sandboxed compute environment"; long-term reasoning + planning over thousands of decisions; multi-step plans with environment feedback; recall/learning; real-time collaboration with user; self-correction. Iterative refinement (>10 min for 72% of successful SWE-bench solutions).

#### Replit Agent 3 (Sept 10, 2025)
- **Source**: blog.replit.com/introducing-agent-3 + automated-self-testing. Closed-source, hosted on Replit. [§6.8]
- **Architecture summary**: 200-min autonomy ceiling, 10x more autonomous than Agent 2, 3 effort modes (Economy/Power/Turbo). Browser tool is REPL-based with Playwright JS sandbox. Verification is a SEPARATE subagent (context-pollution avoidance). Median session cost $0.20.

#### Layer-by-layer (combined; closed harnesses)
- **control loop**: Both ReAct-like with environment feedback. Devin emphasizes long-horizon planning ("thousands of decisions"). Replit Agent 3 runs continuously up to 200 min. Both use sandbox containers.
- **reasoning**: Devin: "long-term reasoning and planning"; Replit: not specified, but 200-min autonomy implies adaptive planning + reflection.
- **tool surface**: Shell + editor + browser (both); Devin "navigates files on its own — does not receive any list of files"; Replit Agent 3 has REPL-based JS sandbox + Playwright + DB query + client/server logs.
- **tool catalog**: closed; not disclosed.
- **memory**: Devin: "recall relevant context at every step, learn over time, fix mistakes"; Replit: per-session state in REPL container, browser session persistence.
- **sub-agents**: Devin: not documented; Replit Agent 3: yes — testing subagent + "Agent 3 can build other agents and automations" (Slack/Telegram bots).
- **safety**: Devin: 45-min runtime cap in eval; sandboxed container; Replit: container + REPL sandbox; effort modes throttle credit consumption.
- **verification**: BOTH harnesses are recognized for first-class verification loops. Devin: "execute multi-step plans to receive feedback from the environment," runs tests, self-corrects. Replit Agent 3: explicit closed loop ("executes it, identifies errors, applies fixes, and reruns the code until it passes tests"); detects "Potemkin interfaces" via DOM+ARIA inspection. STRONGLY CONVERGENT — these define the "verification separates demo from product" thesis.



---

### 1.9 Secondary harnesses (briefer treatment)

#### Roo Code (Cline fork)
- **Repo**: github.com/RooCodeInc/Roo-Code — Apache-2.0, ~22k stars Feb 2026, ~80% codebase shared with Cline. [§6.9]
- **Differentiators**: 
  - **Custom Modes** with scoped tool permissions (Code / Architect / Ask / Debug / Custom + community Mode Gallery) — strict RBAC for the agent.
  - **Orchestrator Mode**: breaks complex tasks into subtasks, routes each to a specialist mode (Architect / Coder / Debugger). PARALLEL multi-agent pattern emerging from a Cline base that didn't have it.
  - **Diff-based editing**: only outputs changed lines (~30% token savings vs Cline's full-file rewrite).
- **Layer impact**: same control loop as Cline; sub-agent layer = SA-C (parallel best-of-mode); tool surface = Cline + mode-scoped restrictions; memory = Cline + Memory Bank pattern.

#### Sourcegraph Amp (formerly Cody)
- **Source**: sourcegraph.com/amp — closed-source (Sourcegraph SaaS); CLI + VS Code extension. [§6.9]
- **Architecture summary**: prompt → context-gather → TODO generation → tool orchestration → continuous validation. Subagents spawned for "extensive context" tasks; isolated context windows. Similar pattern to Replit Agent 3's verification subagent.
- **Layer impact**: context-isolation subagent (SA-B/SA-D), TODO-list as a planning primitive (R-C plan-then-execute variant).

#### Other secondaries (not deeply surveyed)
- **smol-developer / GPT-Engineer** — single-pass codegen; no real ReAct loop; legacy 2023 era.
- **MetaGPT** — role-based multi-agent (PM / architect / engineer / QA); plan-and-execute; less code-edit focused.
- **AutoGPT** — recursive task decomposition; no IDE integration; more research-prototype than production.
- **Bolt.new / v0** — closed; web-app gen-and-deploy; not directly comparable to file-editing harnesses.

These secondaries are useful for ablation breadth (e.g., MetaGPT's role-based multi-agent vs Cursor 2's best-of-N) but not for primary benchmarking.

---

## 2. Cross-harness comparison matrix

| Layer | Aider | OpenHands | Cline | Continue | Goose | Cursor 2 | Claude Code | Devin / Replit3 |
|-------|-------|-----------|-------|----------|-------|----------|-------------|------------------|
| **control loop** | sync + reflect (max 3) | event-driven `_step()` | recursive ReAct | reactive IDE event | ReAct (max 1000 turns) | ReAct + multi-agent orchestrator | single-thread ReAct | long-horizon ReAct + sandbox |
| **reasoning** | optional o1/Claude thinking | model-dependent | native tool calls + plan/act | minimal | thinking echoed Gemini/Kimi/DeepSeek | Composer-2 MoE+RL | interleaved thinking (default-on Opus 4.6+) | long-term planning (closed) |
| **tool surface** | textual diffs, ~9 commands | ~10 actions + MCP | 24 handlers + MCP | 20 builtin + MCP | MCP-driven, no fixed set | docs + browser + MCP (closed) | ~10 atomic + MCP | shell+editor+browser (closed) |
| **tool catalog** | RepoMap (no function tools) | static registration + microagents | dynamic per-request prompt | static config | static, frontend/backend split | undocumented | ToolSearch deferred (v2.1.69) | undocumented |
| **memory** | RepoMap + ChatSummary + git | `State`+`StateTracker`+microagent | ContextManager + checkpoint + .clinerules | `GlobalContext` + .continue | SessionManager + auto-compact | .cursor/rules MDC | CLAUDE.md + auto-memory + git | per-session container (closed) |
| **sub-agents** | architect mode (single editor) | `AgentDelegateAction` (sequential) | `Subagent` handler (sequential) | none | dynamic tasks + recipes | up to 8 PARALLEL (worktrees) | `Task` (context-isolated) | testing subagent (Replit), unknown (Devin) |
| **safety** | prompt-level + dry-run | security analyzer + sandbox + confirmation | hooks (10) + perm controller + YOLO | per-tool policy (1 file) | 5 inspectors + adversary LLM | YOLO + denylist (deprecated) + auto-run vulns | hooks (zero-cost) + sandbox + 68 user rules | container sandbox + runtime caps |
| **verification** | `auto_lint` + `auto_test` reflect | `StuckDetector` + loop recovery | `checkpointManager` + browser | minimal/telemetry | `goose-self-test.yaml` + compaction | native browser self-test | shadow-verifier + smoke-test + bash | REPL self-test + browser loop (Replit) |



---

## 3. Convergence vs divergence

### 3.1 Strongly convergent layers (all/most harnesses agree)

- **control loop = single-thread ReAct + iterate-until-no-tool-call**: 6 of 8 (Aider with reflection-loop variant; OpenHands V0/V1; Cline; Goose; Claude Code; Devin/Replit). Continue is the only outlier (event-driven IDE handlers, NOT a real agent loop). Cursor 2 augments with multi-agent on top but each individual agent is still ReAct. **The user's stated convergence holds.**
- **tool surface = ~15-20 atomic + MCP for everything else**: Cline 24, Continue 20, Claude Code ~10 atomic + MCP, OpenHands ~7-10 + MCP, Goose entirely MCP. Aider is the outlier (no function tools — diffs as the universal "tool"). **Convergence holds.**
- **memory = files + git as substrate**: Aider RepoMap+git, Cline `.clinerules` + checkpoints, Continue `.continue/`, Goose `.goosehints` + SessionManager, Cursor `.cursor/rules`, Claude Code CLAUDE.md + auto-memory. OpenHands is weaker on this (State class but no canonical memory file). NOT a single harness uses a vector DB as primary memory architecture. **Convergence holds — and is striking.**
- **verification = auto-feedback loops separate "demo" from product**: Aider's `auto_lint`+`auto_test` and Replit Agent 3's REPL+browser self-test loop are widely cited as the harnesses that do this best. Devin's blog explicitly identifies this. The harnesses with weak/no verification (Continue, base OpenHands V0) are widely cited as less reliable. **Convergence holds, with a clear quality split.**

### 3.2 Meaningfully divergent layers (real ablation territory)

- **sub-agents — parallel vs sequential vs none**:
  - Cursor 2: up to 8 PARALLEL (best-of-N), worktree-isolated. CONTRA the user's "context isolation, not parallelism" claim.
  - Claude Code Task tool: context-isolated, sequential by default; user's `/go` adds wave parallelism via worktrees.
  - Cline + OpenHands: sequential delegation, parent waits.
  - Continue: NONE.
  - Goose: dynamic tasks + recipes, can be concurrent if scheduler is invoked.
  - Replit Agent 3: separate testing subagent (context-pollution avoidance) — explicitly the "convergent" pattern.
  - Aider: only architect mode (single editor model). Strong divergence in this layer.

- **safety — hooks vs prompts vs sandbox**:
  - Goose: 5-stage inspector pipeline + LLM-based AdversaryInspector (adversarial-prompt detector). Most paranoid.
  - Claude Code + Cline: hook system (intercept, BLOCK/WARN at zero token cost). Anthropic's 84% reduction claim sits here.
  - OpenHands: security analyzer + sandbox container.
  - Cursor: known-vulnerable auto-run, denylist deprecated, CVE-2026-22708 (shell built-in bypass). Worst safety story among the leaders.
  - Continue: per-tool policy file only.
  - Aider: dry-run + .aiderignore + git, no runtime intercept.
  - Devin/Replit: container sandbox + runtime caps; details sparse.

- **reasoning — interleaved thinking vs none vs plan-then-execute**:
  - Claude Code: interleaved thinking on by default (Opus 4.6+).
  - Goose: echoes back thinking content from Gemini/Kimi/DeepSeek across turns.
  - Aider: optional via `--reasoning-effort` flag, NOT default.
  - Continue/Cline: model-dependent, not a harness primitive.
  - Cursor: Composer 2 model-baked.
  - Devin: long-term planning (closed). Replit: not specified.
  - True ablation territory.

- **tool catalog — deferred loading vs static**:
  - Claude Code v2.1.69+: ToolSearch deferred-loading for ALL built-ins. Drove ~14-16k → 968 tokens.
  - Everyone else: static. Cline trims via `getSystemPrompt(promptContext)` per request but doesn't search-on-demand.
  - This is the LAYER WITH THE LARGEST RECENT MOVEMENT — until Oct 2025 every harness was static.

### 3.3 Where the user's "convergent answer" is WRONG / weakened

- **"sub-agents = context isolation, not parallelism"** — Cursor 2 (8 parallel) and Claude Code's `/go` wave model (also parallel, worktree-isolated) prove parallelism IS used in production. The convergent answer should be: "sub-agents are used for context isolation — and increasingly also for best-of-N parallelism when worktrees provide cheap isolation." Both are valid; the field is bifurcated.
- **"reasoning = ReAct + interleaved thinking, default-on for Opus 4.6/4.7 and Sonnet 4.6"** — true for Claude Code, but most other harnesses (Cline, Continue, Goose, Aider, OpenHands) treat thinking as model-side, not harness-side. The convergent answer is a Claude-Code-specific assertion that does not generalize across the field.
- **"plan-and-execute lost"** — partially wrong: Cline's Plan vs Act mode is a first-class plan-and-execute split that's heavily used. Aider's architect mode is plan-and-execute. The pattern lost AS THE DEFAULT, but persists as an opt-in mode. The user's framing should be: "plan-and-execute is opt-in, not default."



---

## 4. Ablation candidates (per layer)

For harness-bench arms, each layer below offers 3-4 distinct strategies observed in the field. These become our ablation arms.

### 4.1 Control-loop ablations
- **CL-A**: Pure single-thread ReAct, terminates on plain text (Claude Code, Cline). [DEFAULT/CONVERGENT]
- **CL-B**: ReAct + reflection bound (`max_reflections=N`) with re-query on tool failure (Aider). [TIGHTER FEEDBACK]
- **CL-C**: Event-driven async controller (OpenHands V0 `_step()` + event stream). [REACTIVE]
- **CL-D**: Multi-agent orchestrator wrapping individual ReAct agents (Cursor 2, user's `/go`). [PARALLEL OUTER LOOP]

### 4.2 Reasoning ablations
- **R-A**: Interleaved thinking ON (default for Opus 4.6+ in Claude Code). [DEFAULT]
- **R-B**: Thinking-OFF (raw ReAct, faster turns). [LATENCY-OPT]
- **R-C**: Plan-then-execute split (Cline Plan/Act, Aider architect). [STRUCTURED]
- **R-D**: Echo thinking content back across turns (Goose `reasoning_content` for Gemini/Kimi/DeepSeek). [CHAIN PRESERVATION]

### 4.3 Tool-surface ablations
- **TS-A**: Atomic core (Read/Edit/Glob/Grep/Bash/Web/Task) ~10 tools + MCP for everything else (Claude Code). [DEFAULT/CONVERGENT]
- **TS-B**: Wide flat surface ~24 named handlers (Cline). [BROAD]
- **TS-C**: Pure-MCP (Goose — every tool is an extension). [PROTOCOL-FIRST]
- **TS-D**: NO function tools at all — diff-format text parsing (Aider). [TEXT-NATIVE]

### 4.4 Tool-catalog ablations
- **TC-A**: Static load all tools upfront (pre-v2.1.69 Claude Code, current Cline/Goose/Continue). [BASELINE]
- **TC-B**: Deferred via ToolSearch — load on demand (Claude Code v2.1.69+). [TOKEN-OPT]
- **TC-C**: Dynamic per-request prompt assembly (Cline `getSystemPrompt(promptContext)` with conditional tools). [SCOPE-OPT]
- **TC-D**: Microagent / skill-router (OpenHands microagents, user's `/go` skill-router). [INTENT-FILTERED]

### 4.5 Memory ablations
- **M-A**: Pure file-based — `.md` + git only (Aider, Claude Code CLAUDE.md). [DEFAULT/CONVERGENT]
- **M-B**: File + auto-summary cache (`ChatSummary` Aider, `compact_messages` Goose, `ContextManager` Cline). [SUMMARY-AUG]
- **M-C**: File + structured event log + checkpoints (Cline `checkpointManager`, OpenHands `StateTracker`). [EVENT-LOG]
- **M-D**: File + LRU + indexed codebase RAG (Continue `CodebaseIndexer` + opened-file LRU). [RAG-AUG]

### 4.6 Sub-agent ablations
- **SA-A**: NONE — single agent (Continue, base Aider). [BASELINE]
- **SA-B**: Sequential delegation, parent waits, used for context isolation (Claude Code Task default, Cline Subagent, OpenHands AgentDelegateAction). [DEFAULT/CONVERGENT]
- **SA-C**: Parallel best-of-N with worktree isolation (Cursor 2, user's `/go` wave model). [PARALLEL]
- **SA-D**: Specialized verification subagent (Replit Agent 3 testing subagent). [VERIFY-DELEGATED]

### 4.7 Safety ablations
- **S-A**: Prompt-only + dry-run flag (Aider). [BASELINE]
- **S-B**: Per-tool policy function (Continue `evaluateToolCallPolicy`). [PER-TOOL]
- **S-C**: Hooks intercept Pre/Post tool with BLOCK/WARN (Claude Code, Cline, user's harness 68 rules). [INTERCEPT/CONVERGENT]
- **S-D**: Inspector pipeline including LLM-based adversary check (Goose 5-stage). [DEEP/PARANOID]
- **S-E**: Sandbox container + runtime cap (OpenHands, Devin, Replit). [ISOLATION]

### 4.8 Verification ablations
- **V-A**: NONE / telemetry only (Continue). [BASELINE]
- **V-B**: Loop-detector + stuck-recovery (OpenHands `StuckDetector`, Goose `compact_messages` retry). [SAFETY-NET]
- **V-C**: Reflect-on-lint+test failure in main loop (Aider `auto_lint`+`auto_test`). [INLINE]
- **V-D**: Browser/REPL self-test in dedicated subagent loop (Replit Agent 3, Cursor 2 native browser, user's smoke-test+exploit-scan). [CLOSED-LOOP]
- **V-E**: Post-hoc shadow audit (user's `shadow-verifier` haiku). [POST-AUDIT]



---

## 4.9 Combined ablation matrix (planned arms for harness-bench)

To go from layer-arms to a runnable matrix, we collapse to ~24 ablation arms in the first pass. Each arm holds 7 layers fixed at the convergent default and varies ONE layer:

| Arm ID | Varied layer | Strategy | Implementing harness | Notes |
|--------|--------------|----------|---------------------|-------|
| ARM-CL-A | control loop | sync ReAct | Claude Code | baseline |
| ARM-CL-B | control loop | reflect bound | Aider | repurposed via aider CLI |
| ARM-CL-D | control loop | parallel orchestrator | Cursor 2 / `/go` | run wave model |
| ARM-R-A | reasoning | thinking ON | Claude Code | baseline |
| ARM-R-B | reasoning | thinking OFF | Claude Code with `--no-thinking` | wrap |
| ARM-R-C | reasoning | plan-then-execute | Cline Plan/Act | mode flag |
| ARM-R-D | reasoning | echo thinking | Goose | provider flag |
| ARM-TS-A | tool surface | atomic + MCP | Claude Code | baseline |
| ARM-TS-C | tool surface | pure MCP | Goose | extension-only |
| ARM-TS-D | tool surface | text diffs | Aider | edit_format=editblock |
| ARM-TC-A | tool catalog | static load | Claude Code pre-2.1.69 (pin version) | baseline |
| ARM-TC-B | tool catalog | ToolSearch | Claude Code latest | enable |
| ARM-TC-C | tool catalog | dynamic per-prompt | Cline | passive default |
| ARM-M-A | memory | files + git | all baseline | universal |
| ARM-M-B | memory | + auto-summary | Goose | enable compaction |
| ARM-M-C | memory | + checkpoints | Cline | enable checkpointManager |
| ARM-M-D | memory | + RAG indexed | Continue | CodebaseIndexer ON |
| ARM-SA-A | sub-agents | none | Aider | no architect mode |
| ARM-SA-B | sub-agents | sequential isolation | Claude Code Task | baseline |
| ARM-SA-C | sub-agents | parallel best-of-N | Cursor 2 / user `/go` | wave model |
| ARM-SA-D | sub-agents | verify subagent | Replit Agent 3 / user smoke-test | enable verify-only subagent |
| ARM-S-C | safety | hooks intercept | Claude Code + harness 68 rules | baseline |
| ARM-S-D | safety | adversary inspector | Goose | adversary.md ON |
| ARM-V-C | verification | inline lint+test | Aider | auto_lint+auto_test ON |
| ARM-V-D | verification | closed-loop browser | Replit Agent 3 / Cursor 2 | browser tool ON |
| ARM-V-E | verification | post-hoc shadow audit | user shadow-verifier | enable |

This gives us 24 ablation arms × 5 task domains × 3 difficulty tiers = 360 evaluation cells in the first pass. Subsequent passes can layer 2-axis interactions (e.g., ARM-V-C × ARM-SA-D to test "does parallel verification subagent dominate inline reflection?").

---

## 5. What's hard to ablate (wrapper-level only)

The following components are deeply baked into specific harnesses such that swapping them in/out requires forking the harness rather than a configuration flag. We will need to ablate these via WRAPPER FLAGS (turn-on-or-off) or by running a different harness entirely.

- **Cursor 2's Composer 2 model** — proprietary MoE+RL trained by Cursor. Cannot be reproduced; ablation = "use vs don't-use Cursor."
- **Aider's diff-format edit** — central to identity; the entire `coders/` hierarchy is built around it. Ablation = pick a specific Coder subclass (`editblock` vs `udiff` vs `patch` vs `whole`).
- **OpenHands CodeAct paradigm** — entire agent built on "act in code." Cannot meaningfully ablate without rewriting the agent.
- **Cline's Plan vs Act mode** — two distinct system prompts in `system-prompt/` and `system-prompt-legacy/`; not a runtime flag, baked into how the agent reasons.
- **Goose's MCP-only tool surface** — every tool is an extension; cannot turn into a "fixed atomic surface" without removing the extension manager.
- **Claude Code's compiled binary** — closed-source; ToolSearch, hook firing, and the underlying ReAct loop are not user-configurable. Ablation = harness-level wrapper (turn `--enable-thinking`, `--no-tools`, etc).
- **Replit Agent 3 / Devin** — closed SaaS. Ablation only via the public API (effort modes for Agent 3; no public knobs for Devin).

For these we will run the harness with its native config + flag combos and treat the harness itself as one cell in the matrix, rather than swapping internals.



---

### 5.1 Workarounds for hard-to-ablate components

For each hard-to-ablate component, the practical strategy:

- **Cursor 2 / Composer 2**: treat as "Cursor cell" in the matrix. Use Cursor CLI with `--mode composer-2` flag. Compare end-to-end against same-task runs in Cline (which can use Composer-equivalent open weights). Cannot decompose Composer 2's MoE+RL training contributions.
- **Aider's diff format**: pin specific Coder subclass. Run `aider --edit-format editblock` vs `--edit-format udiff` vs `--edit-format whole`. This is itself a useful ablation arm (TS-D variants).
- **OpenHands CodeAct**: run OpenHands as a single cell. To compare CodeAct (act-as-Python) vs traditional function-calling, swap to Cline's tool surface as the comparison cell.
- **Cline Plan/Act**: pin mode to Plan or Act for the evaluation; do not swap mid-run. Each becomes a cell.
- **Goose pure-MCP surface**: simulate atomic surface by writing minimal MCP wrappers around Read/Edit/Bash/Glob/Grep — but this is essentially re-implementing Claude Code's surface inside Goose. Note as future work.
- **Claude Code binary**: the user's `~/.claude/` extension surface (commands, hooks, agents, skills) IS our primary lever. Toggle the 13 hook categories on/off via settings.json to ablate the safety/quality layer.
- **Replit Agent 3 / Devin**: black-box. Use only the public effort modes (Economy/Power/Turbo for Replit; whatever Devin exposes via API). Treat both as "ceiling-cells" — what's the maximum quality achievable when we can't see internals?

---

## 6. Repo evidence appendix

Every claim above is keyed to one of the following sources.

### 6.1 Aider
- Repo: https://github.com/Aider-AI/aider — Apache-2.0, Python 43,635 stars, 2026-04-09. (gh api stats)
- `aider/coders/base_coder.py` lines ~110, ~1175, ~1472, ~1550, ~1600, ~1670, ~1693, ~1735, ~2259, ~2335, ~2356, ~2363 — `max_reflections`, `choose_fence`, `check_tokens`, `send_message`, `lint_edited`, `run_one`, `cmd_web`, `summarize_start`, `allowed_to_edit`, `prepare_to_edit`, `run_shell_commands`, `dirty_commits`.
- 16+ Coder subclasses in `aider/coders/`: `editblock_coder.py`, `editblock_fenced_coder.py`, `editblock_func_coder.py`, `editor_diff_fenced_coder.py`, `editor_editblock_coder.py`, `editor_whole_coder.py`, `patch_coder.py`, `single_wholefile_func_coder.py`, `architect_coder.py`, `ask_coder.py`, `context_coder.py`, `help_coder.py`, plus base + prompts files.
- `aider/repomap.py`, `aider/linter.py`, `aider/scrape.py`, `aider/run_cmd.py`, `aider/voice.py` — feature implementations.

### 6.2 OpenHands
- Repo: https://github.com/All-Hands-AI/OpenHands — NOASSERTION (MIT-ish), Python 71,605 stars, 2026-04-20.
- `openhands/controller/agent_controller.py` — `_step`, `on_event`, `should_step`, `_handle_action`, `_handle_observation`, `start_delegate`, `end_delegate`, `_handle_security_analyzer`, `_is_stuck`, `_perform_loop_recovery`.
- `openhands/controller/{action_parser, agent, replay, stuck}.py`, `state/` subdir.
- `openhands/microagent/`, `openhands/memory/`, `openhands/runtime/`, `openhands/security/` directories.
- `AGENTS.md` for V1 transition reference.

### 6.3 Cline
- Repo: https://github.com/cline/cline — Apache-2.0, TypeScript 60,500 stars, 2026-04-21.
- `src/core/task/index.ts` — `Task.recursivelyMakeClineRequests`, `attemptApiRequest`, `presentAssistantMessage`.
- 24 tool handlers in `src/core/task/tools/handlers/`.
- Subagent infra in `src/core/task/tools/subagent/{AgentConfigLoader, SubagentBuilder, SubagentRunner, SubagentToolName}.ts`.
- 10 hook files in `src/core/hooks/`.
- Plan vs Act prompts in `src/core/prompts/system-prompt/` and `system-prompt-legacy/`.
- Storage in `src/core/storage/{StateManager, disk}.ts`.

### 6.4 Continue
- Repo: https://github.com/continuedev/continue — Apache-2.0, TypeScript 32,684 stars, 2026-04-21.
- `core/core.ts` — `Core.registerMessageHandlers`, `messenger.on`, `handleToolCall`.
- `core/tools/builtIn.ts` — `BuiltInToolNames` enum (20 tools); `CLIENT_TOOLS_IMPLS` (Edit/SingleFind/MultiEdit run in IDE).
- 23 tool definition files in `core/tools/definitions/`.
- 1 policy file: `core/tools/policies/fileAccess.ts`.
- MCP via `MCPManagerSingleton`.

### 6.5 Goose (Block)
- Repo: https://github.com/block/goose — Apache-2.0, Rust 42,875 stars, 2026-04-21.
- `crates/goose/src/agents/agent.rs` — `Agent.reply`, `reply_internal`, `DEFAULT_MAX_TURNS=1000`, `categorize_tool_requests`, `tool_inspection_manager.inspect_tools`, `dispatch_tool_call`, `handle_approval_tool_requests`, `handle_schedule_management`.
- 5 inspectors: `SecurityInspector`, `EgressInspector`, `AdversaryInspector` (uses `~/.config/goose/adversary.md`), `PermissionInspector`, `RepetitionInspector`.
- `crates/goose-mcp/`, `crates/goose-server/`, `crates/goose-cli/`.
- Architecture proposals: github.com/block/goose/discussions/4389 (AgentManager), #6202 (unified tooling), #6973 (2026 roadmap).
- `recipe.yaml`, `goose-self-test.yaml`.

### 6.6 Cursor 2 / Composer 2
- cursor.com/blog/2-0 (Oct 29, 2025) — Composer 2 launch + 8 parallel agents + worktree isolation + native browser tool.
- cursor.com/docs — rules system (`.cursorrules`, `.cursor/rules/*.mdc`).
- backslash.security/blog/cursor-ai-security-flaw-autorun-denylist — denylist deprecation.
- dev.to/cverports/cve-2026-22708 — shell built-in bypass of safe mode.
- infoq.com/news/2025/11/cursor-composer-multiagent — multi-agent context-aware development.

### 6.7 Claude Code (Anthropic)
- code.claude.com/docs/en/overview — agent SDK, sub-agents, hooks, skills, CLAUDE.md, auto-memory.
- github.com/anthropics/claude-code — closed binary, but `.claude/{commands,hooks,settings}` + plugins/ public.
- gh issues: #31002 (ToolSearch deferred since v2.1.69), #31172 (ToolSearch UI visibility), #31596 (suppress Tool loaded message).
- platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool — tool search API.
- code.claude.com/docs/en/changelog — version history.
- claudefa.st/blog/guide/changelog — third-party changelog tracker.
- Local install at `~/.claude/`: 81 commands, 26 agents, 31 skills, 17 hooks, 38KB CLAUDE.md, plus user's harness extensions documented in CLAUDE.md.

### 6.9 Secondary harnesses
- github.com/RooCodeInc/Roo-Code — Roo Code (Cline fork), Custom Modes + Orchestrator + diff-based editing.
- morphllm.com/comparisons/roo-code-vs-cline — codebase delta + diff-edit token savings.
- docs.roocode.com/basic-usage/using-modes — modes documentation.
- sourcegraph.com/amp + amp-examples-and-guides repo — Amp agent + context-engineering guide.
- amplifilabs.com/post/sourcegraph-amp-agent-accelerating-code-intelligence-for-ai-driven-development — Amp pattern: TODOs → orchestration → continuous validation.

### 6.8 Devin / Replit Agent 3
- cognition.ai/blog/introducing-devin (Mar 2024) — long-term planning, shell+editor+browser, sandbox, recall+learn.
- cognition.ai/blog/swe-bench-technical-report — 45-min runtime cap in eval, 72% of solutions >10 min, "navigates files on its own."
- blog.replit.com/introducing-agent-3-our-most-autonomous-agent-yet (Sept 10, 2025) — 200-min autonomy, sub-agents, build-other-agents.
- blog.replit.com/automated-self-testing — REPL-based verification, Playwright sandbox, separate testing subagent, $0.20 median cost.
- infoq.com/news/2025/09/replit-agent-3 — extended autonomous coding.



---

## RESEARCH LOG (raw, append-only)

Each web call appends a `## SOURCE: <name>` block here with verbatim findings.

### SOURCE: gh-api-stats (2026-04-21)
| Repo | Stars | Lang | Last push | License | Size (kb) |
|------|-------|------|-----------|---------|-----------|
| Aider-AI/aider | 43,635 | Python | 2026-04-09 | Apache-2.0 | 140,294 |
| All-Hands-AI/OpenHands | 71,605 | Python | 2026-04-20 | NOASSERTION (MIT-ish) | 314,487 |
| cline/cline | 60,500 | TypeScript | 2026-04-21 | Apache-2.0 | 389,060 |
| continuedev/continue | 32,684 | TypeScript | 2026-04-21 | Apache-2.0 | 870,682 |
| block/goose | 42,875 | Rust | 2026-04-21 | Apache-2.0 | 1,146,139 |
| anthropics/claude-code | 116,410 | Shell | 2026-04-20 | none (closed binary, plugins repo) | 27,546 |

### SOURCE: aider/coders/base_coder.py (2026-04-21)
- Loop: `run_one()` → `send_message()` → reflection up to `max_reflections=3` (line ~110). Single-thread sync.
- Tools: slash commands (`/add`, `/drop`, `/web`, `/diff`, `/undo`, `/run`, `/test`, `/lint`, `/clear`); no native function-call tools — patches via diff format.
- Memory: `done_messages` + `cur_messages`; `RepoMap` (line ~505); `ChatSummary` for compaction.
- Sub-agent: single-agent + optional `editor_model` if `edit_format == "architect"` (line ~183). NOT parallel.
- Safety: `allowed_to_edit()`, `prepare_to_edit()`, `dry_run`, `.aiderignore` (line ~390).
- Verification: `auto_lint` reflects errors back; `auto_test` reflects test failures; lines ~1600–1690.
- Edit formats: `editblock`, `editblock_fenced`, `editor_diff_fenced`, `architect`, `patch`, `whole`, `udiff` (16+ coder variants in `aider/coders/`).

### SOURCE: openhands/controller/agent_controller.py (2026-04-21)
- Loop: `step()` → `_step_with_exception_handling()` → `_step()`; event-driven via `on_event()`. Marked DEPRECATED V0; V1 uses Software Agent SDK.
- Tools: action types (`CmdRunAction`, `FileEditAction`, `IPythonRunCellAction`, `BrowseURLAction`, `MCPAction`).
- Sub-agent: explicit `AgentDelegateAction` → `start_delegate()`/`end_delegate()`; child `AgentController` with `is_delegate=True`. Sequential delegation, NOT parallel.
- Memory: `State` (history/agent_state/inputs/outputs/iteration_flag/budget_flag/metrics/delegate_level); `StateTracker` persists.
- Safety: `_handle_security_analyzer()` checks `ActionSecurityRisk` HIGH/UNKNOWN → `AWAITING_USER_CONFIRMATION`. Fail-safe to UNKNOWN if no analyzer.
- Verification: `StuckDetector._is_stuck()` + `attempt_loop_recovery()` + `LoopDetectionObservation`. Loop-detection prevents infinite agentic spin.

### SOURCE: cline/src/core/task/index.ts (2026-04-21)
- Loop: `Task.recursivelyMakeClineRequests()` → `attemptApiRequest()` → `presentAssistantMessage()`. Continues until `attempt_completion` tool call or no tools used.
- Tools: dynamically generated by `getSystemPrompt(promptContext)`. Has `READ_ONLY_TOOLS` constant. Native tool calling toggle (`enableNativeToolCalls`); parallel tool calling separately gated.
- Memory: `ContextManager` truncates conversation; auto "quarter" truncation on context-window error.
- Sub-agent: `subagentsEnabled` setting referenced but no spawning impl in this file.
- Safety: hooks (`PreCompact`, `TaskStart`, `UserPromptSubmit`, `TaskResume`, `TaskCancel`); `CommandPermissionController`; `maxConsecutiveMistakes` limit; YOLO mode toggle.
- Verification: `checkpointManager.doesLatestTaskCompletionHaveNewChanges()`.

### SOURCE: continuedev/continue/core/core.ts (2026-04-21)
- Loop: event-driven via `Core.registerMessageHandlers()`; `messenger.on()` async handlers; reactive to IDE events, NOT a traditional agent ReAct loop.
- Tools: registered in `config.tools`, looked up by name; `tool.preprocessArgs?.()` + `tool.evaluateToolCallPolicy()`. Builtin tools listed in `core/tools/builtIn.ts` + `core/tools/definitions/`.
- Sub-agent: not present; capability composition via `CodebaseIndexer`, `CompletionProvider`, `NextEditProvider`, `DocsService`.
- Memory: `GlobalContext`, `historyManager`, `MCPManagerSingleton`, `prevFilepaths` LRU.
- Safety: `tool.evaluateToolCallPolicy()` per-tool; `core/tools/policies/` directory.
- Verification: minimal; telemetry only.

### SOURCE: cursor.com/blog/2-0 + InfoQ + cometapi (2026-04-21)
- Composer model: MoE + RL, 4x faster than peers, "completes most turns in under 30 seconds."
- Multi-agent: up to 8 parallel agents, isolated via git worktrees or remote machines (sandboxed worker).
- "Multiple models attempt the same problem and picking the best result significantly improves the final output, especially for harder tasks." (best-of-N parallel sampling).
- Native browser tool: "allows Cursor to test its work and iterate until it has produced the correct final result."
- Interface "centered around agents rather than files."
- Rules: `.cursorrules` + `.cursor/rules/*.mdc` with frontmatter `globs:` and `alwaysApply: true`.
- Safety: deprecated denylist auto-run feature in 1.3 due to security flaws (Backslash report); auto-run mode known-vulnerable (CVE-2026-22708 — shell built-ins bypass safe mode).
- 2.0 launch: Oct 29, 2025; Composer 2 distinct cost-efficient model for sub-agent work (MindStudio).

### SOURCE: blog.replit.com/introducing-agent-3 + automated-self-testing (2026-04-21)
- Launched Sept 10, 2025; refined through 2026.
- 200-minute autonomy ceiling; "10x more autonomous" vs Agent 2.
- Effort modes: Economy / Power / Turbo (credit consumption tradeoff).
- Browser tool: built-in REPL-based, runs Playwright JS sandboxed; "stripped-down DOM augmented with ARIA labels and test attributes" + DB query + client/server logs.
- Verification subagent: SEPARATE subagent runs tests "to prevent context pollution"; only essential info passed back. Median cost $0.20 / session.
- Sub-agent generation: "for the first time ever, Agent 3 can build other agents and automations" (Slack/Telegram bots).
- Self-testing loop: "executes it, identifies errors, applies fixes, and reruns the code until it passes tests or meets the specified requirements" (closed feedback loop).
- Detects "Potemkin interfaces" (features that look functional but aren't wired up).

### SOURCE: github.com/block/goose/blob/main/crates/goose/src/agents/agent.rs (2026-04-21)
- Loop: `reply()` streams; `reply_internal()` runs up to `DEFAULT_MAX_TURNS = 1000` per turn calling `stream_response_from_provider()`.
- Tool routing: `categorize_tool_requests()` splits frontend vs backend; backend goes through `tool_inspection_manager.inspect_tools()` (security/egress/adversarial/permissions/repetition); then `dispatch_tool_call()` to `ExtensionManager`.
- Extensions = MCP servers (stdio / built-in / platform / streamable_http). `crates/goose-mcp/`.
- Inspectors (in inspect order): `SecurityInspector` → `EgressInspector` → `AdversaryInspector` (LLM-based, reads `~/.config/goose/adversary.md`) → `PermissionInspector` → `RepetitionInspector`.
- Sub-agents: dynamic tasks spawn subagents on demand; recipes/sub-recipes (Discussion #4389 proposes unified `AgentManager` mapping `session_id → Agent`).
- Memory: `SessionManager` adds/replaces messages; auto-`compact_messages()` on threshold; `maybe_summarize_tool_pairs()`.
- Reasoning: echoes back thinking content from Gemini/Kimi/DeepSeek; `reasoning_content` preserved across turns. ReAct pattern.
- Confirmation: `ToolConfirmationRouter` queues approval; chat mode skips with `CHAT_MODE_TOOL_SKIPPED_RESPONSE`.
- Verification: `ContextLengthExceeded` triggers compaction (max 2 attempts); telemetry via PostHog.

### SOURCE: continue/core/tools/{definitions,policies,builtIn} (2026-04-21)
- 23 builtin tools in `core/tools/definitions/`: `codebaseTool`, `createNewFile`, `createRuleBlock`, `editFile`, `fetchUrlContent`, `globSearch`, `grepSearch`, `ls`, `multiEdit`, `readCurrentlyOpenFile`, `readFile`, `readFileRange`, `readSkill`, `requestRule`, `runTerminalCommand`, `searchWeb`, `singleFindAndReplace`, `viewDiff`, `viewRepoMap`, `viewSubdirectory`.
- `BuiltInToolNames` enum (decoded from `core/tools/builtIn.ts`): ReadFile, ReadFileRange, EditExistingFile, SingleFindAndReplace, MultiEdit, ReadCurrentlyOpenFile, CreateNewFile, RunTerminalCommand, GrepSearch, FileGlobSearch, SearchWeb, ViewDiff, LSTool, CreateRuleBlock, RequestRule, FetchUrlContent, CodebaseTool, ReadSkill, ViewRepoMap, ViewSubdirectory.
- `CLIENT_TOOLS_IMPLS = [EditExistingFile, SingleFindAndReplace, MultiEdit]` — edits client-side (in IDE), not via LLM.
- Single policies file: `policies/fileAccess.ts`. Minimal policy surface vs Goose/Claude Code.

### SOURCE: ClaudeCode v2.1.69 ToolSearch (gh issues #31002, #31172, platform.claude.com docs) (2026-04-21)
- Pre-v2.1.69: built-in tool schemas loaded upfront → ~14-16k tokens.
- Post-v2.1.69: ALL built-in tools (Bash/Read/Edit/Write/Glob/Grep/Agent etc) deferred behind ToolSearch → ~968 tokens base.
- Mechanism: tool_reference blocks returned by ToolSearch (3-5 results) automatically expand into full schemas; Claude then selects + invokes.
- Originally only MCP tools were deferred; v2.1.69 generalized to built-ins. Confirmed by issue #31002.
- "Tool loaded" message in chat (issue #31596).

### SOURCE: Local Claude Code harness (~/.claude/) (2026-04-21)
- 81 commands in `commands/` (slash-prefix skills).
- 26 agents in `agents/` (markdown agent definitions: supervisor, implementer, researcher, scout, hydrator, etc).
- 31 skills in `skills/` (e.g., browse, camoufox, chrome, design-intelligence, peers, watch).
- 17 hook scripts in `hooks/` covering Pre/Post tool, SubagentStop, agent-retry, watchdog, role-router, role-router, telemetry, harness-enforce, trace, session-start, quality-gates, safecheck-detect.
- CLAUDE.md = 38KB / ~38500 chars (root global memory).
- 13-category, 68-rule enforcement matrix (per CLAUDE.md doc).
- Atomic commits, named agents (`role-qualifier`), telemetry pipeline (~/.claude/audit/), reaction engine, named-agent registry, dashboard at localhost:3457.
- Orchestrator wave model: Phase 0 codesight index → 1b LLM-decompose → 2 wheel-scout gate → 3 hydrate → 4 forge/build/skill → 5 implement (Ralph BRAID) → 6 verify (shadow) → 7 smoke-test.
- Ralph loop: GRD-first (Mermaid flowchart) → implement → test → fix → repeat (max 2 trivial / 5 standard / 7 complex).
- Sub-agents spawned via `Task` tool, get `SUBAGENT_RULES.md` + `agent-context-header.md` injected pre-spawn (hook-enforced).

### SOURCE: cline tool handlers + subagent dirs (2026-04-21)
- Tool handlers (24 in `src/core/task/tools/handlers/`): `ReadFile`, `WriteToFile`, `ApplyPatch`, `ExecuteCommand`, `BrowserTool`, `WebFetch`, `WebSearch`, `SearchFiles`, `ListFiles`, `ListCodeDefinitionNames`, `UseMcpTool`, `AccessMcpResource`, `LoadMcpDocumentation`, `UseSkillTool`, `Subagent`, `NewTask`, `AskFollowupQuestion`, `AttemptCompletion`, `Condense`, `Summarize`, `PlanModeRespond`, `ActModeRespond`, `GenerateExplanation`, `ReportBug`.
- Subagent: `src/core/task/tools/subagent/{AgentConfigLoader, SubagentBuilder, SubagentRunner, SubagentToolName}.ts`. Nested-task pattern.
- Hooks (10 in `src/core/hooks/`): `HookDiscoveryCache`, `HookProcess`, `HookProcessRegistry`, `PreToolUseHookCancellationError`, `hook-executor`, `hook-factory`, `notification-hook`, `precompact-executor`. Hook system mirrors Claude Code architecture.
- Plan vs Act modes: `PlanModeRespondHandler` and `ActModeRespondHandler` are separate, suggesting two-mode workflow.
- Subagents are spawned but the parent waits sequentially (no native parallel-by-default).

### SOURCE: code.claude.com/docs/en/overview (2026-04-21)
- Modes: terminal CLI, VS Code, Desktop, JetBrains, Web (claude.ai/code), Mobile (iOS).
- Surfaces: All share single engine + CLAUDE.md / settings / MCP servers.
- Tools mention: file edits, multi-file work, MCP integration, GitHub Actions, GitLab CI.
- Memory: CLAUDE.md (project root, read at session start) + auto-memory feature ("saving learnings like build commands and debugging insights across sessions without you writing anything").
- Sub-agents: explicit (`/en/sub-agents`) — "Spawn multiple Claude Code agents that work on different parts of a task simultaneously. A lead agent coordinates the work, assigns subtasks, and merges results."
- Hooks: "let you run shell commands before or after Claude Code actions, like auto-formatting after every file edit or running lint before a commit." (`/en/hooks`)
- Custom commands aka skills: `/en/skills` — packageable workflows like `/review-pr`, `/deploy-staging`.
- Scheduling: Routines (cloud cron), Desktop scheduled tasks (local), `/loop` (in-session repeat).
- Composability: `tail -200 app.log | claude -p "..."` Unix philosophy.
- Agent SDK: `/en/agent-sdk/overview` — build custom agents with full Claude Code tools.
- Cross-surface: same engine, sessions move between terminal/desktop/web/mobile.

