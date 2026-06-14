from __future__ import annotations

import asyncio
import json

from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.schemas.chat import ChatRequest

QUESTIONS = [
    "Khi nào bắt đầu học kỳ Fall?",
    "Hạn drop course là khi nào?",
    "Sinh viên có những trách nhiệm gì theo Student Code of Conduct?",
    "Học phí hoặc tariff được quy định ở tài liệu nào?",
]


async def main() -> None:
    service = VinUniAgentService()
    results = []
    for index, question in enumerate(QUESTIONS, start=1):
        response = await service.chat(
            ChatRequest(message=question, conversation_id=f"eval-{index}")
        )
        results.append(response.model_dump())
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

