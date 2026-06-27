# VinChatbot — Đánh giá kỹ thuật (Senior Engineering Review)

Đánh giá chuyên sâu về chatbot hỗ trợ sinh viên VinUni: **backend RAG + multi-agent (ReAct)** dùng FastAPI/LangGraph và **frontend Next.js App Router**. Kiến trúc đã được đối chiếu với tài liệu và mã nguồn thực tế; các file nhạy cảm về bảo mật được đọc trực tiếp để xác minh.

> **Phạm vi:** repo có hơn 100 hàm/component. Tài liệu này trình bày đầy đủ mẫu (mục đích / input-output / logic / nơi dùng / tại sao quan trọng / cải tiến) cho những phần cốt lõi, các phần còn lại được tóm tắt trong bảng. Nơi nào chưa đọc từng dòng sẽ được ghi chú rõ.

---

## 1. Dự án làm gì

VinChatbot trả lời câu hỏi của sinh viên VinUni (deadline lịch học, chính sách, học phí, dịch vụ thư viện/phòng đào tạo), **mặc định trả lời bằng tiếng Việt**, dựa trên nội dung web chính thức của VinUni đã được crawl. Theo `README.md` và `ARCHITECTURE.md`:

- **Pipeline ingest offline** crawl các domain VinUni, parse HTML/PDF/spreadsheet, chia chunk, embed (dense + sparse BM25), và index vào **Qdrant**.
- **Pipeline truy vấn online** xử lý mỗi lượt chat qua: các lớp guard an toàn → supervisor định tuyến tới 1 trong 4 specialist agent (ReAct) → tools chạy pipeline hybrid-retrieval → output guards (kiểm tra tính trung thực, rò rỉ bí mật, degrade khi thiếu dữ liệu) → trả về `ChatResponse` kèm citations và điểm tin cậy.
- **Frontend** là portal sinh viên + admin song ngữ (EN/VI) với giao diện chat hướng minh bạch (trạng thái grounding, panel citations, "tại sao có câu trả lời này").

**Tóm tắt thẳng thắn:** *backend RAG/agent/guardrail thực sự mạnh và có tư duy production*; còn *auth và portal admin mới ở mức demo/stub*. Rủi ro lớn nhất nằm ở khoảng cách giữa hai điều này.

---

## 2. Kiến trúc tổng thể

```
Browser ──(same-origin /api/*)──> Next.js (rewrites proxy) ──> FastAPI :8000
                                                                  │
        ┌─────────────────────────────────────────────────────────┘
        ▼
  Input Guards (regex → safety API → LLM classifier)   [agents/guardrails, safety_guard, llm_guard]
        ▼ allowed
  Supervisor (intent: calendar|policy|financial|services)   [agents/supervisor.py]
        ▼
  MỘT Specialist ReAct agent (prompt + tập tool riêng)      [agents/specialists.py]
        ▼ tool call
  Pipeline retrieval: expand → hybrid search (dense+BM25) → RRF fuse → rerank once →
     dedup → metadata boost → dynamic-k → parent-section expand → LITM reorder → injection scan
                                                            [rag/*, storage/qdrant_store.py]
        ▼ chunks
  Specialist soạn câu trả lời + citations
        ▼
  Output Guards (sensitive-output, faithfulness, graceful degrade, moderation tùy chọn)  [agents/vinuni_agent.py]
        ▼
  ChatResponse {answer, citations[], confidence, tool_trace, needs_human_review}
        ▲
  LangGraph checkpointer theo conversation_id (in-memory hoặc Postgres) = bộ nhớ ngắn hạn
```

**Lựa chọn công nghệ chính**

| Hạng mục | Lựa chọn |
|---|---|
| API | FastAPI (`vinchatbot/app/main.py`) |
| Agent runtime | LangChain `create_agent` (ReAct) trên LangGraph |
| LLM / embeddings / rerank | OpenRouter (`gpt-4o-mini` chat, `text-embedding-3-small`, Cohere rerank, `qwen-2.5-7b` guard) |
| Vector DB | Qdrant (hybrid dense + FastEmbed BM25 sparse) |
| An toàn | OpenAI omni-moderation + regex/deobfuscation + LLM injection/scope classifier |
| Frontend | Next.js 14 App Router, React 18, TS — **không dùng thư viện state/data**, tự viết tay |
| Triển khai | Docker Compose: Caddy (auto-HTTPS) → Next.js → FastAPI; Qdrant Cloud bên ngoài |

---

## 3. Cấu trúc thư mục / file

```
VinChatbot/
├─ vinchatbot/app/              # Backend FastAPI (phần kỹ thuật cốt lõi)
│  ├─ main.py                   # app factory, request-id middleware, /health
│  ├─ api/                      # routes_chat.py, routes_ingest.py
│  ├─ agents/                   # graph, supervisor, specialists, tools, prompts,
│  │                            #   guardrails, llm_guard, safety_guard, vinuni_agent
│  ├─ rag/                      # retriever, context, query_engineering, reranker, citations
│  ├─ ingest/                   # crawler, parsers, normalizer, chunker, indexer, assets, ocr
│  ├─ storage/                  # qdrant_store, vector_metadata
│  ├─ llm/ embeddings/          # OpenRouter clients
│  ├─ core/                     # config, logging, observability
│  └─ schemas/                  # chat, document (Pydantic models)
├─ frontend/                    # Portal Next.js
│  ├─ app/                      # App Router: login, student/*, admin/*, api/feedback
│  ├─ components/               # auth/, layouts/, shell/, chat components, portal/
│  └─ lib/                      # auth, api, i18n, theme, types, useAsync, responseState, mock
├─ scripts/                     # crawl_seed, ingest_documents, run_eval, build_core_seeds
├─ tests/                       # 16 file pytest (guards, retrieval, chunker, routes…)
├─ data/                        # raw/ (đã crawl), processed/ (chunks), eval/ (golden QA)
├─ docker-compose.yml, Dockerfile, Caddyfile, DEPLOY.md
├─ frontend_backup_20260618/    # ⚠️ bản sao cũ của frontend — nên xóa
└─ ARCHITECTURE.md, PRD.md, BRIEF.md, FUTURE_IMPROVEMENTS.md, PROJECT_JOURNAL.md, LOGS/
```

Lưu ý: có thư mục `frontend_backup_20260618/` (rác trong repo) và file chưa track `data/eval/golden/multi_intent.json` (theo git status — gợi ý đang đánh giá multi-intent).

---

## 4. Các file chính theo từng mảng

| Mảng | File chính |
|---|---|
| **Backend entry/API** | `main.py`, `api/routes_chat.py`, `api/routes_ingest.py` |
| **Chatbot/agents** | `agents/graph.py`, `agents/supervisor.py`, `agents/specialists.py`, `agents/tools.py`, `agents/prompts.py`, `agents/vinuni_agent.py` |
| **Guards** | `agents/guardrails.py`, `agents/llm_guard.py`, `agents/safety_guard.py` |
| **RAG** | `rag/retriever.py`, `rag/context.py`, `rag/query_engineering.py`, `rag/reranker.py`, `rag/citations.py` |
| **Config/util** | `core/config.py`, `core/logging.py`, `core/observability.py` |
| **Frontend auth** | `lib/auth.tsx`, `components/auth/ProtectedRoute.tsx` |
| **Frontend chat** | `app/student/chat/page.tsx`, `lib/api.ts`, `lib/responseState.ts`, `next.config.js` |

---

## 5. Luồng đầy đủ: khởi động → đăng nhập → role → gửi tin → phản hồi

**Khởi động app.** `uvicorn vinchatbot.app.main:app` gọi `create_app()` (`main.py:14`): load settings, cấu hình logging, đăng ký request-id middleware + `/health` + hai router. Frontend chạy riêng (`next start`) và proxy `/api/*` tới backend qua rewrites trong `next.config.js`.

**Đăng nhập & role.** Hoàn toàn phía client (`lib/auth.tsx`). Màn login có "Continue as Student" / "Continue as Admin" (và nút "SSO" giả cũng đăng nhập như student). `login(role)` chọn `DEMO_STUDENT` hoặc `DEMO_ADMIN` rồi ghi vào `localStorage["vinuni-copilot-session"]`. Không mật khẩu, không token, không gọi server.

**Xử lý role.** `ProtectedRoute.tsx` bọc mọi route group `/student/*` và `/admin/*`. Sau khi hydrate, nó redirect `null → /login`, sai role `→ /403`, đúng thì render. **Chỉ ở phía client** — không có `middleware.ts` và không có kiểm tra ở backend.

**Người dùng gửi tin nhắn.** `app/student/chat/page.tsx` `ask()` thêm placeholder streaming theo kiểu optimistic, tùy chọn ghép thêm context "My Student Info", rồi gọi `postChatStream()`.

**Request từ frontend.** `lib/api.ts` `postChatStream()` POST `{message, conversation_id, filters}` tới `/api/chat/stream`; Next rewrite sang FastAPI `/chat/stream`. Nó tự viết SSE reader để áp dụng event `delta` vào bubble và bắt payload `done` cuối cùng.

**Xử lý backend.** `routes_chat.py` `_resolve_chat()` chạy input guards; nếu được phép, gọi `get_agent_service().chat()`. **Streaming theo kiểu verify-then-reveal**: câu trả lời *hoàn chỉnh, đã qua guard* được tính trước (`routes_chat.py:97`), *sau đó* mới hiển thị từng token — nên không token nào bị thu hồi (khớp với ghi chú bộ nhớ về streaming).

**AI/agent/RAG/tools.** `vinuni_agent.py` `chat()` gọi LangGraph: supervisor định tuyến intent → một specialist ReAct agent lặp (suy nghĩ → gọi tool `search_*` → đọc chunks → trả lời). Mỗi tool gọi `_search()` trong `tools.py`, chạy pipeline retrieval đầy đủ trên Qdrant và lọc bỏ các chunk bị nhiễm injection.

**Render phản hồi.** Output guards chạy; `ChatResponse` quay về. Frontend suy ra một *trạng thái* (grounded / conversational / refusal / degraded) qua `responseState.ts` và render bubble + `SourcesPanel.tsx` (thẻ citation, nhảy tới nguồn, pill tin cậy, trace "tại sao có câu trả lời này").

> **MCP / A2A:** Chưa triển khai. README/ARCHITECTURE ghi rõ là hoãn lại — tools là các hàm `@tool` LangChain in-process. Đừng kỳ vọng có MCP server trong code.

---

## 6. Các hàm/component quan trọng (mẫu đầy đủ)

### Backend — agent core

**`VinUniAgentService.chat`** — `vinuni_agent.py:53`
- **Mục đích:** điều phối trọn một lượt chat (input guard → graph invoke → output guards → ChatResponse).
- **Input/output:** `ChatRequest` → `ChatResponse`.
- **Logic:** reset counter telemetry → `resolve_guardrail_decision` → ghép filter API + chỉ thị ngôn ngữ vào message → `agent.ainvoke(config={thread_id: conversation_id})` → kiểm tra `contains_sensitive_output` → `should_gracefully_degrade or not assess_faithfulness` → moderation output tùy chọn → trích xuất citations/trace/confidence → log lượt chat.
- **Dùng ở:** `routes_chat.py:52` qua `get_agent_service()` có `@lru_cache`.
- **Tại sao quan trọng:** đây là điểm thắt nút duy nhất ép buộc grounding và an toàn. Output guards ở đây là tuyến phòng thủ chính chống hallucination/rò rỉ.
- **Cải tiến:** (1) chạy lại `resolve_guardrail_decision` dù `routes_chat.py:37` đã chạy — truyền decision vào để giảm một nửa chi phí/độ trễ guard trên đường HTTP; (2) không có `recursion_limit` rõ ràng trong config invoke — nên đặt để giới hạn vòng lặp ReAct; (3) repr của `filters.compact()` bị nối vào prompt dưới dạng text tự do (lộ schema + bề mặt injection nhỏ).

**`build_agent_graph`** — `graph.py:45`
- **Mục đích:** biên dịch graph `START → supervisor → <1 trong 4 specialist> → END`.
- **Input/output:** `(retriever, settings?, checkpointer?, specialists?, supervisor_router?)` → graph đã compile.
- **Logic:** `supervisor_node` phân loại intent và **clamp** intent lạ về `"services"` (`graph.py:69`); conditional edge định tuyến tới specialist tương ứng; dependency injection cho phép test offline không cần model.
- **Dùng ở:** `VinUniAgentService.__init__`.
- **Tại sao quan trọng:** đây là cơ chế "multi-agent"; clamp giúp định tuyến fail-safe.
- **Cải tiến:** một intent mỗi lượt — câu hỏi đa intent ("deadline drop course là khi nào *và* phí trễ bao nhiêu?") bị phục vụ thiếu. Cân nhắc fan-out 2 specialist hoặc bước merge.

**`_search`** — `tools.py:26`
- **Mục đích:** cổng retrieval duy nhất mà mọi tool đi qua.
- **Input/output:** `(query, filters?, enforced_filters?)` → chuỗi JSON các chunk `{text, score, metadata}` cho LLM.
- **Logic:** loại filter rỗng → **soft-routing** (category của specialist thành *gợi ý boost*, không phải hard filter, để định tuyến sai không làm trống kết quả) → phát hiện point-lookup → query expansion → một trong ba đường retrieval (fuse-then-rerank-once / legacy / single) → **`scan_for_injection` loại bỏ chunk bị nhiễm** → serialize với `excerpt(text, 900)` + toàn bộ `metadata.model_dump()`.
- **Dùng ở:** cả 5 tool trong `tools.py`.
- **Tại sao quan trọng:** việc lọc indirect-injection ở đây là phòng thủ thực sự, đặt đúng chỗ.
- **Cải tiến:** ⚠️ **`get_source_detail` (`tools.py:165`) bỏ qua injection scan** — nguồn bị nhiễm khi fetch theo URL/id sẽ tới LLM chưa được lọc. Và **`metadata.model_dump()` dump toàn bộ metadata** cho LLM/citations — nên whitelist các trường liên quan citation để tránh lộ trường nội bộ.

**`resolve_guardrail_decision`** — `guardrails.py:317`
- **Mục đích:** cổng input phân tầng, tối ưu chi phí.
- **Input/output:** `(message, filter_values?)` → `GuardrailDecision(action, allowed, ...)`.
- **Logic:** Tier 0 regex + deobfuscation (zero-width / leetspeak / **giải base64**) trả về ngay khi *chắc chắn*; chỉ các trường hợp gray/out-of-scope mới gọi Tier 1 (safety API) rồi Tier 2 (LLM classifier). Mọi tầng API **fail open** (cho phép) để provider lỗi không làm hỏng chat.
- **Dùng ở:** `_resolve_chat` và `VinUniAgentService.chat`.
- **Tại sao quan trọng:** tầng regex là sàn luôn-bật; deobfuscation tốt hơn mức trung bình.
- **Cải tiến:** `contains_sensitive_output` (`guardrails.py:476`) chỉ khớp *tên marker* (`openrouter_api_key`, `system prompt:`), không khớp giá trị bí mật thật hay prompt bị diễn giải lại. `assess_faithfulness` (`guardrails.py:506`) chỉ kiểm tra trùng khớp **số/ngày** — một quy định bịa đặt dạng văn bản thuần sẽ vượt qua cổng faithfulness (chỉ bị bắt bởi kiểm tra có-citation).

### Backend — RAG

**`QdrantHybridRetriever._finalize`** — `retriever.py:265`
- **Mục đích:** biến pool ứng viên thành context xếp hạng cuối.
- **Logic:** rerank-once (Cohere qua OpenRouter, fail-open) → dedup Jaccard → metadata boost → dynamic-k → parent-section expansion → lost-in-the-middle reorder.
- **Tại sao quan trọng:** đây là động cơ chất lượng; mọi bước đều được gate bằng config để A/B test — kỷ luật rất tốt.
- **Cải tiến:** dynamic-k chạy *trước* parent-section expansion, nên có thể *gộp* các chunk anh em (`context.py:117`) → số lượng cuối có thể tụt dưới `min_k` một cách âm thầm. Nên đổi thứ tự bước hoặc áp lại sàn min-k sau khi expand.

**`OpenRouterReranker.rerank`** — `reranker.py:24`
- **Mục đích:** rerank ứng viên; fail-open về thứ tự retrieval.
- **Cải tiến (bug thật):** vòng lặp parse kết quả nằm **ngoài** `try/except`, nên payload API thiếu `index` sẽ raise và thoát ra thành 503 thay vì fail-soft. Đưa parse vào trong khối guard. Ngoài ra: tạo mới `httpx.AsyncClient` mỗi lần gọi (không pooling).

**`expand_query`** — `query_engineering.py:67`
- **Mục đích:** sinh các biến thể paraphrase + cross-lingual cho query.
- **Cải tiến (bug thật):** `line.lstrip("-•*0123456789. )")` (`query_engineering.py:109`) strip một *tập ký tự*, nên biến thể như `"2024-2025 academic calendar"` mất `2024` ở đầu — phá hỏng đúng các query chứa năm mà point-lookup phụ thuộc. Dùng regex prefix (`^[\s\-•*\d.)]+` neo theo list marker, không phải số trần).

### Backend — API

**`run_ingest`** — `routes_ingest.py:27`
- **Mục đích:** `POST /ingest/run` — crawl, parse, chunk, embed, index.
- **Cải tiến (mức cao):** không auth; `request.urls` do caller cung cấp với **không validate scheme/domain → SSRF** (vd. `http://169.254.169.254/...`); chạy đồng bộ trong request (không background task, không khóa concurrency); ghi file không atomic, đua trên file dùng chung.

**`list_sources`** — `routes_ingest.py:71`
- **Cải tiến (hiệu năng):** chạy lại `chunk_document` cho *mỗi* doc trong *mỗi* lần gọi `GET /sources` chỉ để đếm chunk — O(corpus) mỗi request, trên event loop. Nên lưu số chunk lúc ingest.

### Frontend

**`AuthProvider` / `useAuth`** — `lib/auth.tsx:65` — đã nói ở §5; **giả lập, localStorage, sửa được dễ dàng**.

**`ProtectedRoute`** — `ProtectedRoute.tsx:22` — cổng role phía client; chỉ mang tính trang trí, không phải kiểm soát bảo mật.

**`postChatStream`** — `lib/api.ts:72`
- **Mục đích:** stream câu trả lời đã xác minh qua SSE; dispatch `delta`/`done`/`error`.
- **Tại sao quan trọng:** triển khai nửa client của verify-then-reveal; re-throw `AbortError` để cancel ≠ failure.

**`ask`** — `app/student/chat/page.tsx:134`
- **Mục đích:** điều phối một lượt với optimistic UI + khả năng **stream-rồi-fallback-sang-POST**.
- **Cải tiến:** gọi `void ask(...)` *bên trong* updater `setMessages` (`page.tsx:217`) — side effect trong reducer, là anti-pattern React (rủi ro với StrictMode/concurrent). Nên tính text trước rồi mới gọi `ask`.

**`deriveState`** — `responseState.ts` — map `ChatResponse` → grounded/conversational/refusal/degraded để UI hiển thị đúng tín hiệu tin cậy. Sạch, comment tốt; *loại* câu trả lời được suy ra ở client (không nằm trong HTTP status).

---

## 7. Phân tích theo từng mảng

### Frontend (cấu trúc, routing, state, UX)
- **Routing:** App Router với route-group theo role (`/student/*`, `/admin/*`), mỗi cái gate bằng layout mount `ProtectedRoute`. Root `/` và `/login` là bộ redirect thuần. **Không có `error.tsx` / `not-found.tsx` / `loading.tsx`** ở bất kỳ đâu.
- **State:** ba React Context (Theme → Language → Auth) trong `providers.tsx`; data từng view qua hook `useAsync` tự viết + `AsyncBoundary`. Không Redux/Zustand/React-Query — phù hợp với quy mô.
- **Tầng data:** rõ ràng **nửa-thật, nửa-mock** (`lib/api.ts`, `lib/mock.ts`). LIVE: chat, `GET /sources`, `POST /ingest/run`. MOCK: toàn bộ profile/lịch/học phí sinh viên, mọi analytics/logs/unanswered của admin, và các mutation admin (disable/resolve/forward) là **no-op giả thành công**. Được gắn nhãn rõ, nhưng vận hành viên có thể tưởng đã thay đổi state.
- **Điểm mạnh UX:** state machine grounding, nhảy tới nguồn citation, pill tin cậy *chỉ* hiển thị cho câu trả lời grounded, trace "tại sao có câu trả lời này", refusal định tuyến tới kênh chính thức, **không dùng `dangerouslySetInnerHTML`** (markdown inline an toàn XSS). Script theme pre-paint (không FOUC), song ngữ EN/VI đầy đủ.
- **Rủi ro UX:** renderer markdown bằng regex (không có list/heading/code); hội thoại không lưu qua reload; từ điển song ngữ là hai object ~1000 dòng viết tay (rủi ro lệch nhau).

### Backend (endpoints, error handling, auth, bảo mật)

| Endpoint | Method | Auth | Ghi chú |
|---|---|---|---|
| `/health` | GET | không | lộ `app_env`/`app_name` |
| `/chat` | POST | **không** | `ChatRequest` có giới hạn (`message` 1–4000, `conversation_id` ≤128) |
| `/chat/stream` | POST | **không** | SSE verify-then-reveal |
| `/sources` | GET | **không** | re-chunk corpus mỗi lần gọi |
| `/ingest/run` | POST | **không** | **SSRF + ghi nặng + đồng bộ** |

- **Auth/authz:** *không có ở đâu cả*. Đã xác minh: không `CORSMiddleware`, `add_middleware`, `Depends`, `APIKeyHeader`, hay rate limiting trong backend. Các header `Authorization` duy nhất là *gửi ra ngoài* tới OpenRouter/OpenAI.
- **Lưu ý triển khai:** trong `docker-compose.yml` backend dùng `expose` (chỉ trong mạng Docker nội bộ), không `ports`, nên không *trực tiếp* truy cập từ Internet. **Nhưng** frontend Next.js công khai proxy `/api/ingest/run` và `/api/sources` thẳng qua mà không auth — nên bề mặt ingest/SSRF không auth *vẫn truy cập được từ Internet qua proxy*. CORS không cần (proxy same-origin), nhưng lỗ hổng auth là thật.
- **Error handling:** mọi lỗi chat đều dồn về **503** (kể cả `ValueError` do client gây ra); ingest chỉ bắt `RuntimeError` (exception khác → 500 + stack trace lộ ra). Không nhất quán.
- **Bí mật:** không hardcode secret (đều là `str | None` từ env) — tốt. Nhưng không có readiness check lúc khởi động: deploy thiếu key vẫn boot "healthy" và 503 ở mọi lượt chat.

### Chatbot (prompt, context, RAG, history, rủi ro hallucination/rò rỉ)
- **Prompt** (`prompts.py`) có vệ sinh tốt: nội dung người dùng + nội dung retrieve được khai báo không-tin-cậy-để-làm-lệnh; không bao giờ tiết lộ system prompt/bí mật; trích dẫn mọi claim quan trọng; từ chối dữ liệu riêng SIS/Canvas/email. `PROMPT_VERSION = "phase0-v1"` **đã cũ** so với hành vi Phase 1.7/1.8 đang chạy.
- **Bộ nhớ:** LangGraph checkpointer theo `conversation_id` (mặc định in-memory, tùy chọn Postgres). Ngắn hạn, theo từng hội thoại. Context checkpointer Postgres được `__enter__` nhưng không `__exit__` (`vinuni_agent.py:251`).
- **Chống hallucination:** temperature thấp (0.1), cổng có-citation, graceful degradation, kiểm tra faithfulness số/ngày. **Khoảng trống:** hallucination văn bản phi-số và giá trị bí mật bị lộ vẫn lọt cổng.
- **Rò rỉ:** dump toàn bộ `metadata.model_dump()` cho LLM; repr `filters` của client trong prompt; rerank/embedding gửi text corpus tới OpenRouter/Cohere (dự kiến, nhưng cần lưu ý quản trị dữ liệu); Langfuse PII scrub chỉ phủ email + số điện thoại VN (tên/mã sinh viên lọt vào trace).

### Đăng nhập/đăng xuất & role
Cơ chế thật = `localStorage` + `ProtectedRoute` phía client. Logout xóa storage. **Role do attacker kiểm soát được** (`localStorage.setItem(...role:"admin")` → vào full UI admin). Tác động thấp *hiện tại* (data admin là mock), nhưng cao ngay khi có endpoint admin thật. Dòng chú thích trên màn login "quyền truy cập dựa trên role và permission VinUni" là gây hiểu lầm.

---

## 8. Điểm mạnh / điểm yếu / nợ kỹ thuật / rủi ro

**Điểm mạnh**
- Pipeline retrieval tinh vi, gate hoàn toàn bằng config (hybrid → RRF → rerank-once → boost → dynamic-k → parent-section → LITM → injection-scan).
- Guardrail phân tầng fail-open kèm deobfuscation; lọc indirect-injection trên chunk retrieve.
- Streaming verify-then-reveal giữ được đảm bảo grounding.
- Observability chu đáo (request-id contextvar, counter rerank/point-lookup theo lượt, Langfuse có PII masking, ước tính chi phí).
- Tài liệu in-code trung thực, đầy đủ; dependency injection giúp agent test offline; 16 file test.
- UX chat hướng tin cậy (trạng thái grounding, citations, gating tin cậy, refusal routing).

**Điểm yếu / nợ kỹ thuật**
- Backend không auth/authz/rate-limit; SSRF trên ingest truy cập được qua proxy công khai.
- Auth giả lập phía client; cổng role chỉ trang trí.
- Guard chạy trùng; lỗ hổng fail-open của reranker; bug strip số trong `expand_query`; vi phạm min-k trong `_finalize`; re-chunk trong `GET /sources`.
- Thư mục chết `frontend_backup_20260618/`; `PROMPT_VERSION` cũ; hai từ điển i18n viết tay.
- Mutation admin là no-op giả; không có `error.tsx`/`not-found.tsx`; không test frontend.

**Rủi ro hàng đầu:** (1) ingest SSRF/DoS không auth qua proxy; (2) khuếch đại chi phí trên `/chat` mở; (3) giả mạo role khi có endpoint admin thật; (4) lệch embedding-model âm thầm phá retrieval nếu `OPENROUTER_EMBEDDING_MODEL` đổi sau khi đã index.

---

## 9. Cải tiến theo ưu tiên

### 🔴 Cao

| Vấn đề | Lý do | Cách sửa | File cần đổi |
|---|---|---|---|
| Không auth ở mọi endpoint; ingest truy cập được qua proxy công khai | Ai cũng có thể chạy crawler / đốt budget LLM | Thêm dependency shared-secret/API-key cho `/ingest/run` (+ route proxy admin); yêu cầu token session do Next proxy forward cho chat | `main.py`, `routes_ingest.py`, `next.config.js` |
| **SSRF** qua `IngestRunRequest.urls` | URL do caller cung cấp tới endpoint nội bộ/metadata | Validate scheme=`https` và host theo allow-list domain VinUni trước khi crawl | `schemas/chat.py:43`, `routes_ingest.py:31` |
| Role chỉ ép phía client | Bypass dễ dàng qua localStorage | Chuyển sang cookie httpOnly/JWT + `middleware.ts` gate server-side; thay `login()` bằng `POST /auth/login` | `lib/auth.tsx`, `ProtectedRoute.tsx`, file mới `frontend/middleware.ts` |
| `get_source_detail` bỏ qua injection scan | Nguồn nhiễm bypass phòng thủ injection từ dữ liệu | Cho chunk của nó đi qua `scan_for_injection` như `_search` | `tools.py:165` |
| Không rate limiting | Khuếch đại chi phí / DoS trên `/chat` | Thêm `slowapi` giới hạn theo IP (và giới hạn concurrency cho `/ingest/run`) | `main.py` |
| Không bảo vệ lệch embedding-model | Serving ≠ ingest model → retrieval rác, âm thầm | Lưu embedding model lúc ingest vào metadata collection; assert khớp lúc khởi động | `embeddings/openrouter_embeddings.py`, `rag/retriever.py` |

### 🟡 Trung bình

| Vấn đề | Lý do | Cách sửa | File cần đổi |
|---|---|---|---|
| Parse reranker ngoài try/except | Payload lỗi → 503 thay vì fail-soft | Đưa vòng parse vào trong khối guard; dùng chung 1 `httpx` client | `reranker.py:57` |
| `expand_query` strip số đầu dòng | Phá biến thể chứa năm/đã dịch | Thay `lstrip(charset)` bằng regex list-marker có neo | `query_engineering.py:109` |
| `_finalize` vi phạm min-k do gộp section | Ít chunk hơn cam kết tới LLM | Áp lại min-k sau `expand_to_parent_sections`, hoặc expand trước dynamic-k | `retriever.py:298`, `context.py` |
| `GET /sources` re-chunk corpus mỗi lần gọi | O(corpus) chặn trên event loop | Lưu `chunk_count` lúc ingest; đọc lại | `routes_ingest.py:83` |
| Guardrail chạy trùng | 2× độ trễ/chi phí guard mỗi lượt HTTP | Truyền decision từ `_resolve_chat` vào `chat()` | `routes_chat.py:37`, `vinuni_agent.py:57` |
| Faithfulness chỉ kiểm số/ngày | Hallucination văn bản lọt qua | Thêm LLM-judge hoặc NLI cấp claim cho claim phi-số | `guardrails.py:506` |
| Không timeout/retry cho LLM client | Cuộc gọi OpenRouter treo làm nghẽn request | Đặt `request_timeout` + `max_retries` cho `ChatOpenAI` | `llm/openrouter_chat.py` |
| Mutation admin là no-op giả | Vận hành viên tưởng đã đổi state | Nối endpoint thật hoặc gắn nhãn rõ là demo | `lib/api.ts` |

### 🟢 Thấp

| Vấn đề | Cách sửa | File |
|---|---|---|
| Side effect trong updater `setMessages` | Tính text trước, gọi `ask` sau khi update state | `app/student/chat/page.tsx:217` |
| Dump toàn bộ `metadata.model_dump()` cho LLM/citations | Whitelist trường citation | `tools.py:117` |
| `PROMPT_VERSION` cũ, thư mục chết `frontend_backup_20260618/` | Bump version khi đổi prompt; xóa thư mục backup | `prompts.py:9`, root repo |
| Không `error.tsx`/`not-found.tsx`/route boundary | Thêm vào | `frontend/app/` |
| Lỗi chat dồn về 503 | Map lỗi client sang 4xx | `routes_chat.py:58` |
| Langfuse PII scrub hẹp | Thêm pattern tên/mã sinh viên | `observability.py:127` |

---

## 10. Hướng dẫn onboarding

### Giải thích dễ hiểu: hệ thống hoạt động thế nào
Hãy hình dung nó như một thủ thư chỉ trả lời dựa trên tài liệu chính thức của VinUni. Offline, một crawler tải các trang VinUni, cắt thành đoạn nhỏ, và lưu vào kho tìm kiếm (Qdrant). Khi bạn hỏi: một bảo vệ kiểm tra câu hỏi an toàn và đúng chủ đề (guards); một điều phối viên quyết định câu hỏi về lịch, chính sách, học phí hay dịch vụ (supervisor); specialist phù hợp tra các đoạn liên quan (retrieval), viết câu trả lời **trích dẫn các đoạn đó**, và một bộ kiểm tra cuối đảm bảo câu trả lời thực sự được hậu thuẫn bởi những gì tìm thấy trước khi hiện ra. Website chỉ là ô chat nói chuyện với động cơ này và hiển thị nguồn.

### Bắt đầu đọc code từ đâu (theo thứ tự)
1. `ARCHITECTURE.md` — mô hình tư duy (sơ đồ Mermaid).
2. `routes_chat.py` — cổng HTTP; nhỏ, dễ đọc.
3. `vinuni_agent.py` — điều phối lượt chat.
4. `graph.py` → `specialists.py` → `tools.py` — agent.
5. `retriever.py` `_finalize` — động cơ chất lượng RAG.
6. Frontend: `lib/api.ts` → `app/student/chat/page.tsx` → `responseState.ts`.

### Sửa gì ở đâu
| Để thay đổi… | Sửa file… |
|---|---|
| UI chat / bubble / panel nguồn | `components/MessageBubble.tsx`, `components/SourcesPanel.tsx`, `components/Composer.tsx` |
| Hành vi/giọng điệu/quy tắc chatbot | `agents/prompts.py` |
| Intent định tuyến / thêm specialist | `agents/supervisor.py`, `agents/specialists.py` |
| Chất lượng retrieval / tinh chỉnh | `rag/retriever.py`, `rag/context.py`, các flag trong `core/config.py` |
| Quy tắc safety/guard | `agents/guardrails.py` |
| Đăng nhập / session | `lib/auth.tsx` (+ route backend `/auth` mới) |
| Role / kiểm soát truy cập | `components/auth/ProtectedRoute.tsx` + file mới `frontend/middleware.ts` |

### Checklist debug
- **Mọi lượt chat đều 503?** Thiếu `OPENROUTER_API_KEY` hoặc collection Qdrant chưa tồn tại (chạy ingest). `/health` lên nhưng chat fail → hầu như luôn do thiếu key hoặc collection Qdrant rỗng/lệch.
- **Câu trả lời rỗng/lạc đề?** Xác nhận embedding model khớp model lúc ingest; kiểm tra rerank không fail-open (logs); xem `tool_trace` trong response.
- **Sai specialist?** Log `intent` trong `graph.py`; soft-routing khiến định tuyến sai vẫn degrade nhẹ nhàng, nên kiểm tra cả boost hint.
- **Frontend không tới được backend?** Kiểm tra `BACKEND_URL` và rewrites trong `next.config.js`; browser gọi `/api/*` (same-origin), không phải `:8000` trực tiếp.
- **"Couldn't ground" quá thường xuyên?** Xem `assess_faithfulness` (chỉ số/ngày) và cổng có-citation; kiểm tra retrieval có trả về chunk không.
- **Dùng Langfuse traces** để xem token/chi phí mỗi lượt và toàn bộ vòng lặp tool.

### Lộ trình cải tiến 1–2 tuần
**Tuần 1 — bảo mật & tính đúng đắn (bắt buộc trước khi mở ra ngoài)**
1. Thêm dependency API-key/shared-secret cho `/ingest/run` + allow-list domain chống SSRF (½ ngày).
2. Thêm rate limiting `slowapi` + khóa concurrency ingest (½ ngày).
3. Auth thật: backend `POST /auth/login` phát JWT qua cookie httpOnly + `middleware.ts` gate role server-side (2 ngày).
4. Sửa ba bug thật: parse reranker đưa vào try, strip số trong `expand_query`, min-k trong `_finalize` (1 ngày).
5. Cho `get_source_detail` đi qua injection scan; whitelist metadata citation (½ ngày).
6. Readiness check key bắt buộc + kiểm tra khớp embedding model lúc khởi động (½ ngày).

**Tuần 2 — chất lượng, chi phí & hoàn thiện**
1. Khử trùng lặp guardrail; thêm timeout/retry cho LLM client (½ ngày).
2. Lưu `chunk_count`; ngừng re-chunk trong `GET /sources` (½ ngày).
3. Thêm kiểm tra faithfulness/claim phi-số (1 ngày).
4. Frontend: sửa side-effect `setMessages`; thêm `error.tsx`/`not-found.tsx`; xóa `frontend_backup_20260618/`; bump `PROMPT_VERSION` (1 ngày).
5. Nối (hoặc gắn nhãn rõ) mutation admin; thêm test parity key i18n (1 ngày).
6. Chạy `scripts/run_eval.py` trên golden set trước/sau để xác nhận không regression retrieval (½ ngày).
