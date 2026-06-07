# VinChatbot

Backend MVP cho chatbot hỗ trợ sinh viên VinUni bằng RAG + ReAct agent.

## Kiến trúc nhanh

- FastAPI cung cấp `/chat`, `/ingest/run`, `/sources`, `/health`.
- LangChain `create_agent` chạy ReAct tool loop trên LangGraph.
- `conversation_id` trong request được dùng làm LangGraph `thread_id` để giữ short-term context.
- OpenRouter dùng cho chat, embeddings và rerank.
- Qdrant dùng hybrid dense + sparse retrieval.
- Ngôn ngữ trả lời mặc định là tiếng Việt.

## Cài đặt

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Cập nhật `.env` với `OPENROUTER_API_KEY`. Nếu dùng Qdrant Cloud, thêm `QDRANT_URL` và `QDRANT_API_KEY`; nếu không, local Qdrant path sẽ nằm trong `data/qdrant`.

## Chạy API

```powershell
uvicorn vinchatbot.app.main:app --reload
```

Ví dụ chat:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/chat `
  -ContentType "application/json" `
  -Body '{"message":"Hạn drop course là khi nào?","conversation_id":"demo-1"}'
```

## Crawl và ingest

```powershell
py scripts/crawl_seed.py
py scripts/ingest_documents.py
```

Hoặc gọi API:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/ingest/run `
  -ContentType "application/json" `
  -Body '{}'
```

Crawler hiện tại là domain-aware crawler cho VinUni:

- Seed chính gồm Student Gateway, Academic Calendar, toàn bộ policy category pages, All Policies, What's New và Publication.
- Tự discovery public links từ `policy.vinuni.edu.vn`, public VinUni-owned subdomains, public PDFs/files.
- Private/login-required links như SIS, Canvas, SharePoint, Microsoft Forms được lưu thành link reference thay vì index vào vector DB.
- Crawl artifacts:
  - `data/raw/*.json`: normalized raw documents
  - `data/processed/chunks.json`: vector chunks
  - `data/processed/crawl_manifest.json`: crawl manifest/idempotency metadata
  - `data/processed/link_references.json`: skipped/private/external link references
  - `data/processed/structured_records.json`: calendar events, fee records, policy listings, program records

Các crawl caps có thể chỉnh trong `.env`:

```env
CRAWL_MAX_PAGES_TOTAL=500
CRAWL_MAX_VINUNI_PAGES_PER_DOMAIN=50
CRAWL_MAX_EXTERNAL_PAGES_PER_DOMAIN=10
CRAWL_VINUNI_MAX_DEPTH=2
CRAWL_EXTERNAL_MAX_DEPTH=1
```

## Test

```powershell
py -m pytest
```

## Nguồn dữ liệu seed v1

- `https://vinuni.edu.vn/student-gateway/`
- `https://policy.vinuni.edu.vn/student-affairs/`
- Student Code of Conduct
- Financial Regulations and Tariff for Student
- Academic Calendar PDF
