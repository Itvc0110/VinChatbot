from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException

from vinchatbot.app.agents.tools import _extract_form_files
from vinchatbot.app.api import routes_forms
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.repositories.auth import AuthenticatedUser
from vinchatbot.app.schemas.forms import FillFormRequest, FormField, SuggestFormRequest

fitz = pytest.importorskip("fitz")


def _student() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid.uuid4(),
        email="a@vinuni.edu.vn",
        full_name="Nguyễn Văn A",
        preferred_name=None,
        status="active",
        roles=("student",),
    )


def _fillable_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    widget = fitz.Widget()
    widget.field_name = "full_name"
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.rect = fitz.Rect(100, 100, 400, 130)
    page.add_widget(widget)
    return doc.tobytes()


# --- SSRF guard at the route boundary ------------------------------------------------------------

def test_suggest_form_rejects_non_vinuni_url(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "")
    request = SuggestFormRequest(
        official_url="https://evil.com/form.pdf", origin_question="xin nghỉ học"
    )
    with pytest.raises(HTTPException) as err:
        asyncio.run(routes_forms.suggest_form(request, _student()))
    assert err.value.status_code == 400


def test_fill_form_rejects_non_vinuni_url():
    request = FillFormRequest(official_url="https://evil.com/x.pdf", fields=[])
    with pytest.raises(HTTPException) as err:
        asyncio.run(routes_forms.fill_form(request, _student()))
    assert err.value.status_code == 400


# --- /forms/suggest happy path -------------------------------------------------------------------

def test_suggest_form_fetches_analyzes_and_prefills(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "")  # heuristic (deterministic)

    async def _fake_fetch(url, settings=None):
        return _fillable_pdf(), "application/pdf"

    monkeypatch.setattr(routes_forms, "fetch_form_bytes", _fake_fetch)
    request = SuggestFormRequest(
        official_url="https://registrar.vinuni.edu.vn/form.pdf",
        form_title="Đơn xin nghỉ học",
        origin_question="Tôi muốn xin nghỉ học",
    )
    result = asyncio.run(routes_forms.suggest_form(request, _student()))
    assert result.file_kind == "pdf"
    values = {f.key: f.value for f in result.fields}
    assert values["full_name"] == "Nguyễn Văn A"  # prefilled from the authenticated user


def test_suggest_form_fails_open_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "")

    async def _boom(url, settings=None):
        from vinchatbot.app.services.form_fill import FormFetchError

        raise FormFetchError("unreachable")

    monkeypatch.setattr(routes_forms, "fetch_form_bytes", _boom)
    request = SuggestFormRequest(
        official_url="https://registrar.vinuni.edu.vn/form.pdf", origin_question="xin nghỉ học"
    )
    result = asyncio.run(routes_forms.suggest_form(request, _student()))
    assert result.file_kind == "docx"
    assert result.notice  # tells the student it's a generated editable copy
    assert result.fields  # default personal fields present


# --- /forms/fill streams a file ------------------------------------------------------------------

def test_fill_form_streams_pdf(monkeypatch):
    async def _fake_fetch(url, settings=None):
        return _fillable_pdf(), "application/pdf"

    monkeypatch.setattr(routes_forms, "fetch_form_bytes", _fake_fetch)
    request = FillFormRequest(
        official_url="https://registrar.vinuni.edu.vn/form.pdf",
        form_title="Đơn xin nghỉ học",
        file_kind="auto",
        fields=[FormField(key="full_name", label="Họ tên", value="Nguyễn Văn A")],
    )
    response = asyncio.run(routes_forms.fill_form(request, _student()))
    assert response.media_type == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    body = b"".join(
        chunk if isinstance(chunk, bytes) else chunk.encode()
        for chunk in _iter_stream(response)
    )
    assert body[:5] == b"%PDF-"


def _iter_stream(response):
    async def _collect():
        return [chunk async for chunk in response.body_iterator]

    return asyncio.run(_collect())


# --- _extract_form_files helper (pure) -----------------------------------------------------------

def test_extract_form_files_pulls_urls_from_metadata_and_text():
    results = [
        {
            "text": "Tải mẫu tại https://registrar.vinuni.edu.vn/uploads/don-xin-nghi.docx nhé.",
            "metadata": {"document_title": "Biểu mẫu", "source_url": "https://registrar.vinuni.edu.vn/p"},
        },
        {
            "text": "no link here",
            "metadata": {
                "asset_url": "https://policy.vinuni.edu.vn/uploads/Form-01.pdf",
                "document_title": "Form 01",
                "source_url": "https://policy.vinuni.edu.vn/page",
            },
        },
    ]
    files = _extract_form_files(results)
    urls = {f["url"] for f in files}
    assert "https://registrar.vinuni.edu.vn/uploads/don-xin-nghi.docx" in urls
    assert "https://policy.vinuni.edu.vn/uploads/Form-01.pdf" in urls


def test_extract_form_files_ignores_non_file_urls():
    results = [{"text": "see https://vinuni.edu.vn/page for info", "metadata": {}}]
    assert _extract_form_files(results) == []
