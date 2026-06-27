# Phase 1.0 — Foundation — Completion Log

Foundation sub-phase: real data, multi-agent core, eval & CI.
Plan: see the approved Phase 1.0 plan. Pairs with [../UPDATE_PLAN.md](../UPDATE_PLAN.md) / [../PRD.md](../PRD.md).

Legend: [ ] todo · [~] in progress · [x] done.

---

## Checklist

### Workstream B — Config + retrieval tool
- [x] `.env.example` → `VECTOR_STORE_BACKEND=qdrant` (Pinecone/Chroma opt-in)
- [x] `search_vinuni` general retrieval tool (no enforced category) added to `tools.py`

### Workstream C — Multi-agent rework (supervisor + specialists)
- [x] `agents/prompts.py` — versioned base + per-specialist prompts
- [x] `agents/supervisor.py` — intent router (LLM + heuristic fallback)
- [x] `agents/specialists.py` — calendar / policy / financial / services specialists
- [x] `agents/graph.py` — StateGraph: supervisor → specialist (input/output guard at service layer)
- [x] output_guard faithfulness check (`assess_faithfulness` in `guardrails.py`, wired in `chat()`)
- [x] `vinuni_agent.py` rebuilt on the graph; `ChatResponse` contract unchanged

### Workstream D — Eval from real data
- [x] `scripts/run_eval.py` scorer (required/forbidden facts, citation, refusal)
- [~] golden sets under `data/eval/golden/` (schema + README ready; category files authored post-ingest)
- [x] `tests/test_agent_graph.py` offline unit eval

### Workstream A — Data foundation
- [x] `scripts/build_core_seeds.py` (harvest 334 policy detail URLs + core docs)
- [x] incremental crawl-save in `crawler.py` (`write_raw_document` called in `crawl_full`)
- [x] seed-coverage check (`report_seed_coverage` in `crawl_seed.py`)
- [x] focused re-crawl run → core docs present in `data/raw` (761 docs, 171/171 seeds)
- [x] ingest → `chunks.json` (16,621) + Qdrant Cloud collection (16,704 points)

### Workstream E — CI (two-tier)
- [x] `.github/workflows/ci.yml` (ruff + pytest non-live, matrix 3.11/3.12)
- [x] `.github/workflows/eval.yml` (nightly + dispatch, secrets)
- [x] `live` pytest marker registered in `pyproject.toml`
- [x] required GitHub secrets documented (below)

### Gates
- [x] `pytest -m "not live"` green (61 passed)
- [x] `ruff check .` green
- [x] baseline per-category eval numbers recorded below

> Note: fixed a pre-existing self-contradictory test
> (`test_guardrail_deescalates_vietnamese_abusive_message` used English input under a
> "vietnamese" name); input is now a Vietnamese abusive phrase to match its assertion.

### Required GitHub Actions secrets (for eval.yml)
`OPENROUTER_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `OPENROUTER_CHAT_MODEL`,
`OPENROUTER_EMBEDDING_MODEL`, `OPENROUTER_RERANK_MODEL`, `QDRANT_COLLECTION`.

---

## Execution log

### 2026-06-13 — code, crawl, ingest

**Static gate:** `ruff check .` clean (6 pre-existing import-order issues auto-fixed);
`pytest -m "not live"` → 61 passed. Fixed one pre-existing self-contradictory guardrail
test (English input under a "vietnamese" name).

**Seeds:** `build_core_seeds.py` → 171 focused seeds (19 built-in + calendar PDF + 153
unique policy detail URLs harvested from the prior `structured_records.json`).

**Re-crawl (2 passes):**
- Pass 1 (per-domain cap 100): 382 docs, seed coverage 106/171 — the per-domain cap on
  `policy.vinuni.edu.vn` cut off the rest.
- Pass 2 (`CRAWL_MAX_VINUNI_PAGES_PER_DOMAIN=300`): **seed coverage 171/171**.
- Corpus now: **761 raw docs**, manifest 861. source_kinds include 152 `policy_html`,
  116 `policy_pdf`, 5 `financial_policy`, 2 `calendar_pdf`, 53 `registrar_page`,
  65 `student_life_page`, 13 `spreadsheet`, 1 `academic_catalog`.
- Structured records: 40,629 — incl. **59 `calendar_event`**, **36 `fee_record`**,
  4,497 `table_record`, 1,136 `spreadsheet_row`, 24 `program` (all were 0 before).
- Verified core docs present: Academic Calendar PDF, Financial Regulations & Tariff
  (47.7K chars), code-of-conduct, leave-of-absence procedure, academic-integrity, etc.

**Ingest:** chunker produced **16,621 chunks** (~4.2M embed tokens); `chunks.json`
written; indexing into Qdrant Cloud collection `vinuni_documents` (1536-dim hybrid).
_(indexed count + baseline eval appended on completion.)_

**Golden sets (55 cases):** calendar 30 (legacy, validated against ingested PDF),
financial 6, policy_conduct 5, services 4, adversarial 10.

**Known follow-ups (Phase 1.1):** `policy_pdf` (6,175 chunks) largely duplicates
`policy_html` text → dedup needed; `student_life_page` over-chunks (3,812) from nav-heavy
pages → cleaning needed.

**Ingest result:** documents=761, chunks=16,621, indexed=16,621 (0 errors), Qdrant
collection `vinuni_documents` = 16,704 points. Hardened the reranker to fall back to
original order on failure (was raising → would fail a chat turn).

**Live smoke (2 cases):** course-drop → correct "9 tháng 10 năm 2026" cited to the
calendar PDF; Nursing tuition → correct "349,650,000 VND" cited to the tariff doc.

### BASELINE EVAL — 2026-06-13 (report: data/eval/results/eval_20260613T165331Z.json)

| Category        | n  | passed | facts_ok | citation_ok |
|-----------------|----|--------|----------|-------------|
| **overall**     | 53 | **0.472** | 0.472 | **0.981** |
| adversarial     | 10 | 1.000  | 1.000    | 1.000       |
| calendar        | 28 | 0.286  | 0.286    | 1.000       |
| financial       | 6  | 0.833  | 0.833    | 0.833       |
| policy_conduct  | 5  | 0.200  | 0.200    | 1.000       |
| services        | 4  | 0.250  | 0.250    | 1.000       |

**Diagnosis (the number is depressed by non-correctness factors, not wrong answers):**
- **Language mismatch (dominant fix):** the agent answers in Vietnamese even for English
  questions (`DEFAULT_ANSWER_LANGUAGE=vi` overrides the "match user language" rule). Most
  EN cases produced *correct* content in VI that failed English `required_facts`
  (e.g. course-drop = "9 tháng 10 năm 2026" ✓ but EN case wanted "October 9, 2026";
  LOA = "sinh viên toàn thời gian" ✓ but EN case wanted "full-time students"). → Phase 1.3
  prompt fix; should sharply raise calendar/policy/services.
- **Strict fact-matching:** VI date-range answers ("23 đến 27 tháng 8 năm 2027") don't
  contain the exact substring "23 tháng 8 năm 2027"; year sometimes dropped. → make the
  scorer range/format-tolerant.
- **Genuine misses (2):** calendar source-inconsistency reasoning (didn't flag the
  Fall'26 mislabel); `fin-currency-en` degraded instead of answering "VND".
- **Strengths confirmed:** citation rate 98%, guardrails/refusals 100%, retrieval finds
  the right source (citation_ok=1.0 on calendar/policy/services).

Baseline anchor established. Top next levers: (1) honor question language, (2)
range-tolerant eval matching, (3) Phase 1.1 dedup/cleaning of policy_pdf/student_life.
