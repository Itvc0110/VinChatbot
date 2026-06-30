# Phase 5F — Personalization polish (deferred-backlog Track B)

**Trial.** Fix the two classifier under-fires (#5a "am I on track to graduate?", #5b "why am I blocked
from CS301?"), settle the GPA headline (semester vs cumulative), and the schedule now/next fallback shape —
all under the standing rule: **precision > recall, strictly NO over-fire**.

## B1 — classifier under-fires (overfire-safe, audited)
First attempt added progress/eligibility terms to `_GENERIC_APP_DATA`. The offline audit + a hand battery
showed that path **over-fires**: the authenticated-ellipsis rule (`generic + authenticated → personal`) makes
ANY such term fire for a logged-in student's GENERAL question too — e.g. "Học bổng Vingroup dành cho ai đủ
điều kiện?" / "do most students graduate on time?" → hybrid. Rejected.

**Final design (precise):** a new `_PERSONAL_PROGRESS` list (`on track`, `graduate on time`, `tốt nghiệp
đúng hạn`, `eligible`/`đủ điều kiện`, `prerequisite(s)`/`tiên quyết`, `blocked`/`bị chặn`, `ra trường`) that
counts as personal **only with an EXPLICIT first-person pronoun** — NOT via authenticated-ellipsis. So
"**Am I** on track to graduate?" / "**Tôi** có đủ điều kiện học CS301?" route personal, while "**who** is
eligible…?" / "**do most students** graduate on time?" stay general. `register`/`đăng ký` deliberately
excluded (would catch "how do I register for courses?").

**Audit (offline, deterministic — `classify_question_scope` has no LLM):** 236 general/adversarial golden
questions classified with `authenticated=True` (worst case) → **0 new over-fires**; a realistic
general-eligibility battery (scholarship/graduation "who qualifies") all stay general/policy. Unit tests added
in `test_question_scope.py` (first-person → personal; general phrasings → not personal). Note: the bare
"**why can't I register** for CS301" phrasing remains a documented under-fire gap (catching it needs
`register`, which over-fires) — the eligibility phrasing is the supported path.

## B2 — GPA headline → cumulative
PR#6's `get_my_academic_standing` returns BOTH semester GPA (3.0) and cumulative CPA (3.12); "what is my GPA"
was answering the semester value. `PERSONAL_PROMPT` now says: for a plain "GPA của tôi / my GPA" use the
**cumulative CPA** as the headline; report the semester GPA only when asked "this semester". Golden gpa fact
uses the `3.0|3.12` alternation so it passes either way.

## B3 — schedule now/next fallback (shape parity)
`get_my_schedule(window="now"/"next")` now also falls back to the portal schedule (computing current/next)
when the academic timetable is empty — matching the day/week branch. The **fan-out citation over-inclusion**
filter was left in the backlog: faithfully filtering to citations actually used by the synthesis needs
claim-tracing, and a naive filter risks dropping real sources — not worth the precision risk now.

## Progress — verification
- `ruff` clean; **full suite 725 passed** (+ classifier first-person/general tests).
- Offline over-fire audit: **0 new over-fires** on 236 general/adversarial questions.
- Live personal eval (`run_eval_personal.py`): **42/42, route_ok 42/42, facts 19/19** — `pers-on-track` and
  `pers-why-blocked` (eligibility phrasing) now PASS; new negative `pers-neg-eligible-general` confirms the
  general-eligibility question stays on the RAG path (no over-fire).
- Backlog unchanged (data-model, forms, output-guard A/B, RAG correctness, infra, frontend, D-roadmap,
  fan-out citation filter).
