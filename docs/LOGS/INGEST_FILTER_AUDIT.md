# Ingest filter audit — what `--student-only` keeps vs drops, and why

**Date:** 2026-06-24 · **Trigger:** the President/leadership bug ("VinUni có những hiệu trưởng nào?" →
missed Tan Yap Peng). Root cause was the ingest filter, not the prompt or retrieval.

**Purpose of this doc:** so a future "the bot doesn't know about X" report does **not** require re-auditing the
filter from scratch. Read the decision matrix below; if X's pages sit in a **KEEP** bucket they're indexed
(it's a retrieval problem), if they sit in a **DROP** bucket the filter is discarding them (add the section —
see "How to fix a new false-drop"). The ingest log now prints what was dropped (see "Detection") so you can
confirm in seconds.

---

## The systematic failure mode (why this recurs)

`--student-only` (in [scripts/ingest_documents.py](../scripts/ingest_documents.py)) drops docs whose
`source_kind` is in `NOISE_SOURCE_KINDS = {image_asset, file_asset, external_public_page, link_reference}`.
`source_kind` is derived **purely from the URL** by `infer_source_kind`
([normalizer.py](../vinchatbot/app/ingest/normalizer.py)).

The trap: the **main `vinuni.edu.vn` domain is official** (`classify_domain` → `official`) but is mostly
news/marketing, so `infer_source_kind` **default-drops the whole domain to `external_public_page`** unless the
URL matches a hand-maintained high-value pattern. That list was **incomplete** — `/people/` (faculty +
leadership bios) wasn't on it, so 989 bio pages (incl. the President) were silently discarded. The same
allowlist-too-narrow flaw hit the college sites (VI `/bac-dai-hoc/`, `/medical-doctor-program/`, `/uropcecs/`).

**Second instance of the same flaw (PDFs):** `infer_source_kind` kept PDFs **only on `policy.vinuni`** —
every other VinUni host's PDFs fell to `external_public_page`. That silently dropped official **registrar
forms** (FRM02/06/07/09/10 — petition, change-of-program, defer/withdraw, transfer-credit, return-from-leave),
**experience student handbooks** (STUDENT-GUIDE-2025-2026, International-Student-Welcome-Guide, Residential-
Living-Guidelines), and **college curricula/notices** (Bachelor-of-Nursing CurriculumFramework, Full-STUDENT-
GUIDE, PhD-CS admission notice). Fixed by `_pdf_kind`: official student-service hosts keep ALL PDFs;
admissions/college keep document-like PDFs; the main domain keeps document-named PDFs; posters/flyers/
conference-slides/partner one-pagers (UCLA.pdf, *-poster, *-flyer) still drop.

**Two structural fixes applied so this surfaces itself next time:**
1. `_effective_source_kind` now **re-derives** the kind from the URL for *all* `vinuni.edu.vn` hosts at
   ingest, so a classifier fix takes effect **without a re-crawl** (the classifier is the single source of truth).
2. The ingest run now **logs a drop-report** (`Dropped-by-kind` + `Top dropped VinUni sections`). A high-count
   `main/people/` or unfamiliar-section line is the early-warning that a high-value section is being dropped.

---

## Decision matrix (audit of all 13,547 raw docs, kind re-derived with the current classifier)

### KEEP — indexed by `--student-only`
| Source | Kind | Notes |
|---|---|---|
| `policy.vinuni` policies/tariff/catalog | `policy_pdf/policy_html/financial_policy/policy_listing/academic_catalog` | canonical authority |
| `registrar/library/experience.vinuni` | `registrar_page/library_page/student_life_page` | per-host |
| `admissions.vinuni` reference + FAQ | `admissions_page/faq_page` | path-gated to reference sections |
| `scholarships.vinuni` (all) | `scholarship_page` | small dedicated site, kept broadly |
| 4 colleges (cecs/chs/cbm/cas) program pages | `program_page` | path-gated; now incl. `/bac-dai-hoc/ /medical-doctor-program/ /urop*/` |
| **MAIN `vinuni.edu.vn` `/people/`** | **`profile_page`** | **faculty + leadership bios — the fix** (989 docs) |
| MAIN `/academics/` | `program_page` | academics landing/overviews |
| MAIN `/student_life/`, `/global_exchange/` | `student_life_page` | student life + exchange/study-abroad |
| MAIN `/about*/ /leadership/ /governance/` | `about_page` | institution/leadership context |
| registrar/experience/library PDFs | `registrar_page/student_life_page/library_page` | forms, handbooks, guides — keep ALL |
| admissions/college document PDFs | `admissions_page/program_page` | curricula, notices, regulations (drop poster/flyer) |
| MAIN document-named PDFs | `program_page` | e.g. Workstudy-Program-Guideline (drop conference slides/partner one-pagers) |
| any host `*.xlsx/.csv/.docx`, calendar PDFs | `spreadsheet/csv/docx/calendar_*` | format-based, unchanged |

### DROP — intentionally discarded (genuine noise)
| Bucket | ~count | Why dropped |
|---|---|---|
| `/wp-content/uploads/*` images | 4,983 | `image_asset` — pictures |
| MAIN top-level news slugs | ~2,000 | descriptive title slugs, depth-1, not under a reference section |
| `/category/ /tag/` (WordPress archives) | 400 | navigation/aggregation |
| `/event/` (all hosts) | ~240 | event announcements |
| `/page/N/?s&q&post_type=` (search pagination) | ~190 | search-result pagination, no content |
| `/job/ /jobs/` (incl. careerportalvinuni.talent.vn) | ~180 | recruitment, not student reference |
| `/research/event/`, `/research/seminar-recap/` | ~360 | research news/seminars (not student services) |
| MAIN `/wp-content/*.pdf` (partner MoU PDFs e.g. UCLA/Korea) | 114 | low student value; revisit if exchange-agreement Qs arise |
| admissions `/research-projects/`, `/du-an-nghien-cuu/` | 68 | prospective-student showcase/marketing |
| chs `/spark*/` CME courses, `/medical-simulation-center/` etc. | ~80 | professional CE / facility marketing, not enrolled-student services |
| **EXTERNAL** (sc.edu, sheffield, aacrao, cornell, apple, play.google, talent.vn) | many | non-VinUni; also dropped by `--vinuni-only` |

---

## Detection — how a future false-drop shows up

Every `--student-only` ingest now logs:
```
Filtered to student-relevant kinds: <before> -> <after> (-<dropped>)
Dropped-by-kind: {'image_asset': N, 'external_public_page': M, ...}
Top dropped VinUni sections (watch for high-value content here): ['main/people/=989', 'main/research/=360', ...]
```
If a section you'd expect to answer questions (e.g. `main/<new-section>/=<big N>`) appears here, it's being
dropped → add it as a keep-section.

## How to fix a new false-drop (one place each)
- **Main `vinuni.edu.vn` section** → add `"<section>": "<kept-kind>"` to `_MAINSITE_KEEP_SECTIONS` in
  [normalizer.py](../vinchatbot/app/ingest/normalizer.py).
- **Expansion-host (admissions/college) section** → add the first-path slug to `_SECTION_PREFIXES`.
- New kinds must also be added to `DocumentType` ([schemas/document.py](../vinchatbot/app/schemas/document.py))
  and kept OUT of `NOISE_SOURCE_KINDS`. Add a `test_normalizer.py` assertion. Because `_effective_source_kind`
  re-derives, re-ingest applies it **without a re-crawl**.

## Verification evidence (the regression this fixed)
`Tan Yap Peng` chunks present: `vinuni_full_e5` (production, no filter) = **10**; `vinuni_full_e5_v2`
(built **with** `--student-only`, pre-fix) = **0**. So the filter was a strict regression on leadership/
faculty queries; the v2 rebuild with the path-aware filter restores them.
