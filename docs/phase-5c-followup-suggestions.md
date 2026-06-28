# Phase 5C: backend-generated follow-up question suggestions

The chips under each answer ("gợi ý câu hỏi tiếp theo") were **frontend-only, rule-based** and felt
irrelevant: 4 coarse regexes (`person`/`tuition`/`schedule`/`policy`) emitting **canned templates** plus a
generic fallback, with no understanding of the actual answer. Worst offender: personal (Vinnie) answers have
**0 citations by design**, which the rules flagged as "weak" → every GPA/schedule answer led with "Which
office should I contact? / Prepare a support ticket".

## What changed
A **dedicated small/fast LLM call** now derives the next questions from THIS turn's question + answer, the
same pattern as the Part-B ticket suggester. The frontend was already "Phase-2-swappable" (it prefers
backend-provided suggestions), so the wiring was a content swap, not a UI rewrite.

- **`vinchatbot/app/agents/followup_suggest.py`** (NEW) — `suggest_follow_ups(question, answer, settings)`:
  small-model call → JSON array of short questions. Prompt: at most **3**, each **short** (a brief question),
  **content-derived** (reference the specific topic/course/person/office discussed), only things Vinnie can
  answer, no repeat of the original, no invented facts; **same language** as the question (VI note enforces a
  short, natural student register). Tolerant parse; `_clean` drops the original question, duplicates, and
  over-long (>90 char) entries, capped at 3. **Fail-open**: no key / disabled flag / blank inputs / error /
  unparsable → `[]`.
- **`vinchatbot/app/agents/vinuni_agent.py`** — on the SUCCESSFUL answer path only (after all output guards),
  calls `suggest_follow_ups` best-effort under `asyncio.wait_for(timeout=8.0)`; any failure is swallowed and
  yields `[]`. Not run on refused/degraded/conversational turns.
- **`vinchatbot/app/schemas/chat.py`** — `ChatResponse.suggested_follow_ups: list[str] = []`. Flows through
  both `/chat` and the `/stream` `done` event automatically; persisted in `answer_json`.
- **`vinchatbot/app/core/config.py`** — `followup_suggest_model` (default `google/gemini-2.5-flash`, alias
  `FOLLOWUP_SUGGEST_MODEL`) + `enable_followup_suggestions` (default `true`, alias
  `ENABLE_FOLLOWUP_SUGGESTIONS`). `.env.example` documents both (and `TICKET_SUGGEST_MODEL`).

## Frontend
- `lib/types.ts` — `suggested_follow_ups?: string[]` on `ChatResponse`.
- `lib/followUps.ts` — `followUpsFor` already prefers backend suggestions; reduced the cap from 5 to a shared
  `MAX_FOLLOW_UPS = 3` (the questions can be long), applied to both the backend and rule-based paths.
- `lib/chat.tsx` — `chatResponseFromStoredMessage` restores `suggested_follow_ups` from `answer_json` so the
  chips survive a conversation reload. The rule-based set remains as the fail-open fallback (unchanged).

## Model
`google/gemini-2.5-flash` via OpenRouter (a fast/cheap "flash" tier). Swap with `FOLLOWUP_SUGGEST_MODEL`;
disable the backend chips entirely with `ENABLE_FOLLOWUP_SUGGESTIONS=false`. (Live-validated on OpenRouter.)

## Verification
- **Tests**: `tests/test_followup_suggest.py` (no key / disabled / blank → empty; valid JSON capped to 3;
  drops original+dup+over-long; non-list / unparsable / model-error → empty) + 3 wiring tests in
  `tests/test_chat_personalization.py` (attaches on success; flag gates off; failure never breaks the turn).
  **Full suite 695 passed**, ruff clean.
- **Live** (`google/gemini-2.5-flash`, as `student.cs.demo`): GPA → "Làm sao để cải thiện GPA? / GPA bao
  nhiêu thì được học bổng? / Tôi có bị cảnh báo học vụ không?"; next-class → homework / contact-instructor /
  "Phòng A101 ở đâu?"; tuition → room&board / scholarship / future-year changes; an English question returned
  **English** suggestions. All ≤ ~45 chars, exactly 3.
- **Frontend typecheck NOT run here** (no Node on this machine) — run `cd frontend && npm run typecheck`.
