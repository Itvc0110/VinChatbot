# Phase 1.3 — Ingestion v2 (Markdown parsing + structure-aware chunker) — Log

Plan: markdown-first parsing + LangChain header/token chunker, validated on a scratch
collection before promoting. Baseline to beat: **92.5%** (Phase 1.2, 80 cases).

## Built (code complete, 89 offline tests + ruff green; toggle `ENABLE_MARKDOWN_PARSING`)
- `parse_html` → trafilatura `output_format="markdown"`; structured-HTML path emits `- ` list items.
- `parse_pdf_bytes` → `pymupdf4llm` per-page Markdown (`_pdf_pages_to_markdown`), text fallback.
- `parse_docx` (python-docx → Markdown) + crawler/`infer_source_kind` DOCX routing.
- Chunker v2: LangChain `MarkdownHeaderTextSplitter` → `RecursiveCharacterTextSplitter.from_tiktoken_encoder`
  (512-token, header-aligned `section_path`), with paragraph fallback + `# Trang N` page-carry.
- `strip_boilerplate` now tolerates `- `/`#` prefixes.

## Validation result — REGRESSION (not promoted)

Scratch crawl (markdown, 749 docs, 171/171 seeds) → scratch collection
`vinuni_phase3_test` (**14,781 chunks** vs baseline 7,781) → 80-case eval.

| Category        | Phase 1.2 | **Phase 1.3 (markdown)** |
|-----------------|---------|------------------------|
| **overall**     | 0.925   | **0.738** ⬇            |
| financial       | 0.875   | **1.000** ⬆            |
| adversarial/safety | 1.0/1.0 | 1.0/1.0             |
| calendar        | 0.929   | 0.643 ⬇                |
| policy_conduct  | 0.714   | 0.429 ⬇                |
| multiturn       | 1.000   | 0.750                  |
| unanswerable    | 1.000   | 0.600 ⬇ (over-answers) |
| services        | 0.800   | 0.200 (4/5 = missing `library` doc, a coverage confound) |

Report: `data/eval/results/eval_20260614T045334Z.json`.

**Root cause (retrieval, not content):** Markdown + 512-token header splitting **doubled the
chunk count**, diluting the high-value docs. The **calendar PDF** becomes 19 noisy markdown
fragments (pymupdf4llm emits "picture omitted / Start of picture text") and is **outranked by
registrar announcement pages** for calendar queries; the LOA policy similarly degrades. More
weak-match chunks also made the agent **over-answer** unanswerable cases. Markdown clearly
**helped financial** (clean HTML tables → 100%), so the technique isn't worthless — it's the
PDF noise + over-fragmentation that hurt.

**Decision: do NOT promote.** Main collection `vinuni_documents` is untouched (still 92.5%);
markdown code stays behind `ENABLE_MARKDOWN_PARSING` for a possible tuned retry. Scratch
artifacts (`data/raw_phase3`, `data/processed_phase3`, `vinuni_phase3_test`) are disposable.

## Tuning attempt (PDF→text, 1024 tokens, h1/h2 split)

Root cause confirmed by inspecting real chunks: pymupdf4llm rendered the calendar date-grid
as a **markdown table** (`|||| ... <br>`), which broke the `calendar_event` regex
(**59 → 8** garbled events) and flooded retrieval with tiny PDF fragments (`registrar_page`
avg 437 chars). Tune: `ENABLE_PDF_MARKDOWN=false` (PDFs back to plain text → events restored
to **67**), `CHUNK_MAX_TOKENS=1024`, header split on h1/h2 only; HTML markdown kept.

Re-crawl (914 docs) → scratch ingest (13,813 chunks) → eval:

| Category       | Phase 1.2 (proven) | md-v1 | **md-tuned** |
|----------------|------------------|-------|--------------|
| **overall**    | **0.925**        | 0.738 | **0.812**    |
| calendar       | 0.929            | 0.643 | 0.857 ⬆      |
| financial      | 0.875            | 1.000 | 0.750        |
| policy_conduct | 0.714            | 0.429 | 0.429        |
| multiturn      | 1.000            | 0.750 | 1.000        |
| unanswerable   | 1.000            | 0.600 | 0.800        |
| services       | 0.800            | 0.200 | 0.200 (missing `library` doc confound, 4/5) |
| adversarial/safety | 1.0/1.0      | 1.0/1.0 | 1.0/1.0    |

Report: `data/eval/results/eval_20260614T061257Z.json`. Tuning recovered a lot (calendar
64→86, multiturn back to 100), but **81.2% still trails the proven 92.5%** (~86% even after
adjusting for the library confound): HTML markdown fragments policy docs (LOA/academic-
integrity/sexual-misconduct fail despite being present) and the larger corpus over-answers
some unanswerable cases.

## Decision: REVERT (markdown shelved)

Per the plan ("if tuning doesn't beat the proven pipeline, revert"): set
`ENABLE_MARKDOWN_PARSING=false` as the **default**. The proven plain-text pipeline (main
collection `vinuni_documents`, 92.5%) is unchanged. The markdown code stays gated off for a
future revisit. **DOCX support is a genuine keeper** (new dtype; works with markdown off via
the fallback chunker). Scratch artifacts (`data/raw_phase3`, `data/processed_phase3`,
`vinuni_phase3_test`) are disposable.

**Kept from Phase 1.3:** DOCX parsing/routing; tiktoken/splitter deps; the gated markdown
path; this analysis. **Net production change: none to the proven pipeline** (markdown off).
