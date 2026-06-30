# Phase 5G — New DB migration: verify, fix, re-pin golden

**Trial.** Point the app at the teammate's NEW Neon DB (`ep-delicate-mouse-ao5acwf4`), check everything,
fix anything broken, and re-pin the golden set to the new data. (`.env` updated locally — gitignored, creds
not committed.)

## New DB — what's there (37 tables, much richer seed)
112 users / 105 student_profiles / 1912 enrollments / 1947 class_meetings / **9855 student_schedule_events**
/ 200 deadlines / 52 tickets. Students are now realistic VN names with codes like `VU25CECS005`, `VU24VIB025`
(plus the demo `student.cs.demo` kept, code now **D13CECS001**).

**Tables our tools don't use yet (potential agent upgrades — see backlog):**
`student_schedule_events` (per-student denormalized timetable: student_id + start_at/end_at + room/building/
instructor — a cleaner schedule source), `suggested_questions` (admin-approved, `question_text_vi/en`,
`created_by_ai` — could feed follow-ups/starter chips), `question_trends` + `student_question_events`
(what students ask — trending/analytics), `notification_reads` (per-user read/important/archived),
`forum_votes`/`forum_mentions`/`forum_reports`, `audit_logs`.

## Fixed before committing
- **`get_my_profile` was BROKEN on the new schema**: `students.get_current_student_profile` `left join`ed
  `academic_summaries`, which the new DB dropped → `UndefinedTable` → the whole tool errored (no
  profile/advisor/student-id/cohort). Fix: the query now falls back to a no-`academic_summaries` variant
  (GPA/credits come from the academic read-model anyway), and `_student_profile_from_row` reads the summary
  columns with `.get()`. Backward-compatible with schemas that still have the table.
- **PII student-code regex** only matched `D\d{4}…`; the new codes are `D13CECS001` / `VU25CECS005`. Widened
  to `\b(?:VU|D)\d{2,4}[A-Z]{2,6}\d{3}\b` (still never scrubs course codes like CS102). Test added for all
  shapes.

## Golden re-pin (only identity facts changed; academics identical)
`student.cs.demo` on the new DB has the SAME academic data (GPA 3.0/CPA 3.12, 5/115 credits, CS102
failed+retake, CS101 B, courses CS102/CS201/GEN102/MATH102, aim 3.6→3.621 / 3.3→3.308). Changed: student
code `D2026CECS001`→**`D13CECS001`**, advisor `Minh Nguyen`→**`Demo CS Advisor`**, cohort `2026`→**`2025`**.
Updated `golden_personal.json` (3 facts + description).

## Verification
- `ruff` clean; **full suite 726 passed** (+ student-code-shapes scrub test).
- **Live personal eval on the NEW DB: 42/42, route_ok 42/42, facts 19/19** — incl. `get_my_profile` now
  resolving (code/advisor/cohort), schedule/standing/eligibility, and the over-fire negatives.
- RAG path unaffected (Qdrant unchanged; `pers-separation-general-fee` still cites tuition 815,850,000).

## Deferred (logged here + in the plan backlog)
- **Noisy / human-like VN input eval (teencode, typos, abbreviations):** build a golden set of how a real
  Vietnamese student actually types — teencode/abbreviations ("baoh thì thi ck" = "bao giờ thì thi cuối kỳ?",
  "đki môn" = "đăng ký môn", "hp" = "học phí", "ko/k" = "không", "đc" = "được", "j" = "gì"), missing
  diacritics ("bao gio thi cuoi ky"), and casual phrasing; measure the agent's robustness and decide whether
  a normalization/expansion step is warranted. **Defer** (generate + measure first).
- **Use new tables to upgrade the agent** (defer, measure ROI first): `student_schedule_events` as the schedule
  source; `suggested_questions` (vi/en) for follow-ups/starters; `question_trends` for trending prompts.
