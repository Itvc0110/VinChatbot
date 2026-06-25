# Phase 1.28 — Ingest-filter overhaul (the `--student-only` silent-drop bugs) + v2 rebuild

> Triggered by the live President bug (user, 2026-06-24): "VinUni có những hiệu trưởng nào?" → missed
> Tan Yap Peng / Rohit; "Yap-Peng Tan" not found but "Tan Yap Peng" found (name-order). Root cause turned out
> to be the **ingest filter**, not the prompt/retrieval. Full keep/drop matrix: [INGEST_FILTER_AUDIT.md](INGEST_FILTER_AUDIT.md).
> Scratch collection `vinuni_full_e5_v2`; production `vinuni_full_e5` (0.968/188) untouched. **Not promoted.**

## 1.28a — Filter deep-audit + path-aware classifier fix — DONE (not yet promoted)

### Trial
The president content **exists** in raw (10 docs name Tan Yap Peng, incl. his `/people/tan-yap-peng-2/` bio),
but `vinuni_full_e5_v2` (built with `--student-only`) had **0** Tan Yap Peng chunks vs production's 10 — a
strict **regression**. Root cause: `infer_source_kind` **default-drops the whole official `vinuni.edu.vn`
domain to `external_public_page`** unless the URL matches a hand-maintained allowlist, and that list was
incomplete. A full audit of all 13,547 raw docs found **three** instances of the same flaw:
1. Main-domain reference **sections** dumped to noise: `/people/` (989 faculty+leadership bios), `/global_exchange/`
   (60), `/student_life/` (14), `/academics/` (6), `/about//governance/`.
2. College **program slugs** false-dropped by a too-strict first-segment gate: VI `/bac-dai-hoc/`,
   `/medical-doctor-program/`, `/uropcecs/`, college `/people/`.
3. **PDFs** kept only on `policy.vinuni` → official **registrar forms** (FRM02/06/07/09/10), **experience
   student handbooks** (STUDENT-GUIDE-2025-2026, Welcome-Guide, Living-Guidelines), **college curricula/notices**
   (Bachelor-of-Nursing CurriculumFramework, PhD-CS admission notice) all silently dropped.

### Experiment (the fix — all in [normalizer.py](vinchatbot/app/ingest/normalizer.py) + ingest)
- **Main-domain path-aware**: `_MAINSITE_KEEP_SECTIONS` (`people→profile_page`, `student_life/global_exchange→
  student_life_page`, `academics→program_page`, `about/leadership/governance→about_page`); everything else
  (news slugs, `/category//tag//event//job//research//wp-content/`) still → `external_public_page`.
- **College gate widened**: added `bac-dai-hoc`, `medical-doctor`, `urop` to `_SECTION_PREFIXES`; `/people/`→
  `profile_page` on college hosts too.
- **Host-aware PDF rule** (`_pdf_kind`): student-service hosts keep ALL PDFs; admissions/college keep
  document-like PDFs; main domain keeps document-named PDFs; `poster/flyer/banner/brochure` + bare partner
  one-pagers (UCLA.pdf) drop. Verified keep/drop on the real dropped filenames — **all 16 sample cases match**.
- **Structural future-proofing (so this never needs a re-audit)**: (a) `_effective_source_kind` now **re-derives**
  the kind for all `vinuni.edu.vn` hosts → classifier fixes apply **without a re-crawl**; (b) ingest logs a
  **drop-report** (`Dropped-by-kind` + `Top dropped VinUni sections`) so a future false-drop surfaces in the log.
- New `DocumentType`: `profile_page`, `about_page`. `infer_category` for `/people/`→(general,people),
  exchange/student_life, academics. Tests: +3 dedicated `test_normalizer` cases. **366 offline green, ruff clean.**

**A/B of the filter (re-derived kind over all raw):** kept docs **1,208 → 2,435** (+1,227); drop-report clean
(top drops all genuine noise: `wp-content` 4,569, `research` 361, `category` 310, `tag` 90, `job` 77 — `/people/`
**no longer in the dropped list**). Verified the policy-corpus "83-doc recovery" my first head/tail scan reported
was a **scan artifact** (a proper parse of every `policy.vinuni` doc → 0 mis-stored as noise); did not claim it.

### Progress
Filter fix complete + documented; not promoted (validation pending). Next: rebuild v2 (1.28b).

## 1.28b — Incremental v2 rebuild — DONE

### Experiment
`QDRANT_COLLECTION=vinuni_full_e5_v2 python ingest_documents.py --student-only --incremental`. Incremental
reuse worked as designed: `total=14200 unchanged=10911 added=3289 deleted=22 overlap=10911` — only the ~3,289
new chunks embedded (e5 via OpenRouter), the rest reused. v2: **10,933 → 14,200 chunks**. (Two false starts:
the first run was block-buffered and a session restart killed a detached run mid-`structured_records` write →
relaunched via PowerShell `Start-Process` to survive teardown. The 15-min raw-load is the real bottleneck.)
Production untouched (`.env` still `vinuni_full_e5`). Verify: v2 Tan Yap Peng chunks **0 → 5**; `/people/`
chunks **65 → 993**.

## 1.28c — President re-probe (per-case decode, on v2) — MIXED

### Experiment (6 live probes, `QDRANT_COLLECTION=vinuni_full_e5_v2`)
| Case | Before (v2 pre-fix) | After (v2 post-fix) | Verdict |
|---|---|---|---|
| "Tan Yap Peng là ai?" | refused, conf 0 | answers bio (Professor, Princeton PhD, NTU), conf 0.78 | ✅ over-refusal fixed |
| "Yap-Peng Tan là ai?" | refused, conf 0 | answers same person, conf 0.78 | ✅ **F-NAME fixed** |
| "Who is Yap-Peng Tan?" | refused | answers, conf 0.66 | ✅ |
| "Rohit Verma là ai?" | weak | "Founding Provost/Rector, on leave from Cornell" | ✅ correct |
| "VinUni có những hiệu trưởng nào?" | named only Rohit | lists Bangsberg / El Ghaoui / Lê Mai Lan, conf 0.82 | ❌ **confidently wrong** |
| "Who have served as Presidents?" | — | "Dr. Le Mai Lan" | ❌ wrong |

**Decode of the enumeration failure (F-ENUM):** the corpus **overloads "President"** — `Lê Mai Lan` is cited
across many pages as "President of VinUniversity / University Council" (she is **Council President / Vingroup
Vice-Chair**), `Rohit Verma` signs 2021 policy PDFs as "HIỆU TRƯỞNG" (**Rector**), `Tan Yap Peng` is the 2025
Rector (only stated in the **dropped** leadership announcement). So enumeration stitches the most-mentioned
"President" (Lê Mai Lan) → grounded but **wrong role**. The 993 recovered bios made enumeration *more*
confidently-wrong. This is an entity/role problem, not a filter one.

### Progress
- **Filter fix = net win**: F-NAME (name-order) + over-refusal **resolved**; forms/guides/curricula/bios
  recovered. **F-ENUM still open** and now confidently-wrong → routed to **D9** (intent-satisfaction validator,
  designed in [ADAPTIVE_ORCHESTRATION_ROADMAP.md](ADAPTIVE_ORCHESTRATION_ROADMAP.md)) + D8 (role/alias table) +
  content (keep the leadership announcement).
- **Next (this phase, per user sequence):** implement **D9 intent-satisfaction validator** (extend
  `audit_output` groundedness → groundedness+intent; hedge instead of confidently-wrong) + golden cases →
  then citation-too-narrow + scholarship fixes → full `--diff baseline --runs 3` → promote v2.
- **NOT promoted; no git commit.**

## 1.28d — D9 intent-satisfaction validator — IMPLEMENTED + A/B (flag default-off)

### Trial
The 1.28c enumeration failure ("who are the presidents" → confidently lists wrong people) is *grounded* —
the existing critic ([output_audit.py](vinchatbot/app/agents/output_audit.py) `audit_output`) only checks
"is the claim supported", which passes "Lê Mai Lan, President of University Council" for a **Rector** question.
Gap: **grounded ≠ answers-the-specific-question**. Design captured as D9 in
[ADAPTIVE_ORCHESTRATION_ROADMAP.md](ADAPTIVE_ORCHESTRATION_ROADMAP.md).

### Experiment
- **`output_audit.py`**: new `INTENT_SYSTEM` prompt + `audit_output(check_intent=True)` returns
  `satisfies_intent` + `missing_constraints` (role/attribute match: a different-but-similar role — Council-
  President vs Rector — fails; incomplete enumeration fails). Fail-OPEN (defaults True). `check_intent=False`
  keeps the groundedness path byte-identical.
- **`query_engineering.is_identity_query`**: gates the intent check to person/role-identity + role-enumeration
  ("who is X / X là ai / who are the presidents / hiệu trưởng … nào"); EXCLUDES policy "who is eligible/
  responsible/…" to avoid over-firing.
- **`vinuni_agent.py`**: widened the audit gate — `run_intent = enable_intent_audit AND is_identity_query`;
  degrade (hedge via `build_graceful_degradation_response`) when `not grounded OR (run_intent AND not
  satisfies_intent)`. Flag **`ENABLE_INTENT_AUDIT`** (default off), `OUTPUT_AUDIT_MODEL` reused (tested with
  gpt-4o-mini for role reasoning). **16 `test_output_audit` cases green, ruff clean.**

**Live probe (v2, flag on, gpt-4o-mini judge):** "VinUni có những hiệu trưởng nào?" + "Who have served as
Presidents?" → **HEDGE** (was confidently-wrong). "Tan Yap Peng/Yap-Peng Tan/Rohit Verma là ai?" → still
**ANSWER** (satisfies_intent=true, not over-degraded). "Who is eligible for the scholarship?" control → served,
auditor **skipped** (not an identity query → no over-fire).

**A/B (isolated 7-case `identity_intent.json`, v2):**
| | overall | flips |
|---|---|---|
| flag **OFF** | **0.714** (5/7) | `d9-rectors-enumerate-en/vi` FAIL (confidently answer, not hedge) |
| flag **ON** | **1.0** (7/7) | both enumeration cases PASS (hedge); 5 identity/control cases PASS in BOTH (no over-degradation) |

### Progress
- **D9 DONE + validated on the identity set (+2, zero regressions there).** Flag **default-off**; the full
  `--runs 3` A/B over all 188+ cases (over-fire check across the whole set) is the **promote gate for the
  flag**, deferred to the promote step. New golden `data/eval/golden/identity_intent.json` (7 cases).
- **Boundary (unchanged):** D9 = safety/calibration (hedge instead of confidently-wrong). Affirmative
  enumeration ("Rohit Verma + Tan Yap Peng") still needs **content** (keep the leadership announcement) +
  **D8** (role/alias table) — then the enumeration golden flips from `expects_refusal` to
  `required_facts=[both names]`.
- **NOT promoted; no git commit.** Next per user sequence: citation-too-narrow + scholarship retrieval, then
  full eval + promote.

## 1.28e — Citation-too-narrow + scholarship fixes (#1) — expansion golden 7/8

### Trial + decode (probe on v2 with citations dumped)
The 3 "minor golden fails" from the first benchmark — most were **already resolved by the filter fix** (the
authoritative pages are now indexed so the bot cites them):
- **exp-program-datascience-en** → PASS: now cites `cecs.vinuni/undergraduate/data-science/` + the policy BSDS
  curriculum PDF (was dropped before).
- **exp-bba-duration-en** → PASS: now cites `cbm.vinuni/.../bachelor-of-business-administration` + the
  admissions BBA PDF.
- **exp-admissions-ielts-phd-cs-en** → PASS (always did).
- **exp-scholarship-phd-cs-en** → was a **golden-wording bug**, not retrieval: the answer correctly gives
  "100% tuition scholarship + annual allowance up to 240,000,000 VND" but the required word was "stipend"
  (the source says "allowance"). Fixed `required_facts` → `["full scholarship|100% tuition","allowance|stipend"]`
  + `expected_source` += `financial-support`. → PASS.

### Experiment (golden edits, no code change)
- `data/eval/golden/expansion.json`: scholarship wording fix; `expected_source` broadened with the now-citable
  authoritative slugs (`BSDS`, `khoa-hoc-du-lieu`); **exp-presidents-enumerate-en converted to
  `expects_refusal`** (D9-realistic — hedge until D8/leadership content; flip back to both-names then).
- **Targeted eval (expansion.json, v2, ENABLE_INTENT_AUDIT on, gpt-4o-mini judge):** **7/8 = 0.875.**
  PASS: ielts, datascience-en, scholarship, bba, provost, presidents-enumerate (hedge), name-order.
  **FAIL: exp-program-datascience-vi** — `facts_ok=True` ("4 năm", "120"; answer inline-cites the cecs VI DS
  page) but `cite_ok=False`.

### Decode of the one straggler (datascience-vi)
A **direct** `retriever.search` ranks the cecs VI Data-Science page TOP (rerank 0.943), but the **agent's**
collected `citations` were all `global_exchange` (recovered exchange pages) — `_extract_citations` unions
results across ALL ReAct tool calls and keeps the **first 8 by message order**, and the agent's cross-lingual
tool queries retrieved exchange pages, never the cecs chunk. So: user-facing answer is **correct** (right
facts + correct inline source); only the structured-citation scoring trips. Root cause = cross-lingual ReAct
query formulation + first-encountered (not highest-scored) citation selection. Candidate fix (deferred,
needs its own A/B): make `_extract_citations` keep the **highest-scored** citations, not first-encountered.
**Accepted as a documented known limitation** for now (facts correct; EN version passes).

### Progress
- **#1 DONE**: expansion golden 1→7/8; the remaining datascience-vi is a documented cross-lingual citation
  artifact (correct answer). Next: **#2** more golden on new content → **#3** full `--runs 3` A/B → **#4** promote.

## 1.28f — Golden on recovered content (#2) + new-golden validation

### Experiment
New `data/eval/golden/recovered_content.json` (4 cases) — regression guards for the content the filter
RECOVERED, using structural facts (not fiddly curriculum credit numbers, which are table-formatted and
hard to verify from source): **registrar form PDF** (leave-of-absence/defer-withdraw → FRM07), **student
guide/handbook PDF**, **/global_exchange/ section** (Cornell founding partner), EN + one VI. (Probed candidate
MD/nursing credit cases but did NOT author them — couldn't verify the exact numbers against the table-based
source; the dean-CECS identity case was role-ambiguous → skipped.)

**Validation — all 3 new golden files (expansion 8 + identity_intent 7 + recovered 4 = 19), v2, D9 on
(gpt-4o-mini judge):** **18/19.** The 1 fail = `d9-rectors-enumerate-vi` (`refus=False` — answered instead of
hedging). The EN enumeration hedged; the VI didn't *this run* → the D9 auditor's verdict on the VI enumeration
is **probabilistic** (hedged in the earlier probe, not here). Known-noisy; the `--runs 3` gate de-noises it.
Recovered-content cases (rc-*) + scholarship + identity individual all PASS.

### Progress
- **#2 DONE** (19 new golden across 3 files; 18/19, 1 noisy). Next **#3**: full A/B (`--runs 1` smoke for
  regression + D9-over-fire, then `--runs 3` gate) vs baseline 0.968/188 → **#4** promote.

## 1.28g — Full A/B (#3) + PROMOTE (#4)

### Experiment — full `--runs 1`, v2 + D9 on (gpt-4o-mini judge), `--diff baseline 0.968/188`
**Overall 0.962** (~207 cases incl. legacy calendar). **Guards 1.000** (adversarial/safety/unanswerable).
**No D9 over-fire** — `identity_intent` 7/7, and none of the existing 188 was degraded by the auditor. New
content all pass: `expansion` 1.0, `identity_intent` 1.0, `recovered_content` 1.0. Most categories flat.

**Decode of the dip (8 fails):** **6 were ALREADY failing in baseline** (pre-existing hard cases:
`pol-courseeval-vi`, `pol-thesis-days-vi`, `ltp-recordprivacy-access-vi` [input-guard over-refusal, roadmap
D6], `calendar-source-inconsistency-en/vi`, `calendar-vietnam-culture-day-vi`). Only **2 REAL flips**, both
**correct answers vs stale golden** (the `--diff` LOST detector missed them — baseline-format quirk; confirmed
by direct id lookup):
- `svc-library-services`: answer correct (research-support services) but cited the official
  `policy.vinuni/all-policies/library-policies-for-users` page, while `expected_source` required
  `library.vinuni.edu.vn` — which was **excluded from crawl (login-walled)**, so that expectation is stale.
- `pol-loa-fulltime-vi`: answer correct (applies to full-time students) but said "chính thức/full-time"
  not the exact required VI token "toàn thời gian".

### #4 — PROMOTE (user decision: broaden the 2 stale golden + promote on --runs 1)
- **Golden broadened (legit)**: `svc-library-services` expected_source += `library-policies`;
  `pol-loa-fulltime-vi` required_facts → `toàn thời gian|chính thức|full-time`.
- **`.env` flipped**: `QDRANT_COLLECTION=vinuni_full_e5_v2` (prev `vinuni_full_e5` kept as rollback);
  **`ENABLE_INTENT_AUDIT=true`** + `OUTPUT_AUDIT_MODEL=openai/gpt-4o-mini` (D9 enabled). `.env.example` updated.
- **Baseline refresh**: fresh full `--runs 1` on the promoted config → `data/eval/baseline.json` (see result
  below). 372 tests green, ruff clean. No git commit (per standing instruction).

### Progress
- **PROMOTED**: production now serves the filter-fixed v2 corpus + D9 intent auditor. Rollback = flip `.env`
  back to `vinuni_full_e5` + `ENABLE_INTENT_AUDIT=false`.
- Open follow-ups (logged, not blocking): cross-lingual citation precision (datascience-vi / score-sorted
  citations candidate); affirmative president enumeration (needs leadership-announcement content + D8 role
  table); the probabilistic VI-enumeration hedge (D9 auditor variance).

## 1.28h — Citation precision (score-sorted citations) — A/B REJECTED, reverted

### Trial
`_extract_citations` unions results across every ReAct tool call in **message order** and keeps the first 8;
on multi-call turns a low-relevance chunk from an early/off-target sub-query can crowd out the on-target one
(the recovered-content citation dilution; datascience-vi cited only `global_exchange`). Hypothesis: keep the
**highest-scored** 8 instead.

### Experiment
- **`_extract_citations`**: stable `citations.sort(key=score desc, None last)` before `dedupe[:8]`. +2 unit
  tests; 374 green; ruff clean. Baseline `data/eval/baseline.json` refreshed first on v2+D9 (no fix) = 0.957.
- **A/B (full `--runs 1 --diff baseline`, v2+D9):** **0.957 → 0.948.**
  - **GAINED (+1):** `exp-program-datascience-vi` (cite_ok) — the cecs chunk WAS collected but low-ranked;
    score-sort surfaced it. `expansion` 0.875→1.0.
  - **LOST (−5):** `pol-acadint-report-vi`, `pol-exchange-credits-vi`, `pol-finaid-deadline-vi`,
    `pol-loa-return-vi`, `pol-res-curfew-vi` — `policy` **0.941→0.794**. All VI policy, same category, coherent
    → a real cite_ok regression: for cross-lingual policy queries the score-sort pushed the expected VI policy
    source out of the top-8 in favor of higher-scored EN/other chunks. (calendar_pointlookup 0.9→0.967 = the
    known noise bouncing back, not the fix.)

### Progress
- **REJECTED** (net −4 on cite_ok: trades 5 correct VI-policy citations for 1 datascience). Reverted
  `_extract_citations` to first-encountered order (note left in code); removed `test_citation_ranking.py`;
  **372 green**, ruff clean. `baseline.json` (no-fix) is unchanged and matches the reverted code. No git commit.
- **Lesson:** rerank scores are **query-specific** and **not comparable across a multi-call ReAct turn's
  sub-queries**, so global score-sorting mis-ranks cross-lingual citations. A correct fix would need
  per-tool-call normalization or to cite the sources the *answer* actually used — deferred. The cross-lingual
  citation dilution (datascience-vi) stays a documented open item.
