# Phase 1.24 — Ingest-time policy topic index (generality fix for the doc-pin)

> **Status: QUEUED (not started).** Forward design. Build AFTER the 1.21/1.21b pin promotes (and after the
> 1.23 determinism/cache phase), so we generalize a *proven* mechanism. Pairs with `policy_lookup.py` (1.21) and mirrors the
> `build_structured_index.py` ingest-artifact pattern (1.19).

## Why (the problem this solves)
The policy doc-pin (Phase 1.21/1.21b) works, but its topic index is a **hand-curated** `keyword → slug`
table for **17** student-facing policies (`POLICY_TOPICS` in
[policy_lookup.py](../vinchatbot/app/rag/policy_lookup.py)). Two real limits the user flagged:
1. **It does not scale to staff-uploaded policies.** When admin upload lands (Phase 3 doc-management),
   a brand-new policy is **not** in the map → no pin → the VI "magnet" mis-citation returns for it.
2. **It is not universal coverage.** Only 17 of ~155 canonical pages are mapped; the rest fall back to
   plain retrieval.

**Key separation (why this is a small, safe change):** the pin *mechanism* (match → fetch canonical by
`source_url` → prepend) is already fully general. **Only the *index* is hand-coded.** So the fix is to
stop hand-writing the index and **generate it at ingest** — no change to matching or pinning.

## Design
1. **Ingest artifact `data/processed/policy_topic_index.json`** (compact, like `structured_index.json`).
   A new `scripts/build_policy_topic_index.py` scans every canonical `policy_html` / `financial_policy`
   page in the corpus and emits, per page: `source_url`, and topic keywords **auto-derived** from its
   `document_title` + section headings (+ optional 1–2 sentence LLM topic summary, cached by
   `content_hash`). Distinctive-token filtering (reuse `context._salient_terms` + the stopword list).
2. **Staff-provided keywords (the clean production source).** When admin uploads a policy (Phase 3
   `POST /admin/documents`), capture an optional **topic / keywords / audience** field → written into the
   index as **high-confidence** entries. The uploader, who knows the policy, tags it once; engineering
   never edits code.
3. **`policy_lookup` loads the persisted index** instead of the hardcoded constant. Resolution order:
   **(a)** staff-provided keywords (highest confidence) → **(b)** the curated 17 (kept as seed/overrides)
   → **(c)** auto-derived long-tail. `match()` stays **single-winner + fail-open**; ambiguous/no clear
   winner → no pin (byte-identical vector path). **Fallback:** if the JSON is missing, fall back to the
   in-code curated map → no regression / no hard dependency.
4. **Regeneration runbook:** after every ingest/upload, regenerate `policy_topic_index.json` (same
   discipline as the structured index; one line in the ingest pipeline / admin reindex hook).

## Companion (optional, separate) — the no-index universal backstop
For pages with *no* index entry, the magnet bug can still bite. A config-free backstop: **detect &
down-weight "magnet" docs** at retrieval — penalize documents that are very long/broad or that rank
highly across *many unrelated* queries, so a focused page wins on its own topic. Covers uploads with zero
config. Bigger, riskier (Lever 2 was a weak version) → its own research phase, not part of 1.23.

## Files
- `scripts/build_policy_topic_index.py` (new) — corpus scan → `policy_topic_index.json`.
- `vinchatbot/app/rag/policy_lookup.py` — load the persisted index (curated map becomes the fallback/seed);
  matching unchanged.
- (Phase 3) admin upload form + `POST /admin/documents` — capture topic/keywords/audience.
- `tests/test_policy_lookup.py` — index build/load/fallback; precision still 34/34 on golden; **simulate an
  "uploaded" policy NOT in the curated 17** and assert it becomes pin-eligible.

## Verification
- Offline: matcher precision over the 34 golden must stay **34/34, 0 wrong, 0 collisions**; new
  build/load/fallback tests; `ruff` + `pytest -m "not live"` green.
- Coverage probe: pick a few canonical pages OUTSIDE the curated 17, confirm auto-derived keywords pin them
  (and that ambiguous ones correctly fail open rather than mis-pin).
- Live A/B should be **unchanged** for the curated topics (same pins fire) — this phase is about *coverage/
  scalability*, not the measured slice. Re-run the pin A/B to confirm no regression vs the 1.21b baseline.

## Gating
Reuse `ENABLE_POLICY_DOC_PIN` (no new flag). The index source becomes file-backed with the curated map as a
safe fallback. Promote with the same eval-gate discipline.
