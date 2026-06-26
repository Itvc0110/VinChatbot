# Output Guardrails + Output-Audit Critic — design & plan (A / B / C)

Status: **C SHIPPED 2026-06-21** (per-stage observability ledger + confidently-wrong metric;
260 offline tests pass, ruff clean, adversarial review = SHIP). **A and B are logged here for future
work** — deferred by decision on 2026-06-20.

This doc is the grounded design that came out of the `output-guardrails-audit-map` analysis
(6-reader sweep over the output path). Every claim below is anchored to a file:line that was
verified against the live code, not generic advice.

---

## The output stack today (what actually runs post-answer)

Everything post-answer lives in one method, `VinUniAgentService.chat()`
([vinuni_agent.py:130-164](../../vinchatbot/app/agents/vinuni_agent.py#L130-L164)), three checks in order:

1. `contains_sensitive_output(answer)` — **always-on**, but only matches literal API keys /
   config marker words / postgres creds ([guardrails.py:544](../../vinchatbot/app/agents/guardrails.py#L544)).
   It is **not** run through `deobfuscate`, so a base64/zero-width-obfuscated leaked secret evades it
   even though the *input* side defends against exactly that.
2. `should_gracefully_degrade(answer, citations)` **OR** `not assess_faithfulness(answer, retrieved_texts)`
   — **always-on** ([vinuni_agent.py:137](../../vinchatbot/app/agents/vinuni_agent.py#L137)).
   - `should_gracefully_degrade` = no citations OR an "I don't know" marker.
   - `assess_faithfulness` = **lenient numeric-overlap** — passes if *any* number in the answer
     appears *anywhere* in *any* retrieved chunk ([guardrails.py:583](../../vinchatbot/app/agents/guardrails.py#L583)).
     No claim↔number binding, no year/term binding, no prose checking.
3. `assess_safety(answer)` — **OFF by default** (`ENABLE_OUTPUT_MODERATION=false`,
   [config.py:188](../../vinchatbot/app/core/config.py#L188)); safety categories only, and fails *open*
   if `OPENAI_API_KEY` is missing.

### Proven gaps
- **Grounded-but-wrong passes** (the dominant residual). Multi-row fee tables / multi-term calendars
  make almost every plausible-but-wrong number present *somewhere* in the evidence → faithfulness passes.
- **No citation-to-claim binding.** Citations are scraped wholesale from tool payloads
  ([vinuni_agent.py:367](../../vinchatbot/app/agents/vinuni_agent.py#L367)); nothing checks the answer's
  claims map to the cited chunk.
- **Prose claims unchecked** — if the answer has no numbers, faithfulness is a no-op (wrong eligibility
  rule, wrong office, wrong yes/no → unguarded).
- **No output PII scan.** `scrub_pii` (email/phone) is wired only to logs/Langfuse
  ([observability.py:127](../../vinchatbot/app/core/observability.py#L127)), never the served answer.
- **Bypass paths** skip all output checks: the pure-time fast path
  ([vinuni_agent.py:190-231](../../vinchatbot/app/agents/vinuni_agent.py#L190-L231)) and the
  conversational/capability replies (return before line 130).

---

## Phase A — Output guardrail hardening (deterministic, free, always-on) — DEFERRED

No LLM cost. Mirrors the input cascade so output decisions get a logged reason instead of bare bools.

- **Unify** the output checks into `resolve_output_decision(answer, citations, retrieved_texts, query)`
  returning an `OutputAuditDecision(action, reason)` — mirror of `resolve_guardrail_decision`
  ([guardrails.py:357](../../vinchatbot/app/agents/guardrails.py#L357)) and `GuardrailDecision`
  ([guardrails.py:35](../../vinchatbot/app/agents/guardrails.py#L35)). Emit a `tool_trace` entry
  `{type: "output_guard", action, reason}` so every degrade/block records **why**.
- **Add an output PII scan** (always-on): reuse the `scrub_pii` email/phone regexes + add student-ID /
  grade patterns. Decide redact-vs-degrade per category.
- **Run the secret scan through `deobfuscate`** ([guardrails.py:659](../../vinchatbot/app/agents/guardrails.py#L659))
  to close the obfuscated-leak gap.
- **Cover the bypass paths** (time fast path + conversational) with the deterministic PII/secret scan.
- **Add the missing golden cases** for output PII / secret leakage — today there are **zero**; the
  secret guard is completely unexercised by the eval (a regression would be invisible).

**Two deliberate inversions from the input pattern:**
- **Fail _closed_, not open.** An output grounding/PII check that errors should **degrade**, not serve.
- Exclude `CONVERSATIONAL_ACTIONS` turns (smalltalk/capability legitimately have no citations).

**Gate:** `run_eval --diff baseline.json` shows no regression; adversarial / safety / unanswerable stay
**1.000**. Ship without a flag (additive, safe).

---

## Phase B — Output-audit LLM critic (the "auditor") — DEFERRED

The LLM judge tier on top of A's cascade. Mirrors `classify_with_llm`
([llm_guard.py:63](../../vinchatbot/app/agents/llm_guard.py#L63)): small model (`guard_model`,
qwen-2.5-7b), temp 0, strict JSON `{grounded, unsupported_claims, pii, reason}`.

Judges:
1. **Groundedness / correctness** — is each factual claim entailed by a cited chunk? Catches
   grounded-but-wrong (right citation, wrong row/number/year).
2. **Citation alignment** — do the answer's claims map to the listed citations?
3. **PII / safety backstop** — secondary to A's deterministic scan.

- New flag `ENABLE_OUTPUT_AUDIT` (sibling of `enable_output_moderation`,
  [config.py:188](../../vinchatbot/app/core/config.py#L188)).
- **Deterministic-gated**: only invoke the judge when A's cheap tier is uncertain, OR scope it to
  high-stakes intents (financial / calendar point-lookups) — it runs on *every* answer otherwise and
  would double per-turn latency/cost. **Fail-closed.**
- Insert at [vinuni_agent.py:158](../../vinchatbot/app/agents/vinuni_agent.py#L158) (the existing
  output-moderation seam); on an unsupported-claim verdict reuse
  `build_graceful_degradation_response`.

**Gate:** live A/B via `--diff` — adversarial/safety/unanswerable hold **1.000**, no currently-passing
case degrades, and the new **confidently-wrong-served** rate (from Phase C) drops.

---

## ⚠️ The honest framing — why C comes first

The auditor is a **safety net, not a score-fixer.** The grounded-but-wrong residuals
(`calendar-summer-evaluation-vi` answers the adjacent date; `calendar-spring-grade-release-en` the wrong
semester) currently **fail**. If B catches them it **degrades** them → they still fail the eval (a
"couldn't find it" answer has no required facts), just **safely** instead of **confidently wrong**.

So B trades *confidently-wrong* for *safely-declined* — a real trust/safety win, but it **won't lift the
0.946** and could even dip it if it over-degrades a correct answer (e.g. `conduct-disciplinary-tiers-en`
already wrongly degrades — B must not make that worse). To actually serve the *right* date you need the
**structured calendar/fee lookups** (CODEX P0).

→ **B and the structured lookups are complementary:** B stops the bleeding (never serve a wrong date),
structured lookup fixes the root cause (serve the right one). And B's win is **invisible in `passed`** —
it shows up only in a **confidently-wrong-served** metric. That metric is built in **Phase C**, which is
why C is the prerequisite and is being done first.

### Residual map (verified against baseline.json)
| Case | Signature | Who fixes it |
|---|---|---|
| `calendar-summer-evaluation-vi` | grounded-but-wrong (adjacent date) | B degrades it; structured calendar serves right |
| `calendar-spring-grade-release-en` | grounded-but-wrong (wrong semester) | B degrades it; structured calendar serves right |
| `conduct-disciplinary-tiers-en` | over-cautious degradation (false negative) | retrieval/answer-selection; **B must not worsen** |
| `pol-loa-first-step` | scorer brittleness ('form' token) | scorer/golden fix — **not a model error** |
| `pol-loa-fulltime-vi` | mixed retrieval + grounding | retrieval + structured policy lookup |

---

## Phase C — Per-stage observability ledger + confidently-wrong metric — **SHIPPED**

Maps directly to **UPDATE_PLAN.md CODEX-appendix P0: "Full Eval Plus Cost/Latency Ledger."**

Today there is **no per-stage breakdown**: latency is one whole-turn number
([vinuni_agent.py:55](../../vinchatbot/app/agents/vinuni_agent.py#L55)); `sum_token_usage` only sees the
answer stage ([observability.py:98-111](../../vinchatbot/app/core/observability.py#L98-L111)) — supervisor,
expansion, and guard calls are uncounted locally; the eval report records **zero** cost/latency.

- **Stage ledger** (contextvar, in-place-mutated dict so it survives LangGraph task boundaries):
  per-turn `{stage → calls, tokens_in, tokens_out, latency_ms, est_cost_usd}`.
- **Instrument** supervisor route, `expand_query`, `classify_with_llm`, `_llama_guard` /
  `_openai_moderation`, `rerank`, and the answer stage.
- **Fix the undercount**: turn totals are summed from the ledger (not answer-only).
- **Eval ledger**: per-case `est_cost_usd / tokens / latency_ms / model_calls / rerank_calls / stages`;
  summary adds cost/latency aggregates (mean, p95) + **`confidently_wrong_rate`** (non-refusal,
  has-citations, not-degraded, facts wrong → "served a wrong answer confidently"). Additive only —
  existing `passed/facts_ok/citation_ok/by_category` unchanged so baseline diffing still works.

**Gate:** ruff + `pytest -m "not live"` green; ledger appears in the eval report; no behavior change
(fail-open everywhere).
