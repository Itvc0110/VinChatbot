# GUIDELINE — VinChatbot (student academic Q&A)

> PRD: see [PRD.md](PRD.md) (v0.2). Tech stack from PRD §11: React/Next chat UI → FastAPI `POST /chat` → LangGraph ReAct agent → Qdrant hybrid retrieval → OpenRouter (cheap router + strong generator).

## UI pattern
**1. Chat + Context Panel**

Why this pattern: The one surviving valuable story is "Student asks an academic/service question → AI answers grounded in official VinUni sources, *with citations*, and refuses cleanly when the evidence isn't there." The core UX problem is exactly what Pattern 1 solves: the student cannot tell what's backed by a real source versus invented, and a wrong-but-confident fee/deadline/policy is the worst outcome (PRD §8, §12). The chat stream carries the answer; the evidence panel makes grounding visible.

**Panel payload = sources (citations).** This is a true RAG corpus (Qdrant over crawled VinUni pages/PDFs), so the panel shows retrieved source cards: title, source URL/kind, `category`, trust tier (`official_high` vs `external_low`), and the passage that grounds the claim. Never fabricate a source — when retrieval returns nothing, the panel shows the refusal/route-to-office state, not a fake citation. For procedural answers (PRD G3), the panel still anchors each step's "where the rule comes from."

## Visual style
**Data-dense professional** — compact, low-contrast, dashboard feel. The 60/40 chat-vs-evidence split needs the panel to surface several source cards + metadata at once without scrolling, so dense beats airy here.

Concrete rules:
- Compact sans-serif (system UI stack or Inter), 13–14px body; tight line-height (~1.4); generous use of metadata rows over whitespace.
- Low-contrast neutral surface (e.g. slate/gray-50 background, gray-200 borders); reserve saturated color **only** for trust signals.
- Small corner radius (4–6px); thin 1px borders to separate chat bubbles, source cards, and metadata chips.
- Source cards are dense rows: title + URL + category chip + trust-tier badge on one or two compact lines.
- Confidence/grounding uses traffic-light color **paired with a text/icon label** (never color alone) — green = grounded/high, yellow = partial, red = ungrounded/refused.
- Monospace only for any raw identifiers (policy codes, terms) shown in the panel.

## User flow (3 steps)
1. Student types a question (VI or EN) into the chat input — optionally via a quick-prompt chip.
2. App sends it to FastAPI `POST /chat`; the LangGraph ReAct agent runs input guardrail → metadata-routed hybrid retrieval over Qdrant → rerank → strong generator (via the OpenRouter wrapper) → output guardrail (citation + faithfulness). Returns the answer **plus** the retrieved source chunks + metadata.
3. Student reads the answer in the chat stream; the right-hand evidence panel renders the source cards for *that* answer (latest only). Student can click a source to inspect the grounding passage, or see a clean refusal + "ask this office / official link" when evidence is insufficient.

## T·C·R checklist for this pattern

### T — Transparency (what AI work is visible)
- [ ] Layout splits ~60/40 — chat left, evidence panel right; each assistant message exposes its trust signals.
- [ ] Each answer shows honest signals: N retrieved sources (real corpus), per-source trust tier, and a grounding/confidence indicator labeled for what it actually is (e.g. `<N sources>`, `<faithfulness: grounded/partial>` — not a vague single score).
- [ ] Traffic-light grounding state (green grounded / yellow partial / red ungrounded-or-refused), always paired with a text label.

### C — Control (what user can stop / edit / override)
- [ ] Click a source card → scroll/expand to the exact grounding passage; click a category/trust chip → understand (or filter) the basis.
- [ ] Flag/report button under each assistant message → inline "this answer is wrong / missing a source" correction form (feeds the admin gaps view, PRD FR-E3).
- [ ] Stop button aborts an in-flight `/chat` request; edit-last-question to refine without retyping (preserves the conversation).

### R — Recovery (validation + retry + undo)
- [ ] Out-of-scope / private-data / injection inputs are warned or blocked **without wiping the conversation** (PRD FR-G1/G3); refusal is friendly, bilingual, and routes to the official source/office (FR-G4).
- [ ] try/catch around the `/chat` call → error bubble with Retry; a retry must preserve the prior turns and any pinned sources.
- [ ] Short/empty input validated inline (warn, don't block); network failure preserves the conversation and offers reconnect/retry.

## Hinge rule
All LLM calls go through the backend wrapper **`vinchatbot/app/llm/openrouter_chat.py`** (and embeddings via `app/embeddings/openrouter_embeddings.py`). The React/Next UI never imports an LLM/provider SDK and never calls OpenRouter directly — it only calls FastAPI `POST /chat`. Swap providers/models = edit that one wrapper file, not the agent or the UI.

## What NOT to build yet
- **Admin surface** (document upload/URL management, re-index, gaps dashboard, eval dashboards — FR-X4/FR-E), **auth/roles beyond a mock demo account** (FR-X1/X2), and **persisted Postgres chat history** (FR-X3). The student Q&A screen is the valuable story; these are operator/platform scaffolding.
- **Phase 2 personalization** (mock student DB, profile tools, personal-vs-general intent — FR-P). Same actor/screen, but an explicit stretch goal — do not branch the panel into "profile mode" yet.
- T·C·R features come in sequence, not all at once: ship the **baseline chat + sources panel first**, then layer T → C → R via `/tcr-apply`.
- Pattern-1 traps to avoid: (1) the UI calling the LLM directly instead of going through FastAPI/`openrouter_chat.py` — breaks the hinge; (2) **fake citations** when the corpus returns nothing — show refusal, never invent a source; (3) an out-of-scope block implemented as a modal that wipes the conversation; (4) the evidence panel showing the full history of every answer instead of the latest only.
