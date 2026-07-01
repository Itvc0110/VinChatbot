from __future__ import annotations

import asyncio

import vinchatbot.app.agents.form_suggest as form_suggest
from vinchatbot.app.agents.form_suggest import suggest_form_fill
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.schemas.forms import FormField, SuggestFormRequest


def _request(**over) -> SuggestFormRequest:
    base = dict(
        official_url="https://registrar.vinuni.edu.vn/form.pdf",
        form_title="Đơn xin nghỉ học",
        origin_question="Tôi muốn xin nghỉ học một học kỳ vì lý do sức khỏe",
        answer=None,
        context=None,
    )
    base.update(over)
    return SuggestFormRequest(**base)


def _fields() -> list[FormField]:
    return [
        FormField(key="full_name", label="Họ và tên"),
        FormField(key="student_id", label="Mã số sinh viên"),
        FormField(key="ly_do", label="Lý do"),
        FormField(key="date", label="Ngày"),
    ]


_FACTS = {"full_name": "Nguyễn Văn A", "student_id": "D13CECS001", "email": "a@vinuni.edu.vn"}


def _run(**kw):
    return asyncio.run(suggest_form_fill(**kw))


def test_heuristic_fill_prefills_personal_and_reason_without_api_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "")
    result = _run(request=_request(), fields=_fields(), personal_facts=_FACTS, file_kind="pdf")
    values = {f.key: f.value for f in result.fields}
    assert values["full_name"] == "Nguyễn Văn A"
    assert values["student_id"] == "D13CECS001"
    assert values["ly_do"]  # reason filled from the question
    assert values["date"]  # date defaulted to today
    assert result.created_by_ai is False  # heuristic path
    assert result.file_kind == "pdf"


def test_personal_fields_are_authoritative_over_llm(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "sk-test")

    class _Resp:
        content = '{"fields": {"full_name": "WRONG NAME", "ly_do": "em xin nghỉ học"}, "narrative": "n"}'

    class _Model:
        async def ainvoke(self, _messages):
            return _Resp()

    monkeypatch.setattr(form_suggest, "build_chat_model", lambda *a, **k: _Model())
    result = _run(request=_request(), fields=_fields(), personal_facts=_FACTS, file_kind="docx")
    values = {f.key: f.value for f in result.fields}
    assert values["full_name"] == "Nguyễn Văn A"  # deterministic fact wins over the LLM hallucination
    assert values["ly_do"] == "em xin nghỉ học"  # LLM fills the request-specific field
    assert result.created_by_ai is True


def test_fail_open_to_heuristic_on_llm_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "sk-test")

    def _boom(*_a, **_k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(form_suggest, "build_chat_model", _boom)
    result = _run(request=_request(), fields=_fields(), personal_facts=_FACTS, file_kind="docx")
    values = {f.key: f.value for f in result.fields}
    assert values["full_name"] == "Nguyễn Văn A"
    assert values["ly_do"]  # still filled by the heuristic
    assert result.created_by_ai is False


def test_does_not_mutate_caller_fields(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "")
    original = _fields()
    _run(request=_request(), fields=original, personal_facts=_FACTS, file_kind="docx")
    assert all(field.value == "" for field in original)  # caller's list untouched


def test_vi_note_selected_for_vietnamese_form(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "sk-test")
    captured: dict = {}

    class _Resp:
        content = '{"fields": {}, "narrative": ""}'

    class _Model:
        async def ainvoke(self, messages):
            captured["system"] = messages[0]["content"]
            return _Resp()

    monkeypatch.setattr(form_suggest, "build_chat_model", lambda *a, **k: _Model())
    _run(request=_request(), fields=_fields(), personal_facts=_FACTS, file_kind="docx")
    assert "xưng" in captured["system"]  # the Vietnamese formal-register note was appended
