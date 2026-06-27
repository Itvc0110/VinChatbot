# Phase 1.2 — Eval expansion, metadata engineering, layered API guards, flow viz — Log

Plan: the approved Phase 1.2 plan. Pairs with [PHASE1.1_LOG.md](PHASE1.1_LOG.md) (Phase 1.1 ended
at **93.1%** on 58 cases). Everything below is behind a settings toggle for A/B.

## Checklist

### Track 1 — Flow visualization
- [x] `ARCHITECTURE.md` — Mermaid diagrams (ingest, query flow, guard layering) + module map; linked from README

### Track 2 — Metadata engineering
- [x] `event_type` + `fee_type` added to `DocumentMetadata` and populated from calendar/fee records
- [x] `policy_code` (+ issued/updated) propagated listing→text chunks (911 stamped) at ingest
- [x] `source_trust` + term/academic_year/policy_code/category boosts (`apply_metadata_boosts`, `ENABLE_METADATA_BOOST`)
- [x] Hard category filters → soft boosts (`ENABLE_SOFT_ROUTING`), `search_vinuni` fallback kept
- [x] Low-signal `image_asset` chunks excluded (3,957 → 34; only OCR/substantive caption kept)
- [x] Payload indexes for `source_kind`/`source_trust`/`policy_code`/`event_type`/`fee_type`
- [x] Re-ingest: 16,506 → **7,781 chunks** (Qdrant 7,957 points)

### Track 3 — Layered API guards (rule-based first, then API)
- [x] `agents/safety_guard.py` — OpenAI omni-moderation (default) | Llama Guard 4 | off; runs only on non-confident turns
- [x] Layered in `resolve_guardrail_decision` (regex/deobf → safety → injection/scope); `ENABLE_SAFETY_ON_ALL` for strict mode
- [x] `GUARD_MODEL=qwen/qwen-2.5-7b-instruct` (verified resolves on OpenRouter) for injection+scope
- [x] Output moderation switched to the safety guard (`ENABLE_OUTPUT_MODERATION`)
- [x] Verified live: safe→allow; "I will hurt you…"→flagged (harassment/violence) → blocked
- [x] Settings documented in `.env` + `.env.example`; offline tests mock/skip the API

### Track 4 — Eval expansion (58 → 80)
- [x] Multi-turn scorer (`turns` list on one conversation_id; final answer scored)
- [x] New sets: `safety.json` (8), `multiturn.json` (4), `unanswerable.json` (5); +grounded financial/policy/services cases

### Track 5 — Other improvements
- [x] Calendar prompt: explicit Add/Drop disambiguation + flag source term/date contradictions
- [x] Per-turn latency log in `chat()`
- [x] Multi-query retrievals parallelized (`asyncio.gather`)

### Gates
- [x] `pytest -m "not live"` green (86) · `ruff` green

---

## Execution log

### 2026-06-14 — Phase 1.2 build

Re-ingest after metadata + image-exclusion: chunks 16,506 → 9,462 (image exclusion) →
**7,781** (content-hash dedup); stamped `policy_code` onto 911 policy chunks; Qdrant
collection `vinuni_documents` = 7,957 points. Guard verified live (omni-moderation blocks
unsafe; qwen guard model resolves).

**Bug caught & fixed:** the first Phase-1.2 eval read **32.5%** because `apply_metadata_boosts`
mutated a *frozen* `RetrievedChunk.score` → `FrozenInstanceError` crashed every content
retrieval (unit test had used a mutable `SimpleNamespace`, masking it). Fixed with
`dataclasses.replace` + a regression test using the real frozen type.

### BASELINE COMPARISON — Phase 1.2 (report: data/eval/results/eval_20260613T233122Z.json)

| Category        | Phase 1.1 (58) | **Phase 1.2 (80)** |
|-----------------|--------------|------------------|
| **overall**     | 0.931        | **0.925**        |
| citation_ok     | 1.000        | 0.975            |
| adversarial     | 1.000 (15)   | 1.000 (15)       |
| **safety** (new)| —            | **1.000 (8)**    |
| **multi-turn** (new) | —       | **1.000 (4)**    |
| **unanswerable** (new) | —     | **1.000 (5)**    |
| calendar        | 0.893        | 0.929            |
| financial       | 1.000        | 0.875            |
| services        | 1.000        | 0.800            |
| policy_conduct  | 0.800        | 0.714            |

**Held quality (92.5%) while adding 22 harder cases** (safety/memory/refusal all 100%) on a
**33%-smaller index** (11,704 → 7,781). 6 fails: the 2 source-inconsistency reasoning cases
(model reports dates but won't flag the source's "Fall'26" mislabel — the calendar prompt
nudge didn't fully solve it), and 4 VI/phrasing edge cases (fin-standard-credit-vi,
pol-loa-purpose, pol-loa-fulltime-vi, svc-library-services). Metadata boosts + soft routing
+ image exclusion delivered: calendar/safety/memory up, index sharper, no quality loss.
