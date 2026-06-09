import io

import pytest

from vinchatbot.app.ingest.assets import (
    build_ocr_text_record,
    extract_html_image_assets,
    extract_html_table_records,
    extract_pdf_page_image_assets,
)
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.ocr import OcrResult
from vinchatbot.app.ingest.parsers import parse_spreadsheet_bytes
from vinchatbot.app.schemas.document import RawDocument, stable_hash


def test_html_image_asset_metadata_has_context_description_and_ocr_disabled():
    html = """
    <html><body>
      <h1>Student Gateway</h1>
      <h2>Academic Calendar</h2>
      <figure>
        <img src="/assets/calendar.png" alt="Academic calendar overview" width="1200" height="800">
        <figcaption>Calendar timeline for students</figcaption>
      </figure>
    </body></html>
    """

    records = extract_html_image_assets(
        html,
        "https://vinuni.edu.vn/student-gateway/",
        {"document_title": "Gateway for VinUnians"},
        enable_ocr=False,
    )

    assert len(records) == 1
    record = records[0]
    assert record.record_type == "image_asset"
    assert record.data["asset_url"] == "https://vinuni.edu.vn/assets/calendar.png"
    assert record.data["alt_text"] == "Academic calendar overview"
    assert record.data["caption"] == "Calendar timeline for students"
    assert record.data["section_path"] == ["Student Gateway", "Academic Calendar"]
    assert record.data["description_source"] == "caption"
    assert record.data["ocr_status"] == "disabled"


def test_html_image_with_nearby_context_becomes_retrievable_chunk_and_ocr_candidate():
    html = """
    <html><body>
      <h1>Student Gateway</h1>
      <h2>Exam Schedule</h2>
      <div>
        Final exam timetable and deadline summary for students.
        <img src="/assets/exam-schedule.png">
      </div>
    </body></html>
    """

    records = extract_html_image_assets(
        html,
        "https://vinuni.edu.vn/student-gateway/",
        {"document_title": "Gateway for VinUnians"},
        enable_ocr=False,
    )
    raw = RawDocument(
        source_url="https://vinuni.edu.vn/student-gateway/",
        canonical_url="https://vinuni.edu.vn/student-gateway/",
        title="Gateway for VinUnians",
        document_type="gateway_page",
        content="",
        metadata={"source_kind": "gateway_page", "category": "gateway", "subcategory": "student_support"},
        structured_records=records,
    )

    chunks = chunk_document(raw)

    assert records[0].data["description_source"] == "context"
    assert records[0].data["needs_ocr"] is True
    assert chunks
    assert chunks[0].metadata.record_type == "image_asset"
    assert "Final exam timetable" in chunks[0].text


def test_html_image_without_text_context_is_flagged_but_not_chunked():
    html = '<html><body><img src="/assets/banner.png"></body></html>'

    records = extract_html_image_assets(
        html,
        "https://vinuni.edu.vn/student-gateway/",
        {"document_title": "Gateway for VinUnians"},
        enable_ocr=False,
    )
    raw = RawDocument(
        source_url="https://vinuni.edu.vn/student-gateway/",
        canonical_url="https://vinuni.edu.vn/student-gateway/",
        title="Gateway for VinUnians",
        document_type="gateway_page",
        content="",
        metadata={"source_kind": "gateway_page", "category": "gateway", "subcategory": "student_support"},
        structured_records=records,
    )

    assert records[0].data["needs_ocr"] is True
    assert chunk_document(raw) == []


def test_html_table_record_generates_rag_text_and_chunk():
    html = """
    <html><body>
      <h1>Financial Regulations</h1>
      <table>
        <tr><th>Fee</th><th>Amount</th><th>Collection time</th></tr>
        <tr><td>Student ID Card Replacement</td><td>200,000 VND</td><td>At request time</td></tr>
      </table>
    </body></html>
    """
    records = extract_html_table_records(
        html,
        "https://policy.vinuni.edu.vn/all-policies/financial-regulations/",
        {"document_title": "Financial Regulations"},
    )
    raw = RawDocument(
        source_url="https://policy.vinuni.edu.vn/all-policies/financial-regulations/",
        canonical_url="https://policy.vinuni.edu.vn/all-policies/financial-regulations/",
        title="Financial Regulations",
        document_type="financial_policy",
        content="",
        metadata={"source_kind": "financial_policy", "category": "student_affairs", "subcategory": "financial"},
        structured_records=records,
    )

    chunks = chunk_document(raw)

    assert records[0].record_type == "table_record"
    assert "Columns: Fee | Amount | Collection time" in records[0].data["rag_text"]
    assert chunks
    assert chunks[0].metadata.record_type == "table_record"
    assert "Student ID Card Replacement" in chunks[0].text


def test_pdf_sparse_page_is_marked_needs_ocr_when_ocr_disabled():
    records = extract_pdf_page_image_assets(
        page_stats=[
            {"page_number": 3, "text_char_count": 12, "embedded_image_count": 1, "width": 612, "height": 792}
        ],
        source_url="https://policy.vinuni.edu.vn/calendar.pdf",
        parent_doc_id=stable_hash("https://policy.vinuni.edu.vn/calendar.pdf"),
        metadata={"document_title": "Academic Calendar"},
        enable_ocr=False,
        ocr_engine="paddleocr",
        ocr_model="PP-OCRv5",
        ocr_lang="en",
        ocr_min_text_chars_per_page=40,
        ocr_max_pdf_pages=20,
    )

    assert records[0].record_type == "image_asset"
    assert records[0].data["needs_ocr"] is True
    assert records[0].data["ocr_status"] == "disabled"


def test_ocr_text_record_becomes_retrievable_chunk():
    result = OcrResult(text="Important deadline: 12 Sep 2025", confidence=0.91, bbox_count=2)
    record = build_ocr_text_record(
        source_url="https://policy.vinuni.edu.vn/calendar.pdf",
        parent_doc_id=stable_hash("https://policy.vinuni.edu.vn/calendar.pdf"),
        metadata={"document_title": "Academic Calendar"},
        asset_url="https://policy.vinuni.edu.vn/calendar.pdf#page=3",
        page_number=3,
        result=result,
        ocr_engine="paddleocr",
        ocr_model="PP-OCRv5",
        ocr_lang="en",
    )
    raw = RawDocument(
        source_url="https://policy.vinuni.edu.vn/calendar.pdf",
        canonical_url="https://policy.vinuni.edu.vn/calendar.pdf",
        title="Academic Calendar",
        document_type="calendar_pdf",
        content="",
        metadata={"source_kind": "calendar_pdf", "category": "academic", "subcategory": "calendar"},
        structured_records=[record],
    )

    chunks = chunk_document(raw)

    assert len(chunks) == 1
    assert chunks[0].metadata.record_type == "ocr_text"
    assert chunks[0].metadata.ocr_confidence == 0.91
    assert "Important deadline" in chunks[0].text


def test_csv_parser_emits_spreadsheet_rows_and_fee_records():
    csv_content = b"Fee,Amount,Collection time\nStudent ID Card Replacement,200000 VND,At request time\n"

    raw = parse_spreadsheet_bytes(
        csv_content,
        "https://policy.vinuni.edu.vn/wp-content/uploads/fees.csv",
        content_type="text/csv",
    )

    record_types = {record.record_type for record in raw.structured_records}
    assert "spreadsheet_row" in record_types
    assert "fee_record" in record_types
    fee_record = next(record for record in raw.structured_records if record.record_type == "fee_record")
    assert fee_record.data["amount"] == 200000


def test_spreadsheet_parser_falls_back_when_xlsx_url_contains_csv():
    csv_content = b"Fee,Amount\nStudent ID Card Replacement,200000 VND\n"

    raw = parse_spreadsheet_bytes(
        csv_content,
        "https://policy.vinuni.edu.vn/wp-content/uploads/fees.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert raw.metadata["parser_warning"] == "spreadsheet_csv_fallback"
    assert any(record.record_type == "spreadsheet_row" for record in raw.structured_records)


def test_spreadsheet_parser_falls_back_when_excel_url_contains_html_table():
    html_content = b"""
    <html><body><table>
      <tr><th>Fee</th><th>Amount</th></tr>
      <tr><td>Student ID Card Replacement</td><td>200000 VND</td></tr>
    </table></body></html>
    """

    raw = parse_spreadsheet_bytes(
        html_content,
        "https://policy.vinuni.edu.vn/wp-content/uploads/fees.xls",
        content_type="application/vnd.ms-excel",
    )

    assert raw.document_type == "spreadsheet"
    assert raw.metadata["parser_warning"] == "spreadsheet_html_fallback"
    assert any(record.record_type == "table_record" for record in raw.structured_records)


def test_spreadsheet_parser_keeps_corrupt_excel_as_file_asset():
    raw = parse_spreadsheet_bytes(
        b"not an excel workbook",
        "https://policy.vinuni.edu.vn/wp-content/uploads/broken.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert raw.structured_records
    assert raw.structured_records[0].record_type == "file_asset"
    assert raw.structured_records[0].data["parser_warning"]


def test_spreadsheet_parser_reads_valid_xlsx_when_optional_dependencies_exist():
    pytest.importorskip("pandas")
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Fees"
    sheet.append(["Fee", "Amount"])
    sheet.append(["Student ID Card Replacement", "200000 VND"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    raw = parse_spreadsheet_bytes(
        buffer.getvalue(),
        "https://policy.vinuni.edu.vn/wp-content/uploads/fees.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert any(record.record_type == "spreadsheet_row" for record in raw.structured_records)
    assert "Student ID Card Replacement" in raw.content
