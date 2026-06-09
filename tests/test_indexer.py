from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from uuid import UUID

import pytest

from vinchatbot.app.ingest import indexer
from vinchatbot.app.schemas.document import DocumentChunk, DocumentMetadata
from vinchatbot.app.storage.qdrant_store import QDRANT_KEYWORD_PAYLOAD_FIELDS


def _chunk(parent_doc_id: str = "doc-1", chunk_id: str = "chunk-1") -> DocumentChunk:
    metadata = DocumentMetadata(
        source_url="https://policy.vinuni.edu.vn/example/",
        canonical_url="https://policy.vinuni.edu.vn/example/",
        document_title="Example Policy",
        chunk_id=chunk_id,
        parent_doc_id=parent_doc_id,
        content_hash=f"hash-{chunk_id}",
    )
    return DocumentChunk(text=f"Chunk text {chunk_id}", metadata=metadata)


def _settings():
    return SimpleNamespace(
        vector_store_backend="qdrant",
        qdrant_collection="vinuni_documents_test",
        qdrant_url=None,
        qdrant_api_key=None,
        qdrant_local_path="data/qdrant-test",
        qdrant_timeout_seconds=120,
        qdrant_batch_size=16,
        chroma_collection="vinuni_documents_test",
        chroma_persist_dir="data/chroma-test",
        pinecone_api_key=None,
        pinecone_index_name="vinuni-documents-test",
        pinecone_namespace=None,
    )


def _install_common_fakes(monkeypatch, store_class) -> None:
    documents_module = types.ModuleType("langchain_core.documents")

    class Document:
        def __init__(self, page_content, metadata):
            self.page_content = page_content
            self.metadata = metadata

    documents_module.Document = Document
    monkeypatch.setitem(sys.modules, "langchain_core.documents", documents_module)

    qdrant_module = types.ModuleType("langchain_qdrant")
    qdrant_module.QdrantVectorStore = store_class
    qdrant_module.RetrievalMode = SimpleNamespace(HYBRID="hybrid")
    monkeypatch.setitem(sys.modules, "langchain_qdrant", qdrant_module)

    import vinchatbot.app.embeddings.openrouter_embeddings as embeddings

    monkeypatch.setattr(embeddings, "build_embeddings", lambda settings: "dense")
    monkeypatch.setattr(indexer, "build_sparse_embeddings", lambda: "sparse")


def _install_fake_qdrant_models(monkeypatch) -> None:
    package = types.ModuleType("qdrant_client")
    models = types.ModuleType("qdrant_client.models")

    class MatchValue:
        def __init__(self, value):
            self.value = value

    class FieldCondition:
        def __init__(self, key, match):
            self.key = key
            self.match = match

    class Filter:
        def __init__(self, must):
            self.must = must

    class PayloadSchemaType:
        KEYWORD = "keyword"

    models.FieldCondition = FieldCondition
    models.Filter = Filter
    models.MatchValue = MatchValue
    models.PayloadSchemaType = PayloadSchemaType
    package.models = models
    monkeypatch.setitem(sys.modules, "qdrant_client", package)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models)


def _expected_payload_indexes() -> list[dict[str, object]]:
    return [
        {
            "collection_name": "vinuni_documents_test",
            "field_name": field_name,
            "field_schema": "keyword",
            "timeout": 120,
        }
        for field_name in QDRANT_KEYWORD_PAYLOAD_FIELDS
    ]


def test_index_chunks_creates_collection_only_when_missing(monkeypatch):
    _install_fake_qdrant_models(monkeypatch)

    class Store:
        created = None
        instance = None

        def __init__(self):
            self.client = SimpleNamespace(created_indexes=[])

            def create_payload_index(collection_name, field_name, field_schema, wait, timeout):
                self.client.created_indexes.append(
                    {
                        "collection_name": collection_name,
                        "field_name": field_name,
                        "field_schema": field_schema,
                        "timeout": timeout,
                    }
                )

            self.client.create_payload_index = create_payload_index

        @classmethod
        def from_existing_collection(cls, **kwargs):
            raise RuntimeError("collection does not exist")

        @classmethod
        def from_documents(cls, documents, ids, **kwargs):
            cls.created = {"documents": documents, "ids": ids, "kwargs": kwargs}
            cls.instance = cls()
            return cls.instance

    _install_common_fakes(monkeypatch, Store)
    monkeypatch.setattr(indexer, "_qdrant_collection_exists", lambda collection_name, location_kwargs: False)

    indexed = indexer.index_chunks([_chunk()], _settings())

    assert indexed == 1
    assert UUID(Store.created["ids"][0])
    assert Store.created["kwargs"]["collection_name"] == "vinuni_documents_test"
    assert Store.created["kwargs"]["batch_size"] == 16
    assert Store.created["kwargs"]["timeout"] == 120
    assert Store.instance.client.created_indexes == _expected_payload_indexes()


def test_index_chunks_creates_local_qdrant_collection_when_not_found(monkeypatch):
    _install_fake_qdrant_models(monkeypatch)

    class Store:
        created = None

        def __init__(self):
            self.client = SimpleNamespace()
            self.client.create_payload_index = lambda **kwargs: None

        @classmethod
        def from_existing_collection(cls, **kwargs):
            raise ValueError("Collection vinuni_documents not found")

        @classmethod
        def from_documents(cls, documents, ids, **kwargs):
            cls.created = {"ids": ids, "kwargs": kwargs}
            return cls()

    _install_common_fakes(monkeypatch, Store)
    monkeypatch.setattr(indexer, "_qdrant_collection_exists", lambda collection_name, location_kwargs: False)

    indexed = indexer.index_chunks([_chunk()], _settings())

    assert indexed == 1
    assert UUID(Store.created["ids"][0])


def test_index_chunks_does_not_recreate_collection_for_real_qdrant_errors(monkeypatch):
    class Store:
        created = False

        @classmethod
        def from_existing_collection(cls, **kwargs):
            raise RuntimeError("Forbidden: invalid API key")

        @classmethod
        def from_documents(cls, *args, **kwargs):
            cls.created = True

    _install_common_fakes(monkeypatch, Store)
    monkeypatch.setattr(indexer, "_qdrant_collection_exists", lambda collection_name, location_kwargs: True)

    with pytest.raises(RuntimeError, match="Qdrant collection is not available"):
        indexer.index_chunks([_chunk()], _settings())

    assert Store.created is False


def test_index_chunks_replaces_existing_parent_doc_chunks(monkeypatch):
    _install_fake_qdrant_models(monkeypatch)

    class Client:
        def __init__(self):
            self.deleted_parent_doc_ids = []
            self.created_indexes = []

        def create_payload_index(self, collection_name, field_name, field_schema, wait, timeout):
            self.created_indexes.append(
                {
                    "collection_name": collection_name,
                    "field_name": field_name,
                    "field_schema": field_schema,
                    "timeout": timeout,
                }
            )

        def delete(self, collection_name, points_selector, wait, timeout):
            self.deleted_parent_doc_ids.append(points_selector.must[0].match.value)

    class Store:
        instance = None

        def __init__(self):
            self.client = Client()
            self.added_ids = []
            self.batch_size = None

        @classmethod
        def from_existing_collection(cls, **kwargs):
            cls.instance = cls()
            return cls.instance

        @classmethod
        def from_documents(cls, *args, **kwargs):
            raise AssertionError("collection should already exist")

        def add_documents(self, documents, ids, batch_size):
            self.added_ids = ids
            self.batch_size = batch_size

    _install_common_fakes(monkeypatch, Store)
    monkeypatch.setattr(indexer, "_qdrant_collection_exists", lambda collection_name, location_kwargs: True)

    indexed = indexer.index_chunks(
        [_chunk(parent_doc_id="doc-1", chunk_id="chunk-1"), _chunk(parent_doc_id="doc-1", chunk_id="chunk-2")],
        _settings(),
    )

    assert indexed == 2
    assert Store.instance.client.created_indexes == _expected_payload_indexes()
    assert Store.instance.client.deleted_parent_doc_ids == ["doc-1"]
    assert [str(UUID(point_id)) for point_id in Store.instance.added_ids] == Store.instance.added_ids
    assert Store.instance.batch_size == 16


def test_qdrant_point_ids_are_stable_valid_uuids():
    chunks = [_chunk(chunk_id="867c41c5af871e8533b10de3fc3966a476e0455d5e53451c59e3f8bc41ba037f")]

    point_ids = indexer._qdrant_point_ids(chunks)

    assert point_ids == indexer._qdrant_point_ids(chunks)
    assert str(UUID(point_ids[0])) == point_ids[0]


def test_qdrant_collection_exists_closes_client_when_collection_missing(monkeypatch):
    closed = []
    received_kwargs = []

    class Client:
        def __init__(self, **kwargs):
            received_kwargs.append(kwargs)

        def get_collection(self, collection_name):
            raise ValueError(f"Collection {collection_name} not found")

        def close(self):
            closed.append(True)

    qdrant_module = types.ModuleType("qdrant_client")
    qdrant_module.QdrantClient = Client
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_module)

    exists = indexer._qdrant_collection_exists(
        "vinuni_documents",
        {"path": "data/qdrant", "timeout": 120},
    )

    assert exists is False
    assert closed == [True]
    assert received_kwargs == [{"path": "data/qdrant", "timeout": 120}]
