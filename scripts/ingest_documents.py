from __future__ import annotations

import json

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.ingest.chunker import chunk_document
from vinchatbot.app.ingest.crawler import read_raw_documents, write_structured_records
from vinchatbot.app.ingest.indexer import index_chunks


def main() -> None:
    settings = get_settings()
    documents = read_raw_documents(settings.raw_data_dir)
    chunks = []
    records = []
    for document in documents:
        chunks.extend(chunk_document(document))
        records.extend(document.structured_records)

    write_structured_records(records, f"{settings.processed_data_dir}/structured_records.json")
    indexed = index_chunks(chunks, settings)
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
