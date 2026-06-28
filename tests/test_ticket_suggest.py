from __future__ import annotations

import asyncio
from types import SimpleNamespace

from vinchatbot.app.agents import ticket_suggest as ts
from vinchatbot.app.schemas.tickets import SuggestTicketRequest


class _FakeModel:
    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages):
        return SimpleNamespace(content=self._content)


def _settings(key: str | None = "x"):
    return SimpleNamespace(openrouter_api_key=key, ticket_suggest_model="small/fast-model")


def _run(awaitable):
    return asyncio.run(awaitable)


def test_heuristic_fallback_when_no_api_key():
    # No LLM available → deterministic heuristic so the ticket flow never breaks.
    req = SuggestTicketRequest(origin_question="Tôi không đăng nhập được Canvas", answer="Hãy thử reset mật khẩu.")
    draft = _run(ts.suggest_ticket_draft(req, settings=_settings(key=None)))
    assert "Canvas" in draft.subject
    assert draft.body  # populated from the answer/question
    assert draft.category == "other"


def test_valid_llm_json_is_used(monkeypatch):
    monkeypatch.setattr(
        ts,
        "build_chat_model",
        lambda *a, **k: _FakeModel(
            '{"subject": "Cannot log into Canvas", "body": "I am unable to log into Canvas since '
            'yesterday and need help resetting access.", "category": "technical"}'
        ),
    )
    req = SuggestTicketRequest(origin_question="I cannot log into Canvas", answer="Try resetting your password.")
    draft = _run(ts.suggest_ticket_draft(req, settings=_settings()))
    assert draft.subject == "Cannot log into Canvas"
    assert "Canvas" in draft.body
    assert draft.category == "technical"


def test_invalid_category_is_normalized_to_other(monkeypatch):
    monkeypatch.setattr(
        ts,
        "build_chat_model",
        lambda *a, **k: _FakeModel('{"subject": "X", "body": "Y problem", "category": "billing"}'),
    )
    req = SuggestTicketRequest(origin_question="some issue")
    draft = _run(ts.suggest_ticket_draft(req, settings=_settings()))
    assert draft.category == "other"  # "billing" is not an allowed category


def test_unparseable_output_falls_back_to_heuristic(monkeypatch):
    monkeypatch.setattr(ts, "build_chat_model", lambda *a, **k: _FakeModel("I cannot do that."))
    req = SuggestTicketRequest(origin_question="Help with my schedule", answer="Here is your schedule.")
    draft = _run(ts.suggest_ticket_draft(req, settings=_settings()))
    assert draft.subject == "Help with my schedule"
    assert draft.category == "other"


def test_model_error_falls_back_to_heuristic(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("openrouter down")

    monkeypatch.setattr(ts, "build_chat_model", _boom)
    req = SuggestTicketRequest(origin_question="Need help", answer="ans")
    draft = _run(ts.suggest_ticket_draft(req, settings=_settings()))
    assert draft.subject == "Need help"
    assert draft.category == "other"


def test_fields_are_clamped_to_schema_limits(monkeypatch):
    long_subject = "S" * 500
    long_body = "B" * 9000
    monkeypatch.setattr(
        ts,
        "build_chat_model",
        lambda *a, **k: _FakeModel(
            '{"subject": "' + long_subject + '", "body": "' + long_body + '", "category": "academic"}'
        ),
    )
    req = SuggestTicketRequest(origin_question="q")
    draft = _run(ts.suggest_ticket_draft(req, settings=_settings()))
    assert len(draft.subject) <= 200
    assert len(draft.body) <= 5000
    assert draft.category == "academic"
