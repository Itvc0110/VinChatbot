# Phase 1.25 / A4 — Output-audit (sanitize): groundedness + secret-leak (NO PII)

> Plan: `.claude/plans/can-we-try-to-merry-mango.md` (overwrote the old mass-cache plan). Design doc:
> `LOGS/OUTPUT_GUARDRAILS_AUDITOR_PLAN.md`. Baseline: de-noised **0.964/182** (`eval_20260622T081140Z`).
> **PII scan dropped** — deferred to post-personalization (students will request their OWN PII); memory
> `defer-output-pii-scan-until-personalization`. Auditor judges groundedness + secret-leak/safety only.

## Phase A — deterministic output hardening (PROMOTED, always-on, no flag)

### Trial
Unify the 3 inline output checks (`vinuni_agent.chat`) into one decision with a logged reason; close the
**de-obfuscated secret-leak** gap (`contains_sensitive_output` didn't run through `deobfuscate`); cover the
bypass paths (time fast-path, conversational); fail-CLOSED on a check error.

### Experiment
- **`guardrails.resolve_output_decision(answer, citations, retrieved_texts, *, require_grounding)`** +
  `OutputAuditDecision(action, reason)` (mirror of `GuardrailDecision`). Actions: `allow |
  sensitive_output_blocked | graceful_degradation`. `chat()` calls it once, emits `{type:"output_guard",…}`
  to the trace, fail-closed (exception → degrade).
- **`contains_sensitive_output`** now scans the raw answer + a **zero-width-stripped** variant (for the
  digit-bearing secret patterns, which leet-folding would corrupt) + the leet-folded `deobfuscate` form
  (for marker words). Closes the `sk-or-v1-ab<zwsp>cd…` disguise.
- **Bypass coverage:** `_sensitive_output_block` helper; time fast-path + conversational capability reply
  (LLM-generated) secret-scanned (`require_grounding=False` → secret-only, since they have no citations).
- **Tests:** 8 in `test_guardrails.py` (deobfuscated/zero-width secret caught; no false-positive on the
  `0868900016` hotline / tuition figures; decision matrix; e2e block). Behavior-neutral by construction
  (identical decision sequence; the only delta — disguised-secret detection — triggers on no golden case).
- **Eval gate** (`eval_20260622T143223Z`, N=1 --diff): 0.964→0.956 with 3 flips —
  `calendar-fall-grade-release-en` (GAINED), `unans-future-tuition-en` + `svc-library-services` (LOST) — all
  the **known soft-case N=1 noise** (provably not Phase A, which can't change those answers). Guards
  adversarial/safety **1.000**; policy/policy_longtail flat.

### Progress
- **PROMOTED — ships as-is (no flag, always-on).** Free defensive hardening: deobfuscated secret guard +
  logged output-guard reasons + bypass coverage. No `.env` change (flagless). `baseline.json` unchanged
  (behavior-neutral). No git commit.

## Phase B — LLM output-audit critic (REJECTED, kept gated OFF)

### Trial
An LLM groundedness judge (`audit_output`, mirrors `llm_guard`) on high-stakes point-lookups to convert
*confidently-wrong* → *safely-declined* (cut `confidently_wrong_rate`). Honest prior: a safety net, not a
score-lifter; rejects if it over-degrades any passing case.

### Experiment
- **`agents/output_audit.py`** — `audit_output(...) -> OutputAuditVerdict(grounded, unsupported_claims,
  reason)`, strict JSON, tolerant parse (defaults grounded=True), fail-OPEN on error/no-key/no-evidence;
  only a confident `grounded:false` degrades. Flag `ENABLE_OUTPUT_AUDIT` (default off) + **configurable
  `OUTPUT_AUDIT_MODEL`** (decoupled from `guard_model`). 10 unit tests.
- **Model choice (researched):** Patronus Lynx (SOTA dedicated judge) is **not on OpenRouter** + English-
  biased → out. Cost is negligible for all options (~$0.0004/call) → reliability+VI the driver. Chose
  **gpt-4o-mini** (reliable, in-stack, multilingual).
- **Scope-gate BUG found by the empirical check (1st A/B):** the auditor fired on **0 cases** —
  `get_point_lookup()` reads a `ContextVar` set by `mark_point_lookup()` *inside* the LangGraph tool node,
  which does **not** propagate back to the parent `chat()` context (unlike the Phase-C ledger, which
  survives by mutating a dict in place). **Fixed:** scope signal recomputed in `chat()` via
  `is_point_lookup(request.message, result.get("intent"))`; added a regression test exercising the REAL
  gate (the prior seam tests monkeypatched the signal, so they missed it). 346 green, ruff clean.
- **A/B (corrected, `eval_20260622T155554Z`, gpt-4o-mini, --runs 2, --diff baseline):** auditor fired on
  **86 point-lookups, degraded 9**. **STABLE LOST = −10 regressions** (calendar-fall-final-exams en/vi,
  independence-day en/vi, summer-grade-release en/vi, victory-day en/vi, pol-finaid-deadline-vi +
  svc-library-services); STABLE GAINED +1 (the noisy calendar-fall-grade-release-en). **`confidently_wrong`
  2→2 (zero benefit)** — the only CW cases are `calendar-source-inconsistency-en/vi`, where the answer IS
  grounded in a real-but-inconsistent source → a groundedness judge correctly says "grounded" → structurally
  uncatchable. Categories: calendar 0.929→0.786, calendar_pointlookup 0.944→0.833, policy 0.941→0.912.
  Guards adversarial/safety/unanswerable held **1.000**.
- **Latency cost:** mean **+26%** (4512→5693 ms), p95 **+44%** (10414→14967 ms), model_calls/turn 3.0→3.45;
  $ cost negligible (~$0.0004/point-lookup turn; auditor calls cache on run 2).

### Progress
- **VERDICT: REJECT.** A general LLM judge (even gpt-4o-mini) is **too aggressive on date/number grounding**
  — 9 grounded-CORRECT date answers flagged ungrounded (false positives, the cardinal sin) for **zero**
  measured benefit + a real latency hit. `.env` `ENABLE_OUTPUT_AUDIT=false` (documented), `OUTPUT_AUDIT_MODEL=`
  empty. **Code kept inert + gated** (`output_audit.py`, the `chat()` seam, the config) for a **FUTURE
  security use** — output secret/safety-leak detection, where correctness outweighs latency and the
  false-positive cost doesn't apply. To revive as a *grounding* judge it'd need: a less-strict prompt /
  evidence-format normalization (the date false-positives), or a purpose-built judge (Lynx, self-hosted).
- Phase A stays shipped; baseline remains 0.964/182. No git commit.