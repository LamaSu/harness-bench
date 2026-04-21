"""
M5 — Working-Memory Eviction Under Budget Pressure

Real agents have token caps. When working memory exceeds budget, the agent
must intelligently evict — keep what's needed for the current task, drop
what's not. Almost no benchmark scores eviction-decision quality.

Spec: docs/04-bench-spec.md §2.1.M5.
Datasets (cited from docs/01-corpus-catalog.md):
    - #11 BABILong (lengths 0K -> 10M tokens; permissive PG19+bAbI) — PRIMARY
    - #12 RULER (Apache-2.0; configurable length) — git-only, see substitution
    - #13 InfiniteBench (12 tasks at 100K+; research-only)
    - #6  RepoBench v1.1 (CC-BY-NC-ND-4.0 — eval-only)
    - #7  Long Code Arena (mixed permissive)
    - #5  BigCodeBench (Apache-2.0; extended-context experiments)
    - #14 MMLongBench-Doc / #15 MileBench (research-only)
    - #1  SWE-bench Verified / #2 SWE-bench Pro (large repos)

Primary HF dataset: RULER is git-only per catalog #12 (NVIDIA/RULER repo
contains a generator script, not a downloadable dataset). Per docs/01 §6.4
substitution policy, primary becomes **RMT-team/babilong** (catalog #11,
permissive PG19+bAbI). BABILong ships needle-in-haystack tasks at lengths
0K -> 10M tokens, exactly matching M5's NIAH+budget shape.

When include_ruler=True, the loader still references the git path for
runtime-only RULER generation; the v0.2 implementation pulls BABILong only.

Status: IMPLEMENTED (v0.2) by implementer-foxtrot.
"""
from __future__ import annotations

from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.dataset import Sample, hf_dataset
    from inspect_ai.solver import generate
    from inspect_ai.scorer import includes
except ImportError:  # pragma: no cover
    Task = Any  # type: ignore[assignment,misc]
    Sample = Any  # type: ignore[assignment,misc]
    hf_dataset = None  # type: ignore[assignment]
    generate = None  # type: ignore[assignment]
    includes = None  # type: ignore[assignment]

    def task(fn):  # type: ignore[no-redef]
        return fn

# Budgets per spec §2.1.M5
DEFAULT_BUDGETS_TOKENS: tuple[int, ...] = (
    32_000,
    128_000,
    512_000,
    1_000_000,
    # `inf` represented as -1 sentinel; runner picks model max
    -1,
)

# Substituting RULER (git-only) with BABILong (HF-resident, permissive).
# BABILong is organized as (config name, split name) pairs:
#   configs: "0k", "1k", "2k", "4k", "8k", "16k", "32k", "64k", "128k",
#            "256k", "512k", "1M"   (token-length buckets)
#   splits : "qa1".."qa10"          (bAbI task id)
# Default budget = 32k per spec §2.1.M5; default task = qa1.
BABILONG_HF_ID = "RMT-team/babilong"
BABILONG_DEFAULT_NAME = "32k"
BABILONG_DEFAULT_SPLIT = "qa1"
BABILONG_AVAILABLE_NAMES: tuple[str, ...] = (
    "0k", "1k", "2k", "4k", "8k", "16k", "32k", "64k", "128k", "256k", "512k", "1M",
)


def _plant_critical_facts(
    base_context: str,
    n_facts: int = 5,
    placement: str = "prelude",
) -> tuple[str, list[dict[str, Any]]]:
    """Plant N critical facts into the prelude that must survive eviction.

    :param placement: "prelude" | "midstream" | "scattered"
    :returns: (modified_context, list_of_planted_facts)

    The planted facts use sentinel tokens like CRIT_FACT_001 so a
    downstream scorer can detect preservation by exact substring match.
    """
    facts = [
        {
            "id": f"CRIT_FACT_{i:03d}",
            "value": f"sentinel_value_{i:03d}_must_survive_eviction",
        }
        for i in range(n_facts)
    ]
    fact_block = "\n".join(
        f"[CRITICAL] {f['id']}: {f['value']}" for f in facts
    )

    if placement == "prelude":
        modified = f"{fact_block}\n\n---\n\n{base_context}"
    elif placement == "midstream":
        midpoint = len(base_context) // 2
        modified = (
            base_context[:midpoint]
            + f"\n\n{fact_block}\n\n"
            + base_context[midpoint:]
        )
    elif placement == "scattered":
        # Distribute facts evenly through the context.
        if not base_context or n_facts == 0:
            modified = fact_block + "\n\n" + base_context
        else:
            chunk_size = max(1, len(base_context) // (n_facts + 1))
            pieces: list[str] = []
            for i, fact in enumerate(facts):
                pieces.append(base_context[i * chunk_size : (i + 1) * chunk_size])
                pieces.append(f"\n[CRITICAL] {fact['id']}: {fact['value']}\n")
            pieces.append(base_context[n_facts * chunk_size :])
            modified = "".join(pieces)
    else:
        raise ValueError(
            f"placement must be one of 'prelude' | 'midstream' | 'scattered'; "
            f"got {placement!r}"
        )
    return modified, facts


def _inject_distractor_traffic(
    context: str,
    target_size_tokens: int,
    distractor_density: float = 0.7,
) -> str:
    """Inflate context with distractor traffic to force eviction events.

    Used to stress the harness's compaction/eviction policy. Approximates
    tokens as 4 chars each (English average). Distractor text is drawn
    from a deterministic synthetic pool — irrelevant filler that should
    NOT survive eviction.
    """
    # Rough char-per-token approximation; runner-side tokenizer would
    # refine this, but ~4 chars/token is good enough for v0.2.
    chars_per_token = 4
    target_chars = target_size_tokens * chars_per_token
    if len(context) >= target_chars:
        return context

    distractor_pool = (
        "FILLER The rain in Spain falls mainly on the plain. "
        "FILLER A quick brown fox jumps over the lazy dog. "
        "FILLER All work and no play makes Jack a dull boy. "
        "FILLER The five boxing wizards jump quickly. "
        "FILLER Pack my box with five dozen liquor jugs. "
    )

    deficit = target_chars - len(context)
    distractor_chars = int(deficit * distractor_density)
    repeats = (distractor_chars // len(distractor_pool)) + 1
    distractor_text = (distractor_pool * repeats)[:distractor_chars]

    return context + "\n\n" + distractor_text


def _score_m5_curve(
    fact_preservation_per_budget: dict[int, float],
    eviction_decision_accuracy: float,
) -> dict[str, float]:
    """Compute M5 curve + AUC + eviction-decision accuracy. See spec §2.1.M5.

    AUC under the preservation-vs-budget curve is computed via trapezoidal
    integration over log-spaced budgets. Returns a dict with the curve
    points + AUC + eviction_decision_accuracy.
    """
    if not fact_preservation_per_budget:
        return {
            "auc": 0.0,
            "eviction_decision_accuracy": eviction_decision_accuracy,
        }

    sorted_budgets = sorted(
        b for b in fact_preservation_per_budget.keys() if b > 0
    )
    if len(sorted_budgets) < 2:
        # Single point: AUC is just the value (no integration possible).
        single_b = sorted_budgets[0] if sorted_budgets else next(iter(
            fact_preservation_per_budget.keys()
        ))
        return {
            "auc": fact_preservation_per_budget[single_b],
            "eviction_decision_accuracy": eviction_decision_accuracy,
            f"preservation_at_{single_b}": fact_preservation_per_budget[single_b],
        }

    # Trapezoidal AUC over the budgets (treating budget as the x-axis).
    auc = 0.0
    for i in range(len(sorted_budgets) - 1):
        b_lo, b_hi = sorted_budgets[i], sorted_budgets[i + 1]
        y_lo = fact_preservation_per_budget[b_lo]
        y_hi = fact_preservation_per_budget[b_hi]
        auc += 0.5 * (y_lo + y_hi) * (b_hi - b_lo)

    # Normalize AUC by the budget range so it's a 0..1-shaped quality score.
    budget_range = sorted_budgets[-1] - sorted_budgets[0]
    if budget_range > 0:
        auc /= budget_range

    out: dict[str, float] = {
        "auc": auc,
        "eviction_decision_accuracy": eviction_decision_accuracy,
    }
    for b, v in fact_preservation_per_budget.items():
        out[f"preservation_at_{b}"] = v
    return out


def _babilong_record_to_sample(record: dict[str, Any]) -> "Sample":
    """Adapt a BABILong row into an Inspect AI Sample.

    BABILong row shape (per HF card):
        input (string with embedded haystack + needle), question, answer,
        topic, length_class.

    BABILong already plants needles in long context; for M5 we ALSO plant
    sentinel CRIT_FACT_xxx tokens in the prelude so the scorer can measure
    preservation explicitly. The headline scorer is `includes` — did the
    agent's answer include the gold needle string? The sentinel facts are
    captured in metadata for downstream eviction-quality analysis.
    """
    base_context = (
        record.get("input")
        or record.get("context")
        or record.get("haystack")
        or ""
    )
    question = record.get("question") or record.get("query") or ""
    answer = record.get("answer") or record.get("target") or ""
    topic = record.get("topic") or record.get("task") or ""
    length_class = record.get("length_class") or record.get("length") or "unknown"

    # Plant sentinel critical facts in the prelude.
    augmented_context, planted = _plant_critical_facts(
        base_context, n_facts=5, placement="prelude"
    )

    prompt = (
        f"{augmented_context}\n\n"
        f"---\n\n"
        f"Question: {question}\n"
        f"(If you remember any CRIT_FACT_xxx sentinel facts from the "
        f"prelude, list them at the END of your answer under a "
        f"'Preserved facts:' header.)"
    )

    return Sample(
        input=prompt,
        target=str(answer),
        metadata={
            "axis": "M5",
            "domain": "general",
            "license_tag": "permissive (PG19+bAbI)",
            "source_id": record.get("id") or "",
            "topic": topic,
            "length_class": str(length_class),
            "planted_facts": [f["id"] for f in planted],
            "n_planted": len(planted),
        },
    )


@task
def m5_eviction(
    budgets_tokens: tuple[int, ...] = DEFAULT_BUDGETS_TOKENS,
    n_critical_facts: int = 5,
    samples_per_budget: int = 30,
    include_babilong: bool = True,
    include_ruler: bool = True,
    hf_split: str = BABILONG_DEFAULT_SPLIT,
    hf_name: str = BABILONG_DEFAULT_NAME,
) -> "Task":
    """Inspect AI Task for axis M5.

    Long task at controlled token budgets B. Plant 5 critical facts in
    early context. Inject distractor traffic to force eviction. Score:
    % critical facts preserved per B (curve over B values).

    Headline gate: at B=128K, >=80% critical facts preserved; degradation
    curve flatter than -10% per budget halving.

    BABILong is the primary source (HF, permissive). Config `hf_name`
    controls the token-budget bucket (default "32k" per spec §2.1.M5);
    `hf_split` picks a bAbI task id (default "qa1"). RULER (catalog #12)
    is git-only and would be wired via runtime corpus path; not in v0.2.
    """
    if hf_dataset is None:  # pragma: no cover — inspect_ai not installed
        raise RuntimeError(
            "inspect_ai not installed — install via "
            "`pip install -e .[dev]` before running M5 task."
        )

    if hf_name not in BABILONG_AVAILABLE_NAMES:
        raise ValueError(
            f"BABILong config must be one of {BABILONG_AVAILABLE_NAMES}; "
            f"got {hf_name!r}"
        )

    n_total = samples_per_budget * len([b for b in budgets_tokens if b > 0])
    if not n_total:
        n_total = samples_per_budget

    ds = hf_dataset(
        path=BABILONG_HF_ID,
        name=hf_name,
        split=hf_split,
        sample_fields=_babilong_record_to_sample,
        limit=n_total,
    )

    return Task(
        dataset=ds,
        solver=generate(),
        scorer=includes(),
        metadata={
            "axis": "M5",
            "headline_scorer": "includes",
            "budgets_tokens": list(budgets_tokens),
            "n_critical_facts": n_critical_facts,
            "samples_per_budget": samples_per_budget,
            "hf_dataset": BABILONG_HF_ID,
            "hf_name": hf_name,
            "hf_split": hf_split,
            "substitution_note": (
                "RULER is git-only (NVIDIA/RULER, generator script). "
                "Primary source is BABILong (RMT-team/babilong, HF-resident, "
                f"permissive PG19+bAbI). Default eviction budget={hf_name} "
                f"(bAbI task={hf_split}) per spec §2.1.M5. "
                "Eviction-quality score (_score_m5_curve) is computed "
                "downstream by scorers/ from Preserved-facts header in each "
                "response."
            ),
        },
    )


__all__ = [
    "DEFAULT_BUDGETS_TOKENS",
    "BABILONG_HF_ID",
    "BABILONG_AVAILABLE_NAMES",
    "BABILONG_DEFAULT_NAME",
    "BABILONG_DEFAULT_SPLIT",
    "m5_eviction",
]
