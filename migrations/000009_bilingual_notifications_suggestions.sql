-- Bilingual notification + suggested-question content (VI/EN).
--
-- The student UI language toggle (default Vietnamese) must drive the language of the
-- notifications and suggested questions a student sees. We keep the original
-- single-language title/message/question_text columns as the canonical fallback and add
-- optional per-language variants. Student reads resolve coalesce(<col>_<lang>, <col>),
-- so any row that has not been translated still renders its base text in either language.
--
-- Additive and idempotent.

alter table notifications
    add column if not exists title_vi text,
    add column if not exists title_en text,
    add column if not exists message_vi text,
    add column if not exists message_en text;

alter table suggested_questions
    add column if not exists question_text_vi text,
    add column if not exists question_text_en text;
