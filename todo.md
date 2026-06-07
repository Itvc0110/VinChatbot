# TODO VinChatbot

Backlog sau khi da co scaffold RAG + ReAct va domain-aware crawler.

## Da lam

- [x] Scaffold FastAPI, LangChain/LangGraph agent, OpenRouter adapters, Qdrant retriever.
- [x] Domain-aware crawler voi frontier, dedupe, robots.txt, depth/domain caps.
- [x] Mo rong seed URLs cho Student Gateway, Academic Calendar, All Policies va policy categories.
- [x] Them metadata 3 tang: source-level, chunk-level, structured-record-level.
- [x] Ghi crawl artifacts:
  - `data/raw/*.json`
  - `data/processed/chunks.json`
  - `data/processed/crawl_manifest.json`
  - `data/processed/link_references.json`
  - `data/processed/structured_records.json`
- [x] Parsers ban dau cho policy listing, policy detail, calendar event, fee record, program record.
- [x] Tests co ban cho crawler metadata va parser.
- [x] Asset-aware crawler/parser v1.
  - HTML `image_asset` metadata voi alt/caption/nearby text/section path.
  - HTML/PDF/Markdown table `table_record`.
  - CSV/XLSX `spreadsheet_row` parser, XLSX dung optional `pandas/openpyxl`.
  - Direct binary `file_asset`/`image_asset` parser.
  - PaddleOCR PP-OCRv5 English selected, `ENABLE_OCR=false` mac dinh.
  - Sparse PDF pages duoc danh dau `needs_ocr=true`.
  - OCR/table/spreadsheet records co the thanh retrievable chunks khi co text tot.

## P0 - Viec can lam ngay

- [ ] Dien `.env` that.
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_CHAT_MODEL`
  - `OPENROUTER_EMBEDDING_MODEL`
  - `OPENROUTER_RERANK_MODEL`
  - `QDRANT_URL` va `QDRANT_API_KEY` neu dung Qdrant Cloud.

- [ ] Chay crawl that lan dau va inspect artifacts.
  - Kiem tra so luong docs trong `data/raw`.
  - Kiem tra `crawl_manifest.json` co hash/status/skip reason.
  - Kiem tra `link_references.json` co skip SIS/Canvas/SharePoint/social dung ky vong.
  - Kiem tra `structured_records.json` co policy listings, fee records, calendar events.

- [ ] Chay ingest vao Qdrant voi data that.
  - Xac nhan collection duoc tao.
  - Xac nhan chunks co metadata day du.
  - Test `/chat` voi cau hoi calendar/financial/conduct.

- [ ] Fix neu crawl thuc te phat hien HTML layout khac fixture.
  - Policy listing table.
  - Policy detail Status and Details.
  - Calendar PDF one-page dense layout.
  - Financial fee table.

## P1 - Metadata va idempotency

- [ ] Them crawler CLI flags.
  - `--max-pages`
  - `--force`
  - `--seed-url`
  - `--dry-run`
  - `--no-external`

- [ ] Cai thien idempotent indexing.
  - Neu `content_hash` khong doi: skip indexing.
  - Neu document doi: delete old chunks theo `parent_doc_id`, roi upsert chunks moi.
  - Ghi `indexed_at`, `index_status`, `chunk_count` vao manifest.

- [ ] Them source registry.
  - Luu moi source document voi status: crawled, skipped, failed, private, noindex.
  - Luu error message neu HTTP/parser fail.

- [ ] Chuan hoa metadata filter quan trong.
  - `source_kind`
  - `category`
  - `subcategory`
  - `policy_code`
  - `security_classification`
  - `academic_year`
  - `term`
  - `event_type`
  - `fee_type`

## P2 - Xu ly data theo tung datatype

- [ ] Asset/OCR production pass.
  - Neu can OCR: cai `.[ocr]`, bat `ENABLE_OCR=true`, test PaddleOCR tren Windows.
  - Neu can PDF table/XLSX: cai `.[tables]`, test `pdfplumber` va `openpyxl`.
  - Them image header download de lay kich thuoc/file size khi `IMAGE_DOWNLOAD_ENABLED=true`.
  - Them cache binary asset neu can audit ve sau.
  - Ghi nho chien luoc hien tai: khong OCR/chunk moi anh mac dinh; HTML image chi tao `image_asset` metadata va chi enqueue/download khi `IMAGE_DOWNLOAD_ENABLED=true`.
  - Neu muon OCR moi anh: bat ca `IMAGE_DOWNLOAD_ENABLED=true` va `ENABLE_OCR=true`; can them cache/size cap/rate limit rieng truoc khi crawl lon.
  - Nguong PDF can OCR hien tai: page text layer `< OCR_MIN_TEXT_CHARS_PER_PAGE`, mac dinh 40 ky tu.
  - Nguong OCR text duoc chunk hien tai: OCR text dai toi thieu 20 ky tu trong `chunker.py`.
  - Can quyet dinh sau: co chunk moi `image_asset.description` khong co alt/caption hay khong; hien tai chi chunk image description khi co alt hoac caption.

- [ ] Policy listing parser production.
  - Extract chinh xac title/code/issued/updated/detail URL.
  - Dedupe policy xuat hien o nhieu category.

- [ ] Policy detail parser production.
  - Extract Status and Details.
  - Extract Record of Changes.
  - Link HTML policy voi PDF version.

- [ ] Calendar parser production.
  - Normalize date range thanh ISO.
  - Tach event type: instruction, add deadline, drop deadline, exam, holiday, registration.
  - Gan term/year dung cho Fall/Spring/Summer.

- [ ] Financial parser production.
  - Parse table row thay vi chi regex theo line.
  - Extract amount, unit, currency, collection time, conditions.
  - Gan fee type: tuition, exam, library, admin, retake, scholarship/aid.

- [ ] Registrar/library parser.
  - Extract FAQ/procedure/forms/hours/access/fines.
  - Skip login-only content.

- [ ] Markdown/text parser.
  - Neu gap `.md` hoac `text/markdown`, parse heading tree nhu Markdown.
  - Giu section path va line offsets neu co.

## P3 - Metadata-aware RAG

- [ ] Dung metadata de route query truoc khi retrieve.
  - Calendar query -> `source_kind in calendar_page/calendar_pdf`.
  - Fee query -> `source_kind=financial_policy` hoac `record_type=fee_record`.
  - Policy query -> `policy_html/policy_pdf`.

- [ ] Dung metadata de boost/rerank.
  - Boost official_high source.
  - Boost exact `policy_code`, `term`, `academic_year`, `event_type`.
  - Penalize external_low.

- [ ] Chi extract citation tu tool result cua turn hien tai.
- [ ] Them answer guard: fee/deadline/policy claim bat buoc co citation.
- [ ] Them eval set 70 cau:
  - 20 calendar.
  - 20 conduct/policy.
  - 20 financial.
  - 10 private/unsupported/adversarial.

## P4 - Production hardening

- [ ] Auth/admin guard cho `/ingest/run`.
- [ ] Structured logging cho crawl/retrieval/rerank/OpenRouter latency.
- [ ] PostgresSaver cho production short-term memory.
- [ ] Dockerfile va docker-compose voi Qdrant/Postgres.
- [ ] CI chay `pytest`, `compileall`, lint.

## Nguyen tac

- Chat runtime khong crawl web.
- Crawl/ingest la offline/admin pipeline.
- Conversation memory chi de hieu ngu canh, khong phai source of truth.
- Source of truth cho fee/deadline/policy phai den tu retrieval co citation.
- Private/login-required pages chi luu link reference, khong index content.


Lọc lại chunk level meta-data