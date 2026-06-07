from vinchatbot.app.ingest.crawler import (
    SEED_URLS,
    VinUniCrawler,
    _manifest_is_unchanged,
)
from vinchatbot.app.ingest.parsers import (
    extract_fee_records,
    extract_policy_detail_metadata,
    parse_html,
    parse_policy_listing_records,
)
from vinchatbot.app.schemas.document import CrawlManifestEntry, CrawlTarget, RawDocument


def test_policy_listing_parser_extracts_policy_table_rows():
    html = """
    <html><body>
      <h2>Student Affairs</h2>
      <table>
        <tr>
          <th>Policy title</th><th>Policy code</th><th>Date issued</th><th>Date last updated</th>
        </tr>
        <tr>
          <td><a href="/all-policies/student-affairs-regulations-code-of-conduct/">Student Code of Conduct</a></td>
          <td>VU_CTSV02.EN</td><td>Dec 24, 2025</td><td>Dec 24, 2025</td>
        </tr>
      </table>
    </body></html>
    """

    records = parse_policy_listing_records(html, "https://policy.vinuni.edu.vn/student-affairs/")

    assert len(records) == 1
    assert records[0].record_type == "policy_listing"
    assert records[0].data["policy_title"] == "Student Code of Conduct"
    assert records[0].data["policy_code"] == "VU_CTSV02.EN"
    assert records[0].data["date_issued"] == "Dec 24, 2025"
    assert records[0].data["detail_url"].endswith("/all-policies/student-affairs-regulations-code-of-conduct/")


def test_policy_detail_parser_extracts_status_fields_and_pdf():
    html = """
    <html><body>
      <h1>Student Code of Conduct</h1>
      <h3>Status and Details</h3>
      <h4>Reference Number:</h4><p>VU_CTSV02.EN</p>
      <h4>Document Type:</h4><p>Policy</p>
      <h4>Issuing By:</h4><p>VinUniversity</p>
      <h4>Issuing Date:</h4><p>Dec 24, 2025</p>
      <h4>Applying for:</h4><p>All VinUni staff, faculty and students</p>
      <h4>Security Classification:</h4><p>Public</p>
      <h3>PDF version</h3>
      <a href="/wp-content/uploads/code-of-conduct.pdf">Student Code of Conduct</a>
    </body></html>
    """

    metadata = extract_policy_detail_metadata(
        html,
        "https://policy.vinuni.edu.vn/all-policies/student-affairs-regulations-code-of-conduct/",
    )

    assert metadata["document_title"] == "Student Code of Conduct"
    assert metadata["reference_number"] == "VU_CTSV02.EN"
    assert metadata["document_status"] == "Policy"
    assert metadata["security_classification"] == "Public"
    assert metadata["pdf_url"].endswith("/wp-content/uploads/code-of-conduct.pdf")


def test_financial_parser_extracts_fee_records():
    raw = RawDocument(
        source_url="https://policy.vinuni.edu.vn/all-policies/financial-regulations-and-tariff-for-student-2/",
        canonical_url="https://policy.vinuni.edu.vn/all-policies/financial-regulations-and-tariff-for-student-2/",
        title="Financial Regulations and Tariff (for student)",
        document_type="financial_policy",
        content=(
            "Student ID Card Replacement 200,000 VND/card At the time of student's request\n"
            "Exam Score Review 1,000,000 VND/request/subject Upon receipt of application"
        ),
        metadata={"source_kind": "financial_policy"},
    )

    records = extract_fee_records(raw)

    assert len(records) == 2
    assert records[0].data["amount"] == 200000
    assert records[0].data["currency"] == "VND"
    assert records[1].data["fee_type"] == "exam"


def test_parse_html_adds_source_kind_and_structured_records():
    html = """
    <html><head><title>Student Affairs - VinUni Policy</title></head><body>
      <h2>Student Affairs</h2>
      <table><tr>
        <td><a href="/all-policies/financial-regulations-and-tariff-for-student-2/">Financial Regulations and Tariff (for student)</a></td>
        <td>VUNI_TS03_Student</td><td>Oct 08, 2025</td><td>Jul 23, 2025</td>
      </tr></table>
    </body></html>
    """

    raw = parse_html(html, "https://policy.vinuni.edu.vn/student-affairs/")

    assert raw.document_type == "policy_listing"
    assert raw.metadata["source_kind"] == "policy_listing"
    assert raw.structured_records
    assert raw.structured_records[0].record_type == "policy_listing"


def test_crawler_marks_private_links_as_references():
    crawler = VinUniCrawler()
    target = CrawlTarget(
        source_url="https://sis.vinuni.edu.vn/",
        parent_url="https://vinuni.edu.vn/student-gateway/",
        crawl_depth=1,
        anchor_text="SIS",
    )

    should_fetch, reason = crawler._should_fetch_target(target, {})
    reference = crawler._target_to_link_reference(target, reason)

    assert should_fetch is False
    assert reason == "private_or_login_required"
    assert reference.requires_login is True
    assert reference.should_crawl is False


def test_manifest_detects_unchanged_content():
    entry = CrawlManifestEntry(
        source_id="1",
        source_url="https://policy.vinuni.edu.vn/student-affairs/",
        final_url="https://policy.vinuni.edu.vn/student-affairs/",
        canonical_url="https://policy.vinuni.edu.vn/student-affairs/",
        content_hash="abc",
        parser_version="v2",
    )
    previous = {entry.canonical_url: entry}

    assert _manifest_is_unchanged(entry, previous)


def test_seed_urls_include_direct_academic_calendar_pdf():
    assert "https://policy.vinuni.edu.vn/wp-content/uploads/2025/06/VinUni-Academic-Calendar.pdf" in SEED_URLS
