# VinChatbot frontend

Baseline student Q&A screen — **Pattern 1: Chat + Context Panel** (see `../docs/GUIDELINE.md`).
Chat on the left, official-source citations on the right.

## Run

The backend (FastAPI) must be up on `:8000` first:

```bash
# from repo root
uvicorn vinchatbot.app.main:app --reload --port 8000
```

Then the frontend:

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
```

`/api/chat` is proxied to `http://localhost:8000/chat` via `next.config.js`
(`BACKEND_URL` env var overrides the target). The UI only ever calls the FastAPI
`/chat` contract — it never imports an LLM SDK (hinge rule).

## What this renders

The backend encodes the *kind* of reply in `tool_trace` + `citations` +
`needs_human_review`, not the HTTP status. The panel distinguishes:

- **Grounded** → source cards (title, URL, snippet)
- **Conversational** → "no sources needed"
- **Refusal / out-of-scope** → route-to-official-source card (never a fake citation)
- **Couldn't ground** → declined + official routes

## Deferred to `/tcr-apply`

Per-message traffic-light confidence detail, click-source→passage scroll,
flag/report, stop-mid-flight, edit-last-message. Seams are left in
`responseState.ts` / `SourcesPanel.tsx`.
