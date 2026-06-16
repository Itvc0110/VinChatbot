# VinChatbot — Architecture & Flow

Visual reference for how data and a chat turn move through the system. Diagrams are
Mermaid (render in GitHub and the VS Code Mermaid preview). Pairs with [PRD.md](PRD.md) /
[UPDATE_PLAN.md](UPDATE_PLAN.md).

> State (2026-06-16, post-Phase 1.7): the flows, multi-agent routing, layered guards, and module
> map below match the current code. The layered safety guard (OpenAI omni-moderation) is **live**;
> the Phase 1.4 faithfulness output-gate fix is in §2. Serving pipeline is **plain-text** (markdown
> OFF) on **`gpt-4o-mini`**. Retrieval now includes **Phase 1.6 fuse→rerank-once** and **Phase 1.7
> adaptive point-lookup routing** (`ENABLE_ADAPTIVE_RETRIEVAL=true`): point-lookups read the **full
> section** (the parent-doc machinery, previously gated off, is now used for them) + a strict
> extraction prompt. Full detail in **§2b**. See [PHASE1.6_LOG.md](LOGS/PHASE1.6_LOG.md) /
> [PHASE1.7_LOG.md](LOGS/PHASE1.7_LOG.md).

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
        sup["Supervisor (supervisor.py)<br/>route intent: calendar|policy|financial|services"]
        spec["Selected specialist (1 of 4)<br/>ReAct agent, own prompt + tool subset"]
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

Every tool call enters `_search` ([tools.py](vinchatbot/app/agents/tools.py)). A cheap router
(`is_point_lookup`, [query_engineering.py](vinchatbot/app/rag/query_engineering.py)) splits **prose**
from **point-lookups** (exact dates/amounts/codes — routed category `calendar`/`financial`, or a
year/term/amount in the query). Two shipped levers: **Phase 1.6** reranks the RRF-fused pool **once**
(not per variant — ~67% fewer rerank calls); **Phase 1.7** routes point-lookups to **full-section
reading + a strict extraction prompt**, with a domain split on query expansion (calendar OFF for
precision; financial ON + a cross-lingual English variant for recall). Toggles:
`ENABLE_RERANK_AFTER_FUSION`, `ENABLE_ADAPTIVE_RETRIEVAL` (both default **true**; set either `false`
to revert).

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

How the "multi-agent" actually works today: the supervisor (a cheap LLM intent classifier
with a keyword-heuristic fallback) routes each turn to **one of four specialist ReAct
agents**. Each specialist is its own `create_agent` instance with its **own system prompt
and a focused subset of tools**. Tools are **in-process Python functions** (`tools.py`,
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

## 4. Module map

| Area | Modules |
|------|---------|
| API | `app/main.py`, `app/api/routes_chat.py`, `app/api/routes_ingest.py` |
| Agents | `agents/graph.py`, `supervisor.py`, `specialists.py`, `prompts.py`, `tools.py`, `vinuni_agent.py` |
| Guards | `agents/guardrails.py` (regex/deobf/faithfulness), `agents/llm_guard.py` (injection/scope), `agents/safety_guard.py` (omni-moderation/Llama Guard) |
| RAG | `rag/retriever.py`, `rag/reranker.py`, `rag/context.py` (LITM/dedup/dynamic-k), `rag/query_engineering.py`, `rag/citations.py` |
| Ingest | `ingest/crawler.py`, `parsers.py`, `normalizer.py`, `chunker.py`, `indexer.py`, `assets.py`, `ocr.py` |
| Storage | `storage/qdrant_store.py`, `storage/vector_metadata.py` |
| LLM/embeddings | `llm/openrouter_chat.py`, `embeddings/openrouter_embeddings.py` |
| Eval | `scripts/run_eval.py`, `data/eval/golden/*.json` |
