# Phase 11C: Notification-Driven Vinnie Suggestions

Phase 11C makes `GET /suggestions/me` contextual for the authenticated student.
The endpoint remains FastAPI-backed; the frontend never reads Neon/Postgres
directly.

## Data Sources

- Active student-visible notifications from the admin notification workflow.
- Upcoming student deadlines.
- Upcoming student schedule items.
- Existing active rows from `suggested_questions`.
- Safe generic fallback prompts when the student has too little contextual data.

## Ranking

Suggestions are deterministic and rule-based:

- urgent/high notifications rank first;
- upcoming deadlines rank next, with near deadlines boosted;
- schedule/event prompts follow;
- seeded/trending suggestions are preserved;
- duplicate question text is collapsed;
- the final response is limited to eight suggestions.

Hidden notifications do not influence suggestions. Draft, archived, expired, and
future scheduled notifications are ignored, and institute/course/cohort targeting
is respected by the same student visibility rules used by notifications.

## Frontend Integration

The chat page, floating Vinnie widget, and student dashboard use backend-backed
suggestions through `GET /suggestions/me`. If the endpoint is loading, empty, or
fails, the UI falls back to existing safe local prompts and keeps the current
click-to-send behavior.

## Limitations

This phase does not call an LLM and does not expand RAG or agent behavior. The
question text is generated from stable templates for demo predictability. Admins
do not need to manually author suggested questions for notifications, though
seeded `suggested_questions` still participate when present.
