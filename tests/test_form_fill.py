from __future__ import annotations

import pytest

from vinchatbot.app.schemas.forms import FormField
from vinchatbot.app.services.form_fill import (
    analyze_form,
    build_docx,
    default_form_fields,
    fill_pdf,
    is_allowed_form_url,
    render_form_file,
)

fitz = pytest.importorskip("fitz")


# --- Fixtures: tiny in-memory PDFs ---------------------------------------------------------------

def _fillable_pdf() -> bytes:
    """A minimal AcroForm PDF with two text widgets."""
    doc = fitz.open()
    page = doc.new_page()
    for index, name in enumerate(("full_name", "reason")):
        widget = fitz.Widget()
        widget.field_name = name
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(100, 100 + index * 40, 400, 130 + index * 40)
        page.add_widget(widget)
    return doc.tobytes()


def _flat_pdf() -> bytes:
    """A flat (non-fillable) PDF whose text carries a 'Label: ___' blank."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Ho va ten: ______")
    return doc.tobytes()


# --- SSRF guard ----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url,allowed",
    [
        ("https://registrar.vinuni.edu.vn/vi/hoc-thuat-dich-vu/bieu-mau-don-tu/", True),
        ("https://policy.vinuni.edu.vn/wp-content/uploads/2023/05/Form-01.pdf", True),
        ("https://vinuni.edu.vn/form.docx", True),
        ("http://evil.com/vinuni.edu.vn/form.pdf", False),
        ("https://vinuni.edu.vn.attacker.com/form.pdf", False),
        ("file:///etc/passwd", False),
        ("https://169.254.169.254/latest/meta-data/", False),
    ],
)
def test_is_allowed_form_url(url, allowed):
    assert is_allowed_form_url(url) is allowed


# --- analyze_form paths --------------------------------------------------------------------------

def test_analyze_form_fillable_pdf_returns_widget_fields():
    kind, fields = analyze_form(_fillable_pdf(), "application/pdf", "https://vinuni.edu.vn/f.pdf")
    assert kind == "pdf"
    assert {f.key for f in fields} == {"full_name", "reason"}


def test_analyze_form_flat_pdf_returns_docx_with_recognized_and_default_fields():
    kind, fields = analyze_form(_flat_pdf(), "application/pdf", "https://vinuni.edu.vn/flat.pdf")
    assert kind == "docx"
    keys = {f.key for f in fields}
    assert "ho_va_ten" in keys  # recognized "Ho va ten:" blank
    assert "student_id" in keys  # merged default personal field


def test_analyze_form_non_pdf_falls_back_to_default_docx_fields():
    kind, fields = analyze_form(b"not a pdf", "text/html", "https://vinuni.edu.vn/page")
    assert kind == "docx"
    assert {f.key for f in fields} == {key for key, _ in _default_keys()}


def _default_keys():
    return [(f.key, f.label) for f in default_form_fields()]


# --- rendering -----------------------------------------------------------------------------------

def test_fill_pdf_sets_widget_values_and_stays_a_pdf():
    filled = fill_pdf(_fillable_pdf(), {"full_name": "Nguyen Van A", "reason": "xin nghi hoc"})
    assert filled[:5] == b"%PDF-"
    with fitz.open(stream=filled, filetype="pdf") as doc:
        values = {w.field_name: w.field_value for page in doc for w in (page.widgets() or [])}
    assert values["full_name"] == "Nguyen Van A"


def test_build_docx_returns_a_docx_zip():
    data = build_docx("Đơn xin nghỉ học", [FormField(key="full_name", label="Họ tên", value="A")], "note")
    assert data[:2] == b"PK"  # docx is a zip


def test_render_form_file_pdf_path_fills_original():
    data, mime, ext = render_form_file(
        "pdf", _fillable_pdf(), "Form", [FormField(key="full_name", label="Name", value="B")]
    )
    assert ext == "pdf" and mime == "application/pdf" and data[:5] == b"%PDF-"


def test_render_form_file_docx_path_when_no_content():
    data, mime, ext = render_form_file(
        "docx", None, "Form", [FormField(key="full_name", label="Name", value="B")]
    )
    assert ext == "docx" and data[:2] == b"PK"


def test_render_form_file_falls_back_to_docx_when_pdf_fill_fails():
    # Passing non-PDF bytes as the "pdf" content forces fill_pdf to error → fail-open to a .docx.
    data, mime, ext = render_form_file(
        "pdf", b"not a pdf", "Form", [FormField(key="full_name", label="Name", value="B")]
    )
    assert ext == "docx" and data[:2] == b"PK"
