# VinChatbot — Phase 1 Worklog (submission)

VinChatbot is a 24/7 RAG + multi-agent assistant answering VinUni students' academic-services
questions from official documents, with citations and refuse-when-unsure guardrails. Stack: **FastAPI
+ LangChain/LangGraph + Qdrant Cloud (hybrid dense+BM25) + OpenRouter** (`gpt-4o-mini` answer model,
`text-embedding-3-small`, `cohere/rerank-v3.5`). Team 050, AI20K Build Cohort 2.

> **How to read the scores.** The golden eval set grew over time and got *deliberately harder*. Phases
> 1.0–1.6 are measured on the 53→86-case set; **Phase 1.7 expanded it to 130 cases** (adding hard
> point-lookup, cross-lingual, and multilingual-guard cases), so the 1.7+ numbers are **not directly
> comparable** to the earlier ones — the apparent drop (0.919 → 0.846 baseline) is the harder set, not
> a regression. Every change was `ENABLE_*`-flag-gated and A/B-measured on the golden set.

## Metrics journey

| Sub-phase | Focus | Eval (cases) | Note |
|---|---|---|---|
| 1.0 Foundation | crawl→ingest→multi-agent→eval+CI | **0.472** (53) | baseline; language-mismatch dominated |
| 1.1 Quality & safety | language honoring, RAG depth, guards, data-clean | **0.931** (58) | biggest jump |
| 1.2 Metadata, layered guards, eval, viz | boosts, soft-routing, safety API; set→80 | **0.925** (80) | harder set (+safety/multiturn/unanswerable) |
| 1.3 Markdown ingestion v2 | header/token chunking | **reverted** (73.8%) | broke calendar extraction; shelved, DOCX kept |
| 1.4 Chunking/retrieval/fixes | faithfulness fix, conversational handling | **0.919** (86) | +6 conduct cases; parent-doc gated off |
| 1.5 Observability | JSON logs + correlation IDs + cost + Langfuse | **0.930** (86) | logging-only, no regression |
| 1.6 Rerank cost | rerank-once after RRF fusion (~67% fewer rerank calls) | **0.919** (86) | shipped on; accepted ~1-case cost tradeoff |
| 1.7 Eval expansion + adaptive retrieval | set 86→130; point-lookup routing + full-section | **0.846** baseline (130) | new harder reference set |
| 1.8 Cross-lingual expansion | VI↔EN query variant, all domains | **0.885** (130) | **current production — best of the arc** |

Per-category (production, 130 cases): guards (adversarial/safety/unanswerable) **1.000**, calendar
0.929, financial 0.875, conduct 1.000, multiturn 1.000, services 1.000, policy_conduct 0.571*
(*largely eval-scorer artifacts — see caveats). Citation validity ≈ 0.98–1.00.

## Per sub-phase

- **1.0 — Foundation.** 761-doc Qdrant Cloud corpus; LangGraph supervisor→4 ReAct specialists
  (calendar/policy/financial/services); two-tier CI (offline + nightly live eval); golden-set scorer.
  Baseline 0.472 (language mismatch + strict matching diagnosed).
- **1.1 — Quality & safety.** Honor question language; lost-in-the-middle reorder; dynamic-k; near-dup
  dedup; multi-query + RRF; regex+small-LLM guard + de-obfuscation + indirect-injection scan;
  calendar/fee clean structured chunks. 0.472 → 0.931.
- **1.2 — Metadata, layered guards, eval, viz.** event_type/fee_type, policy_code propagation,
  source_trust/term boosts, soft routing, image-chunk exclusion (index −33%); layered API guard
  (OpenAI omni-moderation → small-LLM injection/scope); eval → 80 cases; ARCHITECTURE.md. 0.925.
- **1.3 — Markdown ingestion v2 (REVERTED).** pymupdf4llm markdown + header/token chunker netted
  ≤81% < 92.5% (PDF markdown broke calendar_event extraction; over-fragmentation). Markdown gated
  off; **kept** DOCX parsing/routing.
- **1.4 — Chunking/retrieval/coverage + fixes.** Shipped the **faithfulness false-positive fix**
  (citation/policy-code digits no longer force refusals; recovered the policy LOA cluster) and the
  **conversational-handling fix** (full-VN `answer_language` + rule-tier smalltalk/capability). Tested
  but rejected/gated: parent-doc retrieval, gpt-4o (wash at ~20× cost), prompt tightening. 0.919.
- **1.5 — Observability.** Structured JSON logging + `X-Request-ID` correlation + PII redaction;
  per-turn token/cost capture; **Langfuse** tracing (opt-in extra), all fail-open. No regression
  (0.930).
- **1.6 — Rerank cost reduction.** Rerank the RRF-fused pool **once** instead of once per query
  variant (~67% fewer Cohere calls). A/B was −1 case; **shipped on** (user decision) for the cost win;
  surfaced a calendar point-lookup precision risk (fixed in 1.7).
- **1.7 — Eval expansion + adaptive retrieval.** Grew the eval set **86 → 130** (new
  `calendar_pointlookup` category with adjacent-date distractors, cross-lingual fee, multilingual
  guards) + a `run_eval.py --diff` regression tool. Shipped **adaptive point-lookup routing**: a cheap
  `is_point_lookup` router sends date/fee/code queries to **full-section reading + a strict
  exact-value prompt**; calendar point-lookups drop paraphrase expansion (precision). Fixed the 1.6
  calendar wrong-date.
- **1.8 — Cross-lingual expansion.** A bidirectional **VI↔EN** query-translation variant on every
  domain, so a question in one language matches sources in the other (VI question vs the English fee
  tariff/calendar). Full 130-case eval **0.885** — best of the arc; recovered the persistent VI→EN fee
  misses; guards stayed 1.000.

## Key engineering decisions (with rationale)
- **Qdrant Cloud** as the canonical vector store (Pinecone/Chroma opt-in).
- **NeMo Guardrails dropped** — it pins `langchain<0.4`, which would break our LangChain 1.x stack;
  used OpenAI omni-moderation + a small `qwen-2.5-7b` injection/scope classifier behind a free regex tier.
- **Markdown chunking shelved** (1.3) — lost to the plain-text pipeline; kept gated for a future revisit.
- **Stayed on `gpt-4o-mini`** — `gpt-4o` was a wash at ~15–30× cost; our losses are not model-bound.
- **Cost work** — rerank-once-after-fusion (1.6) cut rerank calls ~67%; per-turn token/cost logging
  (1.5) showed the answer model is the cost driver.
- **Adaptive retrieval (1.7) + cross-lingual (1.8)** — point-lookups (dates/fees) need precision +
  full-section reading + cross-lingual recall, distinct from prose; routed accordingly.
- **Everything `ENABLE_*`-gated and A/B'd** on the golden set; one eval at a time; never trust a run
  with network errors (lesson learned from a mid-eval OpenRouter outage).

## Current production state (2026-06-17)
- Qdrant collection `vinuni_documents` (~7,957 points, plain-text pipeline), untouched in 1.5–1.8.
- Models: `openai/gpt-4o-mini` (answer), `openai/text-embedding-3-small`, `cohere/rerank-v3.5`,
  `qwen/qwen-2.5-7b-instruct` (guard).
- Flags on: `ENABLE_RERANK_AFTER_FUSION`, `ENABLE_ADAPTIVE_RETRIEVAL`, `ENABLE_CROSSLINGUAL_EXPANSION`,
  `ENABLE_COST_TRACKING`; Langfuse opt-in.
- Eval: **0.885 / 130 cases**; guards 1.000; reference `data/eval/baseline.json`.

## Honest caveats / known limitations
- **`policy_conduct` 0.571 is largely a measurement artifact**, not a flow weakness: of 3 fails, 2 are
  eval-scorer issues (token-morphology "temporary"≠"temporarily"; an `expected_source` hardcoded to
  the EN doc while the VI question correctly cited the VI source) and 1 is a borderline generation
  pick. True accuracy ≈ 0.86. The category is tiny (n=7) and LOA-skewed.
- **Single-run eval noise ≈ ±3 cases** (~±2%): a 30-case category swung 0.80↔0.70 on identical logic.
  Multi-run averaging is the top open eval-rigor item.
- **Calendar "period"/grade-release** cases can still fetch the wrong document (registrar blogs outrank
  the Academic Calendar PDF) — candidate for a deterministic structured calendar lookup.
- The golden set is **partly circular/narrow** in places (facts authored from source docs); held-out
  student-phrased cases are tagged `held_out: true`.

## Team members & contribution
> _To be filled by the team (per BRIEF §4.2)._
- _Name — role / contribution_
- _Name — role / contribution_
