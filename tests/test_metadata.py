import pytest
from pydantic import ValidationError

from vinchatbot.app.ingest.normalizer import guess_language
from vinchatbot.app.schemas.document import DocumentChunk, DocumentMetadata


def test_metadata_rejects_missing_required_citation_fields():
    with pytest.raises(ValidationError):
        DocumentMetadata(
            canonical_url="https://policy.vinuni.edu.vn/example",
            document_title="Policy",
            chunk_id="chunk-1",
            parent_doc_id="doc-1",
            content_hash="hash",
        )


def test_chunk_requires_non_empty_text():
    metadata = DocumentMetadata(
        source_url="https://policy.vinuni.edu.vn/example",
        canonical_url="https://policy.vinuni.edu.vn/example",
        document_title="Policy",
        chunk_id="chunk-1",
        parent_doc_id="doc-1",
        content_hash="hash",
    )

    with pytest.raises(ValidationError):
        DocumentChunk(text="   ", metadata=metadata)


def test_guess_language_handles_english_vietnamese_and_mixed_text():
    assert guess_language("Course drop deadline and tuition policy") == "en"
    assert guess_language("Sinh viên cần kiểm tra hạn đăng ký học phần.") == "vi"
    assert guess_language("Sinh viên cần kiểm tra course drop deadline.") == "mixed"

