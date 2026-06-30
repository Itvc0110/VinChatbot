from __future__ import annotations

import asyncio
from types import SimpleNamespace

from vinchatbot.app.agents import followup_suggest as fs


class _FakeModel:
    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages):
        return SimpleNamespace(content=self._content)


def _settings(key: str | None = "x", enabled: bool = True):
    return SimpleNamespace(
        enable_followup_suggestions=enabled,
        openrouter_api_key=key,
        followup_suggest_model="small/fast-model",
    )


def _run(awaitable):
    return asyncio.run(awaitable)


def test_no_api_key_returns_empty():
    # No LLM available → empty so the client falls back to its rule-based chips.
    out = _run(fs.suggest_follow_ups("What is my GPA?", "Your GPA is 3.4.", settings=_settings(key=None)))
    assert out == []


def test_disabled_flag_returns_empty(monkeypatch):
    monkeypatch.setattr(fs, "build_chat_model", lambda *a, **k: _FakeModel('["x?"]'))
    out = _run(fs.suggest_follow_ups("q", "a", settings=_settings(enabled=False)))
    assert out == []


def test_blank_inputs_return_empty():
    assert _run(fs.suggest_follow_ups("", "answer", settings=_settings())) == []
    assert _run(fs.suggest_follow_ups("question", "   ", settings=_settings())) == []


def test_valid_json_array_is_used_and_capped(monkeypatch):
    monkeypatch.setattr(
        fs,
        "build_chat_model",
        lambda *a, **k: _FakeModel(
            '["When is the retake exam?", "Who teaches CS102?", "Where is room A101?", "Extra one?"]'
        ),
    )
    out = _run(fs.suggest_follow_ups("Tell me about CS102", "CS102 is taught by Dr. X.", settings=_settings()))
    assert out == ["When is the retake exam?", "Who teaches CS102?", "Where is room A101?"]  # capped to 3


def test_drops_original_question_duplicates_and_overlong(monkeypatch):
    long_q = "Q" * 200
    monkeypatch.setattr(
        fs,
        "build_chat_model",
        lambda *a, **k: _FakeModel(
            '["What is my GPA?", "What is my GPA?", "' + long_q + '", "How do I improve it?"]'
        ),
    )
    out = _run(fs.suggest_follow_ups("What is my GPA?", "Your GPA is 3.4.", settings=_settings()))
    assert out == ["How do I improve it?"]  # original + dup dropped, over-long dropped


def test_non_list_json_returns_empty(monkeypatch):
    monkeypatch.setattr(fs, "build_chat_model", lambda *a, **k: _FakeModel('{"a": "b"}'))
    assert _run(fs.suggest_follow_ups("q", "a", settings=_settings())) == []


def test_unparseable_output_returns_empty(monkeypatch):
    monkeypatch.setattr(fs, "build_chat_model", lambda *a, **k: _FakeModel("I cannot do that."))
    assert _run(fs.suggest_follow_ups("q", "a", settings=_settings())) == []


def test_model_error_returns_empty(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("openrouter down")

    monkeypatch.setattr(fs, "build_chat_model", _boom)
    assert _run(fs.suggest_follow_ups("q", "a", settings=_settings())) == []
