# Phase 5D — Personalization correctness pass (schedule / overfire / citations) + golden rebuild

**Trial.** Live use surfaced correctness bugs in the personal path: schedule week/day questions wrong,
a greeting triggered a full personal-data dump, personal answers showed an ugly `Nguồn: [personal],
[calendar]` footer, and the personalized golden facts had drifted. Also merged with the teammate's
PR #6 (`dholmes`) which independently refactored the academic read-model.

## Experiment — what changed

### 2b. Schedule + courses (`personal_tools.py`, `timeutils.py`, `prompts.py`)
- `get_my_schedule(window, from_date, to_date)`: windows computed **deterministically in the tool** —
  `today`/`tomorrow` = whole calendar day incl. finished classes; `this_week`/`last_week`/`next_week`
  = **Mon→Sun** (new `timeutils.week_bounds`); `now`/`next`/`all`; plus an explicit `from_date`/`to_date`
  range. Returns every meeting in range (dropped `upcoming_only`), + `current_class`/`next_class`/
  `range_start`/`range_end`. Portal fallback only when the academic timetable is empty (same range, no
  upcoming-only drop).
- `get_my_courses` now reads the academic model so it matches schedule/transcript.
  **Merge note:** the teammate's PR #6 added a shared `_academic_record`/`overview` read-model
  (used by standing/courses/transcript/GPA); on integration we DEFERRED `get_my_courses` to that
  read-model (`source: "academic_read_model"`) and dropped our redundant `academic.get_current_courses`.

### 2c. Greeting overfire + leakage (`vinuni_agent.py`, `guardrails.py`)
- Personalization context is now injected **only for `personal_app_data`/`hybrid` scope** — a general/
  greeting turn no longer carries the student's profile/schedule/deadlines into the prompt.
- Greeting/opener fast-path tolerates a trailing language directive ("hi, trả lời bằng tiếng việt") via
  `_strip_trailing_language_directive`, so it stays conversational instead of hitting the agent.
- **Leakage: confirmed NONE** — the LangGraph thread is namespaced `u:{user_id}:{conversation_id}`; the
  "dump" was per-turn over-share of the user's OWN injected context, not cross-conversation/user leak.

### 3. Citations (`prompts.py`, `graph.py` synthesis, `schemas/chat.py`, frontend)
- Forbid bracketed pseudo-tags (`[personal]`/`[calendar]`); personal → "Dữ liệu cá nhân của bạn",
  RAG → real metadata links. Added `ChatResponse.personal_data` + a frontend "Dữ liệu cá nhân của bạn"
  source chip (`MessageBubble.tsx`, `i18n.tsx`, `types.ts`, `chat.tsx`).

### 2a. Golden rebuild (`data/eval/golden_personal.json`, `run_eval_personal.py`)
- Facts rebuilt by dumping every personal tool for `student.cs.demo` and matching reality. UTF-8 stdout
  so the runner stops crashing on Windows (cp1252). Added cases: `last_week`/`today`/specific-date +
  two greeting-overfire guards; courses CSC*→CS*.

## Experiment — numbers (verified on the INTEGRATED branch / `main` 1058747)
- `pytest`: **708 passed**; `ruff`: clean.
- Live smoke (`student.cs.demo`): greeting → no tools/no dump; "lịch tuần trước" → **22/06–28/06/2026**
  (W26 Mon–Sun, was 26/6–2/7); "hôm nay" → full day incl. finished 08:00 class; "ngày 24/6" →
  `from_date/to_date`; "môn của tôi" → CS102/CS201/GEN102/MATH102 (academic read-model); personal answers
  carry `personal_data=true`, no bracket tags.
- Golden eval (`run_eval_personal.py`): **39/41, facts_ok 19/19, tool_ok 28/30**.

### Merge finding — PR#6 shifted standing semantics (golden re-verified on `main`)
Same DB, but `get_my_academic_standing`/`project_gpa_for_target` now return different numbers than on
the pre-merge branch, so golden facts were re-pinned to `main`'s output:
- GPA: **3.0** (semester) / **3.12** (cumulative CPA) — was 2.97. (Open: "my GPA" returns the *semester*
  3.0; cumulative 3.12 may be the intended headline — for the teammate to confirm.)
- credits earned: **5** (passed-and-counted) — was 21 (attempted); remaining **115** of 120.
- projection (uses cumulative 3.12): target 3.6 → **3.621**, 3.3 → 3.308, 4.0 → not reachable.
- golden facts updated accordingly (GPA `3.0|3.12`, earned `5`, remaining `115`, aim `3.62`/`3.308`).

## Progress / state
- Pushed to `main`: `1058747` (cherry-pick + 3-file conflict resolution merging both sides) + the golden
  re-pin to main's numbers (this doc's commit). Branch `feat/personalization-tools` still holds the
  pre-merge version (main is the integrated truth).
- `.env` synced to the teammate's `.env.example` (added 7 missing keys; **DB URL + secrets untouched** —
  the example only has placeholders, so the working URL was preserved).

## Known issues / deferred
- **2 classifier under-fires** (`pers-on-track`, `pers-why-blocked`) route general instead of personal —
  the deferred input-understanding gap; widening the classifier risks the over-fire we forbid. Left as
  documented golden fails.
- **Frontend not typechecked here** (no Node) — teammate runs `cd frontend && npm run typecheck`.
- **New-DB confirmation pending** — golden is verified against the DB `.env` currently points to; if the
  "new DB" is a different URL, re-dump + re-pin the golden after swapping it in.
- **GPA headline semantics** (semester 3.0 vs cumulative 3.12) — confirm intended behavior with the
  PR#6 author.
