# Plan — Ingesting new-seed (college / admissions / scholarship) data into the vector DB

## Context
**Decision (yours):** crawl ALL the new-seed subdomains (`admissions`, `cecs`, `chs`, `cbm`, `cas?`,
`library`, `scholarships`) **together with the ~603 student-relevant docs already crawled**, **clean** them,
and **ingest later** as one combined set (expand-first, single ingest).

**Why this needs a plan (the risk):** today's vector DB is fed by a **canonical, single-authority, structured**
corpus (policy/calendar/fee from `policy.vinuni`). The new sources are the opposite — **heterogeneous,
marketing-heavy, multi-authority, per-program** (program pages, FAQs, curricula, service blurbs). Dropping
them into the *same* collection creates dilution, retrieval-confusion, and — most dangerously —
**deterministic-layer pollution**. This plan enumerates every failure case and how we cope, then the
crawl→clean→ingest sequencing. (The post-benchmark orchestration roadmap is saved separately at
`LOGS/ADAPTIVE_ORCHESTRATION_ROADMAP.md`.)

---

## Problem map — every case, and how we cope

### A. What enters the vectors (noise / quality)
- **A1 — Marketing/blog/image dilution (proven).** College sites are WordPress like `vinuni.edu.vn` →
  `/category//people//event/`, `/wp-content/uploads/` images, date archives. *Cope:* **path-scoped crawl**
  (only high-value paths) + the `--student-only` kind filter (drops `image_asset`/`external_public_page`) +
  classify college pages as high-value kinds so they're **not** filtered back out.
- **A2 — Near-duplicates across sources.** The same program/fee/deadline stated on the main site, the college
  site, admissions, and policy. Exact dups → `_dedup_by_content_hash` (exists). Near-dups (paraphrases)
  survive → competing chunks. *Cope:* dedup + a **canonical-source preference** (doc-pin-style) so the
  authoritative page wins.
- **A3 — Boilerplate** (nav/CTA/footer on the new templates) → `strip_boilerplate` (exists); verify it covers
  the college/admissions templates (add patterns if needed).

### B. Retrieval confusion (after ingest)
- **B1 — Cross-source fact conflicts.** "tuition" now lives in financial policy (authoritative) **and**
  program pages **and** scholarship pages ("covers tuition"). *Cope:* trust tiers + metadata boost
  ([context.py:221-225](vinchatbot/app/rag/context.py#L221-L225)) keep `official_high` policy above casual
  mentions; the policy doc-pin keeps the tariff authoritative for fee questions.
- **B2 — Program ambiguity.** "What's the curriculum / the requirements?" with no program → CS + Nursing +
  Business curricula retrieved together. *Cope:* **populate `DocumentMetadata.college`/`.program`**
  (already-declared fields, document.py:172-173) from the subdomain+URL → program-filtered retrieval /
  clarification (roadmap D4).
- **B3 — Granularity confusion** (per-credit/semester/year × programs) → reuse the structured fee matrix +
  list mode (shipped).
- **B4 — Scope drift.** Admissions content is for *prospective* students; the bot serves *enrolled* students.
  *Cope:* category metadata + routing keep it in-bounds; the out-of-scope guard still refuses
  "should I apply / will I get in" advice.

### C. ⚠️ The sharp new one — deterministic-layer pollution (biggest risk)
- **C1 — Structured calendar/fee pollution.** Admission/scholarship/program pages say "classes begin…",
  "apply by…", "scholarship covers X", "tuition from Y". These are **official-domain** pages, so the A3
  filter (`is_official_record`, which only drops `external_low`) **does NOT exclude them** → they can emit
  spurious `calendar_event`/`table_record` rows → the **deterministic lookup returns a WRONG authoritative
  date/fee, bypassing rerank**. This is worse than vector dilution (it's confident + skips the guard path).
  *Cope:* flip the structured harvest from a **denylist** (drop external) to an **allowlist of authoritative
  sources** — `build_structured_index.py` keeps calendar/fee records **only** from the canonical academic-
  calendar PDF + the financial-tariff page (by `source_url` / `document_type`), not from any official page
  that happens to mention a date or amount.
- **C2 — Policy doc-pin auto-index** ([build_policy_topic_index.py](scripts/build_policy_topic_index.py))
  is locked to `document_type in {policy_html, financial_policy}` → college pages can't get those types →
  safe. *Verify* the new kinds never map to those types.

### D. Index mechanics / cost
- **D1 — Volume + ANN distractors.** More docs → embedding cost + a bigger candidate pool (more distractors,
  candidate-set jitter). *Cope:* the kind filter bounds growth; deterministic candidate sort (1.23a) + the
  de-noised eval hold the line.
- **D2 — Chunking mismatch.** FAQ pages are Q→A; curricula are course tables. *Cope:* **structure-aware
  chunking** — one Q/A per chunk for FAQs; verify the chunker on real samples.
- **D3 — Metadata completeness.** New docs need `category`/`subcategory`/`college`/`program`/`source_trust`
  populated or boosts/routing/filters misfire. *Cope:* extend `infer_source_kind`/`infer_category`
  ([normalizer.py](vinchatbot/app/ingest/normalizer.py)); derive college/program from subdomain+URL.
- **D4 — Volatile content.** Admission reqs + scholarship amounts change yearly (more than policy). *Cope:*
  periodic re-crawl + the hardened **incremental ingest** for refreshes (note the text-only-id caveat →
  `--recreate` for a full metadata reconcile).

### E. Guards / eval
- **E1 — Eval blindspot → expand the golden set along TWO tracks (after crawl+ingest).** No golden covers
  (a) the new content nor (b) the open failure modes. *Cope:* grow `data/eval/golden/` so it's the **shared
  measurement substrate for both this ingestion AND the orchestration roadmap**:
  - **(a) New-content cases — authored from the CRAWLED authoritative pages** (read the real facts →
    `required_facts`; sourced from the pages, NOT the bot's output, so this is not teaching-to-the-test):
    admission requirements (IELTS/GPA), a program curriculum/credit fact per college, a scholarship
    amount/eligibility, library hours/services. ~2–4 EN/VI each, held-out third per convention.
  - **(b) Failure-mode cases — covering the REMAINING problems in
    [LOGS/ADAPTIVE_ORCHESTRATION_ROADMAP.md](LOGS/ADAPTIVE_ORCHESTRATION_ROADMAP.md):** cross-domain compound
    (financial+calendar), underspecified/clarification, multi-hop (deadline→policy→fee), refusal-calibration
    (legit-policy-about-sensitive must ANSWER vs true-private must REFUSE), out-of-scope/ranking (must refuse
    or defer — not hallucinate "top-20 QS"), and confidence-calibration probes. (These are the roadmap's
    "Phase 0" sets — authoring them here means the roadmap directions become A/B-able the moment we start them.)
  - Both tracks become the standing regression guard; guards `adversarial`/`safety`/`unanswerable` stay 1.000.
- **E2 — Scope guard.** Admissions nudges scope → add adversarial cases; `adversarial`/`safety`/`unanswerable`
  must stay **1.000**.
- **E3 — Confidence mis-calibration** (battery #5) → more partial answers misfire `needs_human_review` →
  roadmap D7 (measurement-led).

### F. Serving
- **F1 — Multi-source answers** (program + policy + scholarship in one question) → the all-or-nothing /
  cross-domain failures → roadmap **D1 (part-aware degradation) + D2 (decompose)**.
- **F2 — Authority/citation.** Prefer + attribute the authoritative source; trust tiers + doc-pin enforce it.

---

## Crawl → clean → ingest sequencing (the agreed action)
Crawling the new seeds *well* depends on the classification changes (else it's another marketing dump that
gets filtered to nothing), so code comes first:

1. **Crawler scoping** ([crawler.py](vinchatbot/app/ingest/crawler.py)): add the new subdomains to
   `VINUNI_PUBLIC_SUBDOMAINS` (line 64) + a **per-site high-value PATH allowlist** mirroring
   `_is_policy_allowed_path`/`POLICY_LISTING_PATHS`, with a **tight depth** (their value is shallow:
   `/undergraduate/<program>/`, `/faqs/`, `/scholarships/`). Add seed URLs to `SEED_URLS`/`core_seeds.json`.
2. **Classification** ([normalizer.py](vinchatbot/app/ingest/normalizer.py)): extend `infer_source_kind`
   (new high-value kinds `program_page`/`admissions_page`/`faq_page`/`scholarship_page`; `library_page`
   exists) + add them to the `--student-only` KEEP set; extend `infer_category`; populate `college`/`program`.
   (Fetch 1–2 sample pages per site first to ground the path + kind patterns.)
3. **Crawl** the new seeds (writes raw only) + **validate gate** (doc count, error ratio, marketing-vs-content
   composition — same gate we just ran).
4. **Clean + ingest the COMBINED set** (the ~603 + new high-value), `--student-only`, into a **scratch
   collection** with `--recreate` (rollback-safe; production untouched until promote).
5. **C1 fix** — tighten `build_structured_index.py` to authoritative-source allowlist — then rebuild the
   structured + policy-topic indexes.
6. **Expand the golden set** (E1, after the content exists): author **(a) new-content cases** from the crawled
   authoritative pages + **(b) failure-mode cases** covering the remaining problems in
   `LOGS/ADAPTIVE_ORCHESTRATION_ROADMAP.md` (cross-domain / underspecified / multi-hop / refusal-calibration /
   out-of-scope-ranking / confidence). New `data/eval/golden/*.json` files; held-out third per convention.
7. **Re-benchmark against the expanded golden** (`run_eval --diff baseline --runs 3`): new + failure-mode
   cases scored, **0.968 held** on the prior set, guards **1.000**, structured-lookup spot-checked un-polluted
   (calendar/fee answers still cite the canonical sources), `confidently_wrong` not up → **promote** (point
   `.env` at the scratch collection) or fall back. Refresh `baseline.json` on promote.

---

## Files
- `crawler.py` (allowlist + path-scoping + seeds), `normalizer.py` (`infer_source_kind`/`infer_category` +
  college/program), `scripts/ingest_documents.py` (`--student-only` KEEP set — filter already added),
  `scripts/build_structured_index.py` (**authoritative-source allowlist for C1**), `data/eval/golden/*`
  (new cases), config flags as needed.

## Verification
`pytest -q` + `ruff` green for each code change. Then crawl → validate → ingest (scratch, `--recreate`) →
rebuild indexes → `run_eval --diff baseline --runs 3`: **≥0.968, guards 1.000, structured-lookup un-polluted
(spot-check a date/fee answer cites the canonical PDF/tariff, not a college page), confidently_wrong ≤
baseline**, new golden cases pass → promote. Keep production as rollback until clean.

## Risks / open
- **Low yield risk:** like the deepening, the college sites may be mostly marketing → few useful docs after
  filtering. The validate gate measures this; if low, the expansion's value is small (decide then).
- **Path-scoping needs real URL structures** → fetch samples per site to define the allowlists.
- `cas.vinuni.edu.vn` unconfirmed; `infer_source_kind` patterns must be authored from real pages.
- C1 (authoritative-source allowlist) is the must-not-skip change — without it, expansion can corrupt the
  deterministic calendar/fee answers that are currently the system's strongest feature.

## NOT now
This is the design + the agreed crawl→clean→ingest path; execution (starting with the crawler/normalizer
changes, then the crawl) proceeds on your go. No git commit unless asked.

---

## Golden-set expansion — concrete checklist (author AFTER crawl+ingest, from the crawled authoritative facts)
The new index MUST ship with golden cases covering BOTH the new content AND every problem surfaced this
session. Author `required_facts` from the real crawled pages (not the bot's output). Held-out third per
convention; guards `adversarial`/`safety`/`unanswerable` stay 1.000. Three buckets:

**Track A — new-content (from the newly crawled subdomains):**
- `admissions.json`: admission requirements (IELTS 6.5 / GPA 8.0), key deadlines, application steps, EN+VI.
- `programs.json`: a curriculum/credit/duration fact per college — CS & Data Science (cecs), Medicine &
  Nursing (chs), BBA (cbm), + a cas program. EN+VI.
- `scholarships.json`: a scholarship's amount/eligibility/deadline.

**Track B — roadmap failure-modes (from `LOGS/ADAPTIVE_ORCHESTRATION_ROADMAP.md`):**
- `cross_domain.json` (financial+calendar compound), `underspecified.json` (missing-term → clarify/default),
  `multihop.json` (drop-after-deadline → refund), `refusal_calibration.json` (legit-policy-about-sensitive
  must ANSWER vs true-private must REFUSE), out-of-scope ranking added to the guard set (must refuse/defer,
  not "top-20 QS"), and confidence-calibration probes.

**Track C — logged entity-handling cases (the presidents bug, F-ENUM/F-NAME):**
- `presidents.json` / leadership: "Who are VinUni's presidents?" → `required_facts=["Rohit Verma",
  "Tan Yap Peng"]` (enumerate BOTH — catches F-ENUM). Plus the **same person asked both name orders**
  ("Yap-Peng Tan" AND "Tan Yap Peng") → both must resolve (catches F-NAME).

Re-run the presidents / name-order live probes on the NEW index during the re-benchmark; if they still fail,
they become the standing regression cases for the entity-alias/enumeration work (roadmap D1/D8).
