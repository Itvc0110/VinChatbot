# VinChatbot — Architecture & Flow

Visual reference for how data and a chat turn move through the system. Diagrams are
Mermaid (render in GitHub and the VS Code Mermaid preview). Pairs with [PRD.md](PRD.md) /
[UPDATE_PLAN.md](UPDATE_PLAN.md).

> State (2026-06-26, post-Phase 1.33): the flows, multi-agent routing, layered guards, and module map
> below match the current code. Serving is **plain-text** on **`gpt-4o-mini`**. Major additions since
> Phase 1.7 (all `ENABLE_*`-flag-gated + fail-open; see [LOGS/SESSION_CLOSEOUT.md](LOGS/SESSION_CLOSEOUT.md)
> for the full done/deferred state and [UPDATE_PLAN.md](UPDATE_PLAN.md) for the roadmap):
> - **Multi-domain fan-out** (Phase 1.33, `ENABLE_FAN_OUT`, **PROMOTED → default ON**, the live flow): the
>   supervisor is a dispatch planner that DECOMPOSEs a genuine cross-domain compound into per-domain subtasks
>   run in PARALLEL, or HEDGEs a route-ambiguous question to 2 candidate specialists, then a synthesis node
>   merges (union of citations). A single-assignment plan (the ~87%) takes the single-specialist path,
>   byte-identical (defers to `route_intent`; same-intent over-fires collapse). Neutral on the single-domain
>   scored set (no regression after the over-fire fix) and adds the multi-domain coverage the single router
>   structurally can't. Set `ENABLE_FAN_OUT=false` to revert. See **§2c**.
> - **Deterministic structured lookup** (calendar + fee) runs BEFORE vector search — exact-row match for
>   point-lookups, **list mode** (Phase 1.27) returns the full fee matrix / all matching calendar events for
>   "all/each" questions (§2b). `ENABLE_STRUCTURED_LOOKUP`, `ENABLE_LIST_MODE`.
> - **Policy doc-pin + ingest auto-index** (Phase 1.21/1.24): a confidently-matched policy question pins its
>   canonical all-policies page by `source_url`; cross-lingual escalation forces the EN variant for VI policy
>   questions (`ENABLE_POLICY_DOC_PIN`, `ENABLE_POLICY_AUTO_INDEX`, `ENABLE_CROSSLINGUAL_POLICY`).
> - **Determinism + exact-match Redis cache** of LLM + rerank calls (Phase 1.23): reproducible runs + cheaper
>   re-runs, fail-open (`ENABLE_LLM_CACHE`, `ENABLE_RERANK_CACHE`).
> - **Output-guard unification** (Phase 1.25 Phase A): `resolve_output_decision` (secret-leak incl.
>   de-obfuscated/zero-width + citation/degrade + faithfulness), logged reasons (§3). The LLM output-audit
>   critic was rejected and is kept inert (`ENABLE_OUTPUT_AUDIT=false`).
> - Baseline: **≈0.98/199** golden, fan-out OFF ([data/eval/baseline.json](data/eval/baseline.json)); guards
>   1.000 (single-run noise ≈ ±3 cases).

---

## 1. Offline ingest pipeline (admin / scheduled — never at chat time)

```mermaid
flowchart LR
    seeds["Seeds<br/>(SEED_URLS + core_seeds.json:<br/>policy detail URLs + calendar PDF)"]
    subgraph crawl["Crawler (crawler.py)"]
        fetch["fetch (httpx)<br/>robots + per-domain/depth caps"]
        route{"source_kind?<br/>(normalizer.infer_source_kind)"}
        save["write each raw doc incrementally<br/>data/raw/*.json"]
    end
    subgraph parse["Parsers (parsers.py)"]
        html["parse_html (trafilatura)"]
        pdf["parse_pdf_bytes (pymupdf)"]
        sheet["parse_spreadsheet_bytes"]
        struct["structured records:<br/>calendar_event, fee_record,<br/>policy_listing, table, image_asset"]
    end
    subgraph ingest["Ingest (ingest_documents.py)"]
        clean["strip_boilerplate + normalize_text"]
        chunk["chunk_document<br/>(prose + structured-record chunks)"]
        dedup["content-hash dedup"]
        embed["embed: dense (OpenRouter) + sparse (FastEmbed BM25)"]
    end
    qdrant[("Qdrant Cloud<br/>hybrid vectors + payload indexes")]
    artifacts["data/processed/*.json<br/>manifest, links, structured_records, chunks"]

    seeds --> fetch --> route -->|HTML| html
    route -->|PDF| pdf
    route -->|CSV/XLSX| sheet
    fetch --> save
    html --> struct
    pdf --> struct
    sheet --> struct
    html --> clean
    pdf --> clean
    struct --> chunk
    clean --> chunk --> dedup --> embed --> qdrant
    chunk --> artifacts
```

## 2. Online query flow (a single `/chat` turn)

```mermaid
flowchart TD
    req["POST /chat<br/>{message, conversation_id, filters}"]
    guard_in{"Input guard<br/>(resolve_guardrail_decision)"}
    blocked["build_guardrail_response<br/>(injection / restricted / abusive / out-of-scope / greeting)"]
    lang["detect language<br/>(answer_language) → directive"]

    subgraph graph["Multi-agent graph (LangGraph, graph.py) — see §2a for detail"]
        sup["Supervisor / dispatch planner (supervisor.py)<br/>1 specialist (calendar|policy|financial|services),<br/>or fan-out to several (§2c)"]
        spec["Selected specialist(s)<br/>ReAct agent, own prompt + tool subset<br/>(parallel + synthesis when fanned out)"]
    end

    retr["Retrieval pipeline (adaptive)<br/>tool _search → QdrantHybridRetriever<br/>— full detail in §2b"]

    answer["answer + citations + tool_trace"]
    guard_out{"Output checks (chat)<br/>secret-leak · citation/degrade · faithfulness"}
    degrade["graceful degradation<br/>(not enough official info)"]
    resp["ChatResponse<br/>answer, citations, confidence, needs_human_review"]
    mem[("LangGraph checkpointer<br/>per conversation_id (in-session memory)")]

    req --> guard_in
    guard_in -->|blocked| blocked
    guard_in -->|allowed| lang --> sup --> spec
    spec -->|tool call| retr --> spec
    spec --> answer --> guard_out
    guard_out -->|leak| blocked
    guard_out -->|unsupported| degrade
    guard_out -->|ok| resp
    graph <--> mem
```

## 2b. Retrieval pipeline detail (adaptive — Phase 1.6 / 1.7)

Every tool call enters `_search` ([tools.py](../vinchatbot/app/agents/tools.py)). A cheap router
(`is_point_lookup`, [query_engineering.py](../vinchatbot/app/rag/query_engineering.py)) splits **prose**
from **point-lookups** (exact dates/amounts/codes — routed category `calendar`/`financial`, or a
year/term/amount in the query). Two shipped levers: **Phase 1.6** reranks the RRF-fused pool **once**
(not per variant — ~67% fewer rerank calls); **Phase 1.7** routes point-lookups to **full-section
reading + a strict extraction prompt**, with a domain split on query expansion (calendar OFF for
precision; financial ON + a cross-lingual English variant for recall). Toggles:
`ENABLE_RERANK_AFTER_FUSION`, `ENABLE_ADAPTIVE_RETRIEVAL` (both default **true**; set either `false`
to revert).

**Deterministic layers that run BEFORE / around vector search** (added Phase 1.19–1.27, each flag-gated +
fail-open → any miss falls through to the vector path byte-identically):
- **Structured lookup** ([structured_lookup.py](../vinchatbot/app/rag/structured_lookup.py)) — for
  calendar/financial turns, a pure dict/regex record match on the USER's raw question returns the ONE exact
  row (date/fee) — never the adjacent near-row vector leaks. **List mode** (Phase 1.27, `is_list_lookup` +
  `ENABLE_LIST_MODE`): "all/each/compare" questions return the **full fee matrix** (`_match_fee`) or **all
  matching calendar events** (`_match_calendar`) deterministically, and widen the vector path
  (`RETRIEVAL_LIST_MAX_K`) + enumerate. Built by `scripts/build_structured_index.py` →
  `data/processed/structured_records.json`.
- **Policy doc-pin** ([policy_lookup.py](vinchatbot/app/rag/policy_lookup.py)) — a confident single-topic
  policy match pins that canonical all-policies page by `source_url` (gap-proof doc selection). The curated
  17-topic map (precedence) + an **ingest auto-index** (title fallback for the other ~138 pages, built by
  `scripts/build_policy_topic_index.py`). VI policy questions also force an EN translation variant
  (cross-lingual escalation) so the often-EN canonical doc is RRF-fused in.
- **Exact-match cache** ([cache.py](../vinchatbot/app/core/cache.py)) — LLM responses (via
  `langchain` `set_llm_cache`) + rerank scores, keyed on the full prompt/content + `CACHE_VERSION`, in Redis.
  Reproducible runs (kills run-to-run noise on exact repeats) + cost cuts; fail-open (any Redis error → miss).

```mermaid
flowchart TD
    q["tool _search(query, routed category) — tools.py"]
    soft["soft-routing → category as boost hint"]
    pl{"is_point_lookup?<br/>ENABLE_ADAPTIVE_RETRIEVAL +<br/>category calendar/financial OR year/term/amount"}

    q --> soft --> pl

    pl -->|"calendar point-lookup"| c1["NO expansion (single query)<br/>precision: date-grid neighbours are distractors"]
    pl -->|"financial / other point-lookup"| c2["expand_query + cross-lingual EN variant<br/>recall: match the EN tariff"]
    pl -->|"prose (not a point-lookup)"| c3["expand_query (same-language paraphrases)"]

    c2 --> mq{"len(queries) > 1?"}
    c3 --> mq
    mq -->|yes| fuse["per-variant candidates (vector+BM25, NO rerank)<br/>→ RRF fuse → near-dup dedup → cap to candidate_k"]
    fuse --> rr
    mq -->|no| rr
    c1 --> rr

    subgraph finz["rerank + finalize — QdrantHybridRetriever._finalize"]
        rr["rerank ONCE (OpenRouter Cohere, fail-open)<br/>Phase 1.6: one call, not per-variant"]
        dd["near-dup dedup"]
        bo["metadata boost (trust / term / policy_code / category)"]
        dk["dynamic-k (score-ratio, min/max)"]
        se["full-section expand for point-lookups<br/>(parent-doc machinery; incl. the calendar table)"]
        lm["lost-in-the-middle reorder"]
        rr --> dd --> bo --> dk --> se --> lm
    end

    lm --> scan["indirect-injection scan (drop poisoned chunks)"]
    scan --> out["chunks → specialist as tool result"]
    out --> sp["calendar & financial specialists add a strict<br/>'answer the exact value only' prompt (point-lookups)"]
```

## 2a. Multi-agent: supervisor → specialists → tools (and where MCP/A2A would fit)

How the "multi-agent" actually works today: the supervisor is a **dispatch planner**
(`ENABLE_FAN_OUT` default ON — **§2c**) that routes a clear single-domain question to **one of
four specialist ReAct agents** (the ~87% common case shown below) or fans a genuine compound
out to several in parallel. Each specialist is its own `create_agent` instance with its **own
system prompt and a focused subset of tools**. Tools are **in-process Python functions** (`tools.py`,
LangChain `@tool`) — every tool ultimately calls the same retrieval pipeline. Memory is the
shared LangGraph checkpointer keyed by `conversation_id`.

> **MCP / A2A are NOT implemented (deferred).** The dashed boxes below show where they
> *would* attach if adopted later: MCP would expose the tools over the Model Context
> Protocol so external clients/agents could call them; A2A would split the specialists into
> independent agent services that talk over the agent-to-agent protocol. Today everything
> runs in one process.

```mermaid
flowchart TD
    q["allowed, language-tagged message"]
    sup{"Supervisor / router<br/>supervisor.py (LLM + heuristic fallback)"}

    subgraph specs["Specialist ReAct agents (one runs per turn) — specialists.py"]
        cal["CalendarAgent<br/>deadline disambiguation"]
        pol["PolicyAgent<br/>procedure format"]
        fin["FinancialAgent<br/>fees / tariff"]
        svc["ServicesAgent<br/>library / registrar / general"]
    end

    subgraph tools["In-process tools — tools.py (LangChain @tool)"]
        t1["search_academic_calendar"]
        t2["search_policy_documents"]
        t3["search_financial_regulations"]
        t4["search_vinuni (general)"]
        t5["get_source_detail"]
    end

    retr["Retrieval pipeline → Qdrant (adaptive)<br/>router → expand/fuse → rerank-once →<br/>boost → dynamic-k → full-section → LITM → scan<br/>(full detail in §2b)"]

    q --> sup
    sup -->|calendar| cal --> t1
    sup -->|policy| pol --> t2
    sup -->|financial| fin --> t3
    sup -->|services| svc --> t4
    cal -.optional.-> t5
    pol -.optional.-> t5
    fin -.optional.-> t5
    svc -.optional.-> t5
    t1 --> retr
    t2 --> retr
    t3 --> retr
    t4 --> retr
    t5 --> retr
    retr -->|chunks as tool result| sup

    mcp["MCP server<br/>FUTURE / deferred"]
    a2a["A2A agent services<br/>FUTURE / deferred"]
    tools -. "could be exposed via" .-> mcp
    specs -. "could be split into" .-> a2a
```

## 2c. Multi-domain fan-out (Phase 1.33 — `ENABLE_FAN_OUT`, PROMOTED, default ON)

**The live flow.** It solves two single-route failures the old flow gets *categorically* wrong: **(a) compound
coverage** ("MD tuition **and** when does Fall start?" — single routing answers one half, silently drops the
other) and **(b) route ambiguity** (a boundary question mis-routed to the wrong single specialist). It is
**neutral on the single-domain scored set** (no regression after the same-intent over-fire fix) and adds the
multi-domain coverage that shows on the authored hard set `data/eval/golden_targets/`. Set `ENABLE_FAN_OUT=false`
to revert to plain single-specialist routing (§2a).

The supervisor calls the **dispatch planner** ([`plan_dispatch`, supervisor.py](vinchatbot/app/agents/supervisor.py))
instead of `route_intent`; the planner emits a PLAN = `list[{query,intent}]` in three modes:

```mermaid
flowchart TD
    msg["allowed, language-tagged message"]
    plan["plan_dispatch (supervisor.py)<br/>Tier-0 keyword fast-path → else LLM planner (DISPATCH_SYSTEM)"]
    collapse{"all assignments<br/>SAME intent?"}
    n{"len(plan)?"}
    single["SINGLE → route_intent(message)<br/>→ existing specialist node (BYTE-IDENTICAL to §2a)"]
    fan["fanout_node (graph.py)"]

    msg --> plan --> collapse
    collapse -->|"yes (over-fire)"| single
    collapse -->|"no / single"| n
    n -->|"1"| single
    n -->|">1 (distinct intents)"| fan

    subgraph fo["fanout_node — parallel, error-isolated"]
        gather["asyncio.gather over subtasks<br/>each: FRESH single-subtask msg +<br/>set_user_message(subtask) so the tools'<br/>structured-lookup/list-mode key off the SUBTASK"]
        l2["L2 reactive retry (cap=1):<br/>re-run a PUNTED subtask with a critique;<br/>keep good parts, can't fabricate"]
        syn["synthesis (SYNTHESIS_SYSTEM):<br/>merge grounded parts, dedupe,<br/>emit ToolMessages (citation union) + answer"]
        gather --> l2 --> syn
    end
    fan --> fo --> done["→ END (service layer guards as usual, §3)"]
    single --> done
```

Key engineering (each a measured fix, see [LOGS/PHASE1.33_LOG.md](LOGS/PHASE1.33_LOG.md)):
- **SINGLE is byte-identical**: a single-assignment plan defers to `route_intent` — the planner only decides
  single-vs-many, never the single-domain intent (letting it pick regressed scored cases).
- **Same-intent collapse**: a multi-assignment plan whose parts ALL route to one specialist is an over-fire →
  collapsed to SINGLE (one specialist answers all facets better from the whole-question context). Genuine
  DECOMPOSE/HEDGE always span ≥2 DISTINCT intents, so they still fan out.
- **Contextvar per subtask**: the turn pins `get_user_message()` to the whole compound; each subtask resets it
  to its own query (isolated per asyncio task) so the deterministic lookups don't key off the wrong text.
- **Synthesis emits the subtasks' ToolMessages** so the service-layer citation/faithfulness guards (§3) work on
  the **union** with no change; the audit is scoped to groundedness-only for a fused multi-domain answer.

## 3. Guard layering (cost-aware: cheap tier first)

```mermaid
flowchart TD
    msg["user message (+ retrieved content for indirect checks)"]
    rule{"Tier 0 — rule-based (cheap, always)<br/>regex + deobfuscate<br/>(base64 / zero-width / leetspeak)"}
    conf{"confident?"}
    safety{"Tier 1 — safety API (non-confident only)<br/>OpenAI omni-moderation (default)<br/>or Llama Guard 4"}
    scope{"Tier 2 — injection+scope classifier<br/>small instruct LLM (GUARD_MODEL)"}
    allow["allow → agent"]
    deny["block → guardrail response"]

    msg --> rule
    rule -->|hard block| deny
    rule -->|clear in-scope allow| allow
    rule -->|gray / out-of-scope| conf
    conf --> safety
    safety -->|unsafe| deny
    safety -->|safe| scope
    scope -->|injection/restricted/abusive/oos| deny
    scope -->|allow| allow
```

The above is the **input** guard (`resolve_guardrail_decision`). The **output** guard
(`resolve_output_decision`, Phase 1.25/A4, always-on) runs on the generated answer in `vinuni_agent.chat`:
(1) **sensitive-output / secret-leak** — markers + key/token patterns, scanned on the raw **and**
de-obfuscated/zero-width-stripped answer; (2) **graceful-degradation** when there are no citations or an
"unknown-answer" marker; (3) **faithfulness** — numeric/date/year grounding against the retrieved evidence.
Each returns a logged `OutputAuditDecision(action, reason)`; the bypass paths (time fast-path, conversational)
get the secret scan too. The **LLM output-audit critic** (`output_audit.py`, `ENABLE_OUTPUT_AUDIT`) is wired
but **rejected/off** (over-degraded correct answers) — kept for a future security use.

## 4. Module map

| Area | Modules |
|------|---------|
| API | `app/main.py`, `app/api/routes_chat.py`, `app/api/routes_ingest.py` |
| Agents | `agents/graph.py` (graph + `fanout_node`, default ON), `supervisor.py` (`route_intent` + `plan_dispatch` fan-out planner), `specialists.py`, `prompts.py` (incl. `DISPATCH_SYSTEM`/`SYNTHESIS_SYSTEM`), `tools.py`, `vinuni_agent.py`, `agents/output_audit.py` (critic, gated off) |
| Guards | `agents/guardrails.py` (input `resolve_guardrail_decision` + output `resolve_output_decision`: regex/deobf/secret/faithfulness), `agents/llm_guard.py` (injection/scope), `agents/safety_guard.py` (omni-moderation/Llama Guard) |
| RAG | `rag/retriever.py`, `rag/reranker.py`, `rag/context.py` (LITM/dedup/dynamic-k), `rag/query_engineering.py` (`is_point_lookup`/`is_list_lookup`), `rag/structured_lookup.py` (calendar+fee deterministic + list mode), `rag/policy_lookup.py` (doc-pin + auto-index), `rag/citations.py` |
| Core | `core/config.py` (all `ENABLE_*` flags), `core/cache.py` (Redis LLM+rerank cache), `core/observability.py` (per-stage ledger) |
| Ingest | `ingest/crawler.py`, `parsers.py`, `normalizer.py`, `chunker.py`, `indexer.py`, `assets.py`, `ocr.py` |
| Storage | `storage/qdrant_store.py`, `storage/vector_metadata.py` |
| LLM/embeddings | `llm/openrouter_chat.py`, `embeddings/openrouter_embeddings.py` |
| Eval | `scripts/run_eval.py` (`--runs N`, ledger, confidently-wrong), `data/eval/golden/*.json`, `data/eval/baseline.json` |
| Index build | `scripts/build_structured_index.py` (calendar+fee records), `scripts/build_policy_topic_index.py` (policy auto-index) |
