# Phase 5I: Personal schedule ("tiết") fixes — refusals, whole-day reporting, "hôm qua"

Students asking about their timetable in natural Vietnamese hit three separate failures. Live testing
(against `quynh.thanh.huynh028@vinuni.edu.vn`, today = BUS220 08:30 / DAT101 10:30 / VIE101 13:30, with the
tool instrumented to log the LLM's args) isolated **three independent layers** — the schedule tool's
range/data logic was already correct; the failures were around it.

## Diagnosis (tested before fixing)
1. **Classification → refusals.** `classify_question_scope` didn't recognize "hôm nay có **tiết gì**", "**có
   tiết không**", "**đang học tiết** gì", "**đã học gì**", "chiều nay **có tiết** không" → `general_unknown` →
   not routed to the personal specialist → Vinnie refused. (The homograph "tiết" — chi tiết / thời tiết / tiết
   kiệm / tiết lộ — meant bare "tiet" couldn't just be added.)
2. **Generation → under-reporting.** With "**còn** tiết nào" the LLM read "còn"=remaining and dropped
   already-finished classes even though `get_my_schedule(window="today")` returned the full day (at 11:00 it
   listed only DAT101 + VIE101, omitting BUS220 08:30). The tool gave the model no per-meeting status to reason
   with.
3. **Tool footgun → "hôm qua" returned today.** No `"yesterday"` window existed and an unknown window
   **silently defaulted to "today"**, so an LLM guess of `window="yesterday"` silently returned today's classes.

Verified NOT broken: `window="today"` always returns the whole day; `current_class`/`next_class` correct;
`from_date/to_date` works.

## Fix
- **Tool** (`vinchatbot/app/agents/personal_tools.py`): added the **`"yesterday"`** window; added a per-meeting
  **`status`** (`finished`/`ongoing`/`upcoming`, from `now` vs start/end) via new helpers `_classify_status` /
  `_listed_meetings` / `_status_counts`; added a **`counts`** summary (total/finished/ongoing/upcoming) to the
  response. Applied to both the academic and student-schedule-API paths.
- **Scope** (`vinchatbot/app/agents/question_scope.py`): added a **homograph-safe** `_SCHEDULE_TIET_RE`
  (`tiết gì/nào/không/tiếp theo/mấy/nay/sáng/chiều/tối` + `còn/mấy/hết tiết`, excluding chi tiết/thời tiết/tiết
  kiệm/tiết lộ/tiết mục — "hoc" deliberately omitted since "tiet hoc" is already a term) folded into
  `has_generic_app_data`, plus a **pronoun-gated** `_SELF_STUDY_RE` (`đã/đang học`) for "sáng nay tôi đã học gì".
- **Prompt** (`vinchatbot/app/agents/prompts.py`, `PERSONAL_PROMPT`): "hôm nay có tiết gì / còn tiết nào / đã
  học gì" → `window="today"`, list the WHOLE day labelled by `status` (đã học/đang học/sắp tới), never drop
  finished classes; use `counts` for "còn tiết"; distinguish "không CÒN tiết (đã học hết)" from "không CÓ tiết
  (ngày trống)"; "hôm qua" → `window="yesterday"`.

## Verification
- **Over-fire audit (deterministic):** `tests/test_question_scope.py` — new `test_tiet_homographs_do_not_
  overfire` (chi tiết học phí, thời tiết, tiết kiệm, "trường có tiết lộ thông tin của tôi", tiết mục, "sinh
  viên đang học gì") all stay non-personal at `authenticated=True`; recall phrasings added to the personal +
  authenticated-elliptical params.
- **Tool unit** (`tests/test_personal_tools.py`): `test_schedule_today_tags_status_and_counts` (11:00 →
  finished/ongoing/upcoming + counts), `test_schedule_yesterday_window_resolves_prior_day`.
- **E2E** (instrumented agent, quynh student): 11:00 "hôm nay có tiết gì" → all 3 with Đã học/Đang học/Sắp
  tới; "nay tôi còn tiết nào" → full day via counts (BUS220 not dropped); "hôm qua tôi có môn gì" →
  `window="yesterday"` → yesterday's classes; 23:30 "còn tiết nào" → "đã hoàn thành tất cả" (not "no classes").
- **Golden**: added `pers-today-tiet-gi`, `pers-yesterday-classes` (+ existing pers-today-tiet/pers-next-tiet).
- **777 backend tests pass**, ruff clean.

Branch `fix/schedule-tiet` off `main`.
