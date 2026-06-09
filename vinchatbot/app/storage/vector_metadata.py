from __future__ import annotations

import json
from typing import Any

from vinchatbot.app.schemas.document import DocumentMetadata

FULL_METADATA_KEY = "_vinchatbot_metadata_json"


def compact_vector_metadata(metadata: DocumentMetadata) -> dict[str, Any]:
    full_payload = metadata.model_dump()
    compact: dict[str, Any] = {FULL_METADATA_KEY: json.dumps(full_payload, ensure_ascii=False)}
    for key, value in full_payload.items():
        if value is None:
            continue
        if isinstance(value, str | int | float | bool):
            compact[key] = value
    return compact


def restore_document_metadata(payload: dict[str, Any]) -> DocumentMetadata:
    full_payload = payload.get(FULL_METADATA_KEY)
    if isinstance(full_payload, str) and full_payload.strip():
        return DocumentMetadata.model_validate(json.loads(full_payload))
    return DocumentMetadata.model_validate(payload)
