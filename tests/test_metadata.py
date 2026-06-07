import pytest
from pydantic import ValidationError

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

