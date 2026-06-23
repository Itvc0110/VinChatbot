"""Cheap retrieval-only A/B (no answer LLM): does e5 retrieve better than 3-small on the real
indexed corpus? Run once per collection via env (QDRANT_COLLECTION / EMBEDDING_BACKEND /
OPENROUTER_EMBEDDING_MODEL). Prints, per query, the top chunk's score + academic_year + snippet,
so we can eyeball calendar-year correctness and VI<->EN recall. Delete after use.
"""

from __future__ import annotations

import asyncio

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.rag.retriever import QdrantHybridRetriever

QUERIES = [
    # calendar — year correctness + adjacent-row
    ("EN", "What events are in June 2027?"),
    ("VI", "Sự kiện trong tháng 6 năm 2027 là gì?"),
    ("EN", "When is the course drop deadline?"),
    ("VI", "Hạn chót rút môn học là khi nào?"),
    ("VI", "Kỳ đánh giá môn học cuối kỳ mùa hè diễn ra khi nào?"),
    # cross-lingual recall — financial / policy / services
    ("VI", "Học phí ngành Điều dưỡng một năm là bao nhiêu?"),
    ("EN", "academic integrity policy on plagiarism"),
    ("VI", "Trường có dịch vụ tư vấn tâm lý cho sinh viên không?"),
    ("EN", "how do I request my official transcript"),
    ("VI", "Giỗ Tổ Hùng Vương là ngày nào?"),
]


async def main() -> None:
    settings = get_settings()
    retriever = QdrantHybridRetriever(settings)
    print(f"### collection={settings.qdrant_collection} model={settings.openrouter_embedding_model}\n")
    for lang, q in QUERIES:
        chunks = await retriever.search(q, limit=5)
        if not chunks:
            print(f"[{lang}] {q[:48]:48} -> (no results)")
            continue
        top = chunks[0]
        ay = getattr(top.metadata, "academic_year", None)
        et = getattr(top.metadata, "event_type", None)
        snippet = " ".join(top.text.split())[:90]
        score = f"{top.score:.3f}" if top.score is not None else "  -  "
        print(f"[{lang}] {q[:48]:48} -> score={score} AY={ay} et={et}")
        print(f"        {snippet}")


if __name__ == "__main__":
    asyncio.run(main())
