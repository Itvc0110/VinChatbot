from __future__ import annotations

import json
import logging
import sys

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.crawler import read_raw_documents, write_structured_records
from vinchatbot.app.ingest.indexer import index_chunks

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


def main() -> None:
    configure_logging()
    settings = get_settings()
    logger.info("Loading raw documents from %s", settings.raw_data_dir)
    documents = read_raw_documents(settings.raw_data_dir)
    logger.info("Loaded documents=%s", len(documents))

    chunks = []
    records = []
    progress_interval = max(1, min(100, len(documents) // 10 or 1))
    for index, document in enumerate(documents, start=1):
        document_chunks = chunk_document(document)
        chunks.extend(document_chunks)
        records.extend(document.structured_records)
        if index == len(documents) or index % progress_interval == 0:
            logger.info(
                "Chunked %s/%s documents chunks=%s structured_records=%s last_type=%s title=%s",
                index,
                len(documents),
                len(chunks),
                len(records),
                document.document_type,
                document.title[:120],
            )

    records_path = f"{settings.processed_data_dir}/structured_records.json"
    logger.info("Writing structured records=%s path=%s", len(records), records_path)
    write_structured_records(records, records_path)

    logger.info(
        "Indexing chunks=%s backend=%s qdrant_collection=%s",
        len(chunks),
        settings.vector_store_backend,
        settings.qdrant_collection,
    )
    indexed = index_chunks(chunks, settings)
    logger.info("Finished indexing indexed=%s", indexed)
    print(
        json.dumps(
            {
                "documents": len(documents),
                "chunks": len(chunks),
                "structured_records": len(records),
                "indexed": indexed,
            }
        )
    )


if __name__ == "__main__":
    main()
