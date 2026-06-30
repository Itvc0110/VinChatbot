# VinChatbot - Sản Phẩm Bàn Giao

> Ngày cập nhật: 2026-06-28  
> Phạm vi: Bộ tài liệu bàn giao end-to-end cho repository VinChatbot hiện tại.  
> Sản phẩm: VinUni student copilot với RAG chat, cổng Student/Admin, app database, dữ liệu demo và tài liệu triển khai.

---

## 0. Deliverables Cần Có Theo Yêu Cầu

Phần này bám đúng checklist nộp bài trong yêu cầu: production URL, evaluation metrics có baseline number, guardrails, demo video draft và cost report tùy chọn.

| # | Deliverable bắt buộc | Trạng thái hiện tại | Bằng chứng / việc cần làm |
| --- | --- | --- | --- |
| 1 | Deployed production URL | Cần điền sau khi deploy | Repo đã có `docker-compose.yml`, `Caddyfile`, `Dockerfile`, `frontend/Dockerfile`, `docs/DEPLOY.md`. Sau khi deploy, điền URL production vào mục `Production URL` bên dưới. |
| 2 | Evaluation Metrics với nhiều hơn 1 metric và baseline number | Có baseline trong repo | `data/eval/baseline.json` có 199 eval cases, pass rate, facts, citation, latency, cost, model calls và confidently-wrong rate. |
| 3 | Guardrails | Có implementation và tests | Input/output guardrails nằm trong `vinchatbot/app/agents/guardrails.py`, `safety_guard.py`, `question_scope.py`; tests liên quan trong `tests/test_guardrails.py`, `tests/test_guard_scope.py`, `tests/test_safety_guard.py`, `tests/test_guard_obfuscation.py`. |
| 4 | Demo video draft 3-5 phút, gồm slides pitch + live demo | Cần quay video theo script | Repo có presentation files trong `presen/`; dùng demo script ở mục `0.4` để quay video. |
| 5 | Optional cost report: ước tính cost/user/month theo usage | Có thể nộp | Baseline eval có estimated cost per turn; mục `0.5` bên dưới tính cost/user/month theo nhiều mức usage. |

### 0.1 Production URL

Production URL:

```text
https://c2-app-050.indevs.in
```


- `docs/DEPLOY.md`: hướng dẫn deploy lên VPS Ubuntu.
- `docker-compose.yml`: chạy backend, frontend và Caddy.
- `Caddyfile`: reverse proxy + auto HTTPS.
- `Dockerfile`: backend FastAPI.
- `frontend/Dockerfile`: frontend Next.js.

Checklist trước khi điền URL:

- DNS đã trỏ về server.
- `.env` production đã cấu hình ngoài git.
- `docker compose up -d --build` chạy thành công.
- Frontend mở được qua HTTPS.
- `GET /health` và `GET /health/db` trả trạng thái OK.
- Demo login hoạt động với ít nhất một tài khoản student và một tài khoản admin.

### 0.2 Evaluation Metrics Baseline

Nguồn baseline hiện tại: `data/eval/baseline.json`.

| Metric | Baseline number | Ý nghĩa |
| --- | ---: | --- |
| Eval cases | 199 | Tổng số test cases trong golden eval baseline. |
| Overall pass rate | 0.980 | Tỷ lệ cases pass toàn bộ điều kiện. |
| Facts OK | 0.985 | Tỷ lệ câu trả lời chứa đúng facts bắt buộc và tránh facts bị cấm. |
| Citation OK | 0.990 | Tỷ lệ câu trả lời có citation hợp lệ khi cần. |
| Confidently wrong | 2 cases | Số câu trả lời sai nhưng vẫn trả lời có vẻ chắc chắn. |
| Confidently wrong rate | 0.013 | Tỷ lệ confidently-wrong trên answerable cases. |
| Mean latency | 11,121.9 ms | Thời gian trung bình mỗi turn trong eval baseline. |
| P95 latency | 25,911.0 ms | Latency p95 trong eval baseline. |
| Total estimated LLM cost | 0.46337 USD | Tổng estimated cost cho 199 eval turns. |
| Mean estimated cost / turn | 0.00232849 USD | Estimated LLM cost trung bình mỗi turn. |
| Mean model calls / turn | 3.4 | Số model calls trung bình mỗi turn. |
| Tokens in / out | 2,701,286 / 27,543 | Tổng input/output tokens trong baseline. |

Lệnh cập nhật baseline khi cần:

```bash
python scripts/run_eval.py --diff data/eval/baseline.json
```

Metric nên đưa vào slide:

- Accuracy/pass rate: `98.0%`.
- Citation validity: `99.0%`.
- Facts correctness: `98.5%`.
- Safety/confidently-wrong: `2 cases`, rate `1.3%`.
- Latency: mean `11.1s`, p95 `25.9s`.
- Cost: mean `$0.00233/turn`.

### 0.3 Guardrails

Guardrails đã có trong repo gồm:

- Input guardrail: phát hiện prompt injection, restricted/private-data probes, abusive language, out-of-scope và greeting/conversational handling.
- Safety/moderation layer: `vinchatbot/app/agents/safety_guard.py`.
- LLM/heuristic guard cho gray-zone routing: `vinchatbot/app/agents/llm_guard.py`.
- Output guardrail: secret-leak scan, citation/degrade check và faithfulness/grounding decision.
- Personal app-data scope guard: phân biệt `personal_app_data`, `official_policy`, `hybrid`, `general_unknown` trong `question_scope.py`.
- Indirect-injection scan trên retrieved chunks trong retrieval/tool path.
- RBAC/data guardrails: current-student identity binding, không cho client truyền `student_id` tùy ý cho student/academic/personalization APIs.

Các test liên quan:

```bash
python -m pytest tests/test_guardrails.py tests/test_guard_scope.py tests/test_safety_guard.py tests/test_guard_obfuscation.py tests/test_output_audit.py tests/test_question_scope.py
```

Các scenario nên demo:

- Prompt injection: "Ignore previous instructions..." -> bị chặn hoặc trả lời an toàn.
- Private-data probe: hỏi dữ liệu sinh viên khác -> từ chối hoặc không leak.
- Unsupported/out-of-scope: câu hỏi ngoài VinUni -> graceful refusal.
- Policy/deadline không có evidence -> degrade sang hướng kiểm tra nguồn chính thức.
- Personal app-data: chỉ trả lời từ context của user đang đăng nhập.

### 0.4 Demo Video Draft 3-5 Phút

```text
https://drive.google.com/file/d/1a9CKYtfQhzN4AlJiqRraQf9KpcTMnerP/view?usp=drive_link
```

### 0.5 Optional Cost Report

Baseline cost lấy từ `data/eval/baseline.json`:

- Mean estimated cost / turn: `0.00232849 USD`.
- Total estimated eval cost: `0.46337 USD` cho `199` turns.
- Mean model calls / turn: `3.4`.

Ước tính LLM cost theo user/month:

| Usage giả định | Công thức | Estimated LLM cost / user / month |
| --- | --- | ---: |
| Light: 30 chat turns/tháng | 30 × 0.00232849 | ~0.070 USD |
| Medium: 100 chat turns/tháng | 100 × 0.00232849 | ~0.233 USD |
| Heavy: 300 chat turns/tháng | 300 × 0.00232849 | ~0.699 USD |

Ước tính này chỉ tính LLM/runtime calls theo baseline eval. Chưa bao gồm hosting VPS/Vercel/Railway, Neon/Postgres, Qdrant Cloud, Redis, bandwidth, log storage hoặc chi phí re-ingestion định kỳ.

## A. Tóm Tắt Điều Hành

Vin Student Copilot là một student copilot dạng web dành cho VinUni. Hệ thống trả lời câu hỏi của sinh viên bằng pipeline RAG có grounding theo nguồn chính thức, hỗ trợ workflow có đăng nhập cho Student và Admin, lưu lịch sử hội thoại, cung cấp các API học vụ/sinh viên/ticket/forum/thông báo, và có giao diện Next.js phục vụ demo.

Tài liệu này là checklist bàn giao chính: mô tả repo đang bàn giao được gì, bằng chứng nằm ở đâu, cách nghiệm thu như thế nào, và phần nào vẫn nằm ngoài phạm vi.

## B. Phạm Vi Sản Phẩm

### Phạm Vi Đã Bàn Giao

- Chatbot Q&A công khai cho VinUni với retrieval, citation, guardrails và multi-agent routing.
- Cổng Student/Admin có đăng nhập.
- Xác thực theo session và phân quyền RBAC.
- Student dashboard, hồ sơ học tập, lịch học, thông báo, gợi ý câu hỏi, ticket hỗ trợ, forum và lịch sử chat.
- Admin dashboard, ticket console, knowledge-source view, notification workflow và các trang admin liên quan.
- Postgres app schema, migrations, demo seed data và script tiện ích database.
- Pipeline RAG gồm ingestion, crawling, indexing, structured lookup, eval harness và nền tảng observability.
- Tài liệu triển khai Docker/Caddy.

### Không Thuộc Phạm Vi Hiện Tại

- Tích hợp VinUni SIS/Canvas/SSO thật.
- Dữ liệu sinh viên production thật.
- Gửi email/push notification thật.
- Thanh toán, đăng ký môn, nộp form hoặc thực hiện hành động thay sinh viên.
- Bộ monitoring production đầy đủ như Prometheus/Grafana alerts.
- Phê duyệt pháp lý/compliance cho production.

## C. Ma Trận Deliverables

| ID | Sản phẩm bàn giao | Bằng chứng trong repo | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| D01 | Yêu cầu sản phẩm và roadmap | `docs/PRD.md`, `docs/UPDATE_PLAN.md`, `docs/BRIEF.md` | Scope, goals, non-goals, users và roadmap đã được tài liệu hóa. |
| D02 | Kiến trúc hệ thống | `docs/ARCHITECTURE.md`, `README.md` | Có mô tả ingest flow, online chat flow, RAG layers, guardrails và agent routing. |
| D03 | Backend API service | `vinchatbot/app/main.py`, `vinchatbot/app/api/*` | FastAPI app khởi động và đăng ký các router chat, auth, student, academic, ticket, forum, notification, conversation, ingest và health. |
| D04 | RAG chatbot core | `vinchatbot/app/agents/*`, `vinchatbot/app/rag/*`, `vinchatbot/app/storage/*` | Chat route được câu hỏi, retrieve context chính thức, sinh câu trả lời grounded và trả về citations/tool traces. |
| D05 | Ingestion pipeline | `scripts/crawl_seed.py`, `scripts/ingest_documents.py`, `scripts/build_structured_index.py`, `vinchatbot/app/ingest/*` | Có thể crawl nguồn chính thức, sinh processed artifacts và index dữ liệu. |
| D06 | App database schema | `migrations/000001_*.sql` đến `migrations/000009_*.sql` | Migrations tạo các bảng auth, student, academic, conversation, ticket, notification, forum và suggestion. |
| D07 | Demo seed data | `scripts/seed_demo_data.py`, `docs/database/phase-5a-demo-academic-seed.md`, `docs/database/phase-5b-demo-activity-seed.md` | Có thể seed idempotent tài khoản demo student/admin và dữ liệu hoạt động giả lập. |
| D08 | Auth và RBAC | `vinchatbot/app/api/routes_auth.py`, `vinchatbot/app/dependencies/auth.py`, `vinchatbot/app/security/*` | Có login, current-user lookup, logout, session hashing và role guards. |
| D09 | Student APIs | `routes_students.py`, `routes_academic.py`, `routes_personalization.py` | Hồ sơ, môn học, lịch, deadline, thông báo, gợi ý, academic overview/transcript/curriculum/eligibility và personalization context đều scope theo sinh viên đang đăng nhập. |
| D10 | Chat persistence | `routes_chat.py`, `routes_conversations.py`, `repositories/conversations.py` | Chat có đăng nhập có thể lưu user/assistant messages và trả về `db_conversation_id`. |
| D11 | Ticket workflow | `routes_tickets.py`, `repositories/tickets.py`, `frontend/components/tickets/*` | Sinh viên tạo/trả lời ticket; admin list, update và reply theo role scope. |
| D12 | Notification workflow | `routes_admin_notifications.py`, `repositories/admin_notifications.py`, `frontend/components/notifications/*` | Admin tạo/cập nhật/publish/schedule/archive thông báo; sinh viên đọc notification feed và read state. |
| D13 | Forum workflow | `routes_forum.py`, `repositories/forum.py`, `frontend/components/forum/*` | Có forum read/write, vote, owner edit/delete và moderation cơ bản cho người dùng đã đăng nhập. |
| D14 | Frontend portal | `frontend/app/*`, `frontend/components/*`, `frontend/lib/*` | Next.js app có login, student pages, admin pages, API client, auth provider, shells và typed UI helpers. |
| D15 | Design system và route map | `docs/DESIGN.md`, `docs/ROUTES.md`, `frontend/app/*.css` | Academic Horizon styling và mapping screen-to-route đã được tài liệu hóa. |
| D16 | Evaluation và tests | `tests/*`, `scripts/run_eval.py`, `scripts/eval_rag.py`, `data/eval/*` | Có unit/API/RAG guard tests và golden eval datasets. |
| D17 | Deployment package | `Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `Caddyfile`, `docs/DEPLOY.md` | Backend, frontend và Caddy có thể deploy bằng Docker Compose với Qdrant ngoài và biến môi trường phù hợp. |
| D18 | Tài liệu vận hành | `README.md`, `docs/DEPLOY.md`, `docs/database/*`, `docs/LOGS/*` | Setup, migration, seed, deployment và phase logs đã được ghi lại. |

## D. Deliverables Chức Năng

### Chat Và RAG

- `POST /chat` trả về câu trả lời cuối đã qua kiểm tra an toàn.
- `POST /chat/stream` dùng SSE events: `status`, `delta`, `done`, `error`.
- Câu trả lời về policy/deadline/fee dùng retrieval từ nguồn chính thức.
- Câu trả lời về dữ liệu cá nhân trong app có thể dùng server-owned student context khi có.
- Guardrails xử lý prompt injection, restricted/private-data probes, abusive content, out-of-scope, secret leakage, yêu cầu citation và grounding checks.

### Student Portal

- Login và role-based route protection.
- Student dashboard hiển thị profile, academic progress, schedule/deadline data, suggestions và entry point vào Vinnie.
- Student chat có streaming, citations, follow-up suggestions, conversation history và entry point report/ticket escalation.
- Student schedule/calendar hiển thị academic meetings theo tháng.
- Student academic page hiển thị transcript, curriculum progress và eligibility.
- Student notifications, tickets, forum, support, tuition placeholder và events pages.

### Admin Portal

- Admin dashboard với aggregate data.
- Admin tickets có filters, detail, status update và reply.
- Admin notifications có create/edit/publish/schedule/archive.
- Knowledge-source/admin upload pages kết nối với ingest/source APIs ở những phần backend đã hỗ trợ.
- Admin analytics/settings/log/context/events pages đã có mặt, trong đó một số hành vi vẫn là demo hoặc partial theo phase notes.

## E. Backend API Deliverables

Các nhóm route chính hiện được đăng ký bởi `vinchatbot/app/main.py`:

- System: `GET /health`, `GET /health/db`
- Auth: `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
- Chat: `POST /chat`, `POST /chat/stream`
- Conversations: `GET/POST /conversations`, `GET/PATCH/DELETE /conversations/{id}`, `GET /conversations/{id}/messages`
- Students: `GET /students/me`, `/courses`, `/schedule`, `/deadlines`, `/notifications`, notification read/unread endpoints, `GET /suggestions/me`
- Academic: `GET /academic/me`, `/transcript`, `/curriculum`, `/courses/eligible`, `GET /schedule/me?month=YYYY-MM`
- Personalization: `GET /personalization/me/context`
- Tickets: student `/tickets*`, admin `/admin/tickets*`
- Notifications: admin `/admin/notifications*`
- Forum: `/forum/categories`, `/forum/topics*`, `/forum/comments*`, vote/report/moderation endpoints
- Ingest/source: `/ingest/run`, `/ingest/upload`, `/ingest/preview`, `/sources`

## F. Frontend Deliverables

### Student Routes

- `/login`
- `/student/dashboard`
- `/student/chat`
- `/student/schedule`
- `/student/events`
- `/student/academic`
- `/student/support`
- `/student/forum`
- `/student/forum/topics/[id]`
- `/student/notifications`
- `/student/tuition`

### Admin Routes

- `/admin/dashboard`
- `/admin/tickets`
- `/admin/sources`
- `/admin/upload`
- `/admin/unanswered`
- `/admin/notifications`
- `/admin/analytics`
- `/admin/context`
- `/admin/events`
- `/admin/settings`
- `/admin/logs`

### Hạng Mục Kỹ Thuật Frontend

- Next.js 14 App Router.
- Auth provider và bearer-token API helper.
- Next rewrites từ `/api/*` sang FastAPI.
- Student và admin role shells.
- Typed API functions trong `frontend/lib/api.ts`.
- UI components cho chat, tickets, notifications, forum, calendar, auth và shells.

## G. Database Deliverables

### Phạm Vi Migration

- Bảng tracking schema migrations.
- Initial app schema: users, roles, sessions, students, schedules, notifications, conversations, tickets, suggestions, audit logs.
- Base reference seed: roles và institutes.
- Forum schema và demo forum seed.
- Admin notification workflow.
- Academic demo core và schedule density.
- Bilingual notifications và suggestions.

### Phạm Vi Seed Data

- 50 demo student users.
- Demo admin/staff users.
- Student profiles, academic summaries, courses, enrollments, schedules và deadlines.
- Notifications, conversations, tickets, trends, suggestions, events.
- Academic catalog, curriculum, requisites, transcript examples, sections, rooms, meetings.

### Demo Accounts

Tài khoản student ví dụ:

- `student.business.demo@vinuni.edu.vn`
- `student.cs.demo@vinuni.edu.vn`
- `student.health.demo@vinuni.edu.vn`
- `student.liberal.demo@vinuni.edu.vn`

Tài khoản admin ví dụ:

- `admin.global.demo@vinuni.edu.vn`
- `admin.business.demo@vinuni.edu.vn`
- `admin.cecs.demo@vinuni.edu.vn`
- `admin.health.demo@vinuni.edu.vn`
- `admin.liberal.demo@vinuni.edu.vn`

Mật khẩu development:

```text
Demo@123456
```

Mật khẩu này chỉ dùng cho local/dev demo.

## H. AI/RAG Deliverables

- Domain-aware crawler cho nguồn public của VinUni.
- Hỗ trợ parse HTML/PDF/DOCX/CSV/XLSX, với OCR/table extras tùy chọn.
- Structured records cho calendar events, fee records, policy listings, tables, image assets và file assets.
- Qdrant hybrid dense+sparse retrieval.
- Structured lookup cho calendar/fee point lookups.
- Policy doc-pin và cross-lingual policy escalation.
- Multi-query/RRF retrieval, rerank-once, metadata boosts, dynamic-k, full-section expansion, lost-in-the-middle reorder.
- Multi-agent supervisor với các specialist calendar, policy, financial và services.
- Fan-out dispatch cho câu hỏi multi-domain.
- Redis-backed exact-match LLM/rerank cache khi bật.
- Eval datasets và scripts để theo dõi regression.

## I. Security Và Privacy Deliverables

- Opaque bearer sessions; database chỉ lưu token hash.
- Password verification qua PBKDF2-SHA256 helper.
- RBAC dependencies cho `student`, `global_admin`, `institute_admin` và `staff`.
- Current-student identity binding cho student/academic/personalization APIs.
- Truy cập cross-user/cross-institute trả `404` ở các chỗ phù hợp để tránh lộ sự tồn tại của dữ liệu.
- Server-owned personalization context; frontend không còn gửi hidden personal context block.
- Nền tảng logging/observability có cân nhắc PII.
- Output guard chống secret leak.

## J. Configuration Deliverables

Runtime configuration được điều khiển bằng biến môi trường. Các nhóm chính:

- OpenRouter: quyền truy cập chat, embedding và rerank model.
- Qdrant: vector store URL/API key/collection.
- App database: pooled và direct Postgres URLs.
- Redis: hỗ trợ cache và rate-limit tùy chọn.
- Deployment: `DOMAIN`, `TLS_EMAIL`, service URLs.
- Feature flags: các toggle `ENABLE_*` cho RAG, caching, fan-out, OCR, structured lookup và hành vi liên quan.

`.env` không phải artifact bàn giao trong git và tuyệt đối không được commit.

## K. Deployment Deliverables

Mô hình production Docker/Caddy:

```text
Caddy auto-HTTPS -> Next.js frontend -> FastAPI backend -> Neon/Postgres + Qdrant Cloud + OpenRouter
```

Các file chính:

- `Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`
- `Caddyfile`
- `docs/DEPLOY.md`

Tiêu chí nghiệm thu deployment:

- DNS trỏ về VPS.
- `.env` tồn tại trên server.
- `docker compose up -d --build` chạy thành công.
- `https://DOMAIN` tải được frontend.
- Backend health trả OK.
- Demo login hoạt động.

## L. Lệnh Kiểm Tra

Backend:

```bash
python -m pytest
python -m ruff check .
python scripts/db_status.py
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

Database:

```bash
python scripts/db_migrate.py
python scripts/seed_demo_data.py --section all --yes
```

Docker:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

RAG/eval:

```bash
python scripts/run_eval.py
python scripts/eval_rag.py
```

## M. Checklist Nghiệm Thu

### Nghiệm Thu Student

- Student có thể đăng nhập bằng tài khoản demo.
- Student thấy đúng profile/dashboard data của mình.
- Student mở chat, hỏi câu hỏi, nhận câu trả lời và thấy citations khi bắt buộc.
- Lịch sử chat của student được lưu và mở lại được.
- Student xem được schedule, academic record, notifications, suggestions, forum topics và tickets.
- Student không truy cập được admin pages.
- Student không đọc được dữ liệu của student khác qua URL, prompt hoặc ID.

### Nghiệm Thu Admin

- Admin có thể đăng nhập bằng tài khoản demo.
- Admin truy cập được dashboard và ticket console.
- Admin list và update được scoped tickets.
- Admin tạo/publish/schedule/archive được notifications.
- Admin xem được knowledge sources và chạy các ingest flows đã hỗ trợ.
- Admin-only APIs từ chối anonymous/student users.

### Nghiệm Thu AI

- Câu trả lời về policy/deadline/fee có grounding từ nguồn chính thức và citations.
- Câu trả lời về personal app-data chỉ dùng authenticated server-owned context.
- Câu hỏi out-of-scope, private-data, prompt-injection và unsupported được degrade/refuse an toàn.
- Eval và safety tests vẫn xanh.

## N. Gói Bàn Giao

Gói bàn giao nên bao gồm:

- Source code của repository.
- Tài liệu deliverables này.
- `README.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/ROUTES.md`, `docs/DEPLOY.md`.
- Database phase documents trong `docs/database/`.
- Frontend integration phase documents trong `docs/frontend/`.
- Migration files trong `migrations/`.
- Test suite trong `tests/`.
- Eval data trong `data/eval/`.
- File presentation demo trong `presen/`, nếu cần cho course/demo.

Secrets bị loại khỏi gói bàn giao và phải được chuyển qua kênh bảo mật riêng.

## O. Runbook Vận Hành

### Local Development

1. Tạo và activate Python virtual environment.
2. Cài backend dependencies: `python -m pip install -e ".[dev]"`.
3. Cài frontend dependencies: `cd frontend && npm install`.
4. Cấu hình `.env`.
5. Apply migrations và seed demo data.
6. Start backend và frontend.

### Tác Vụ Vận Hành Thường Gặp

- Kiểm tra backend health: `GET /health`, `GET /health/db`.
- Chạy lại migrations: `python scripts/db_migrate.py`.
- Reset dev database: `python scripts/db_reset.py --yes`.
- Seed demo data: `python scripts/seed_demo_data.py --section all --yes`.
- Crawl/ingest nguồn public: `python scripts/crawl_seed.py`, sau đó `python scripts/ingest_documents.py`.
- Kiểm tra database status: `python scripts/db_status.py`.

## P. Quality Gates

Một thay đổi được xem là sẵn sàng bàn giao khi:

- Backend tests pass.
- Ruff pass.
- Frontend typecheck pass.
- Frontend build pass đối với thay đổi ảnh hưởng UI.
- Database migrations idempotent và có tài liệu.
- Auth/RBAC tests pass cho protected APIs.
- Thay đổi Chat/RAG không làm regression eval/safety targets.
- Không commit secrets.

## Q. Traceability

| Nhóm yêu cầu | Bằng chứng chính |
| --- | --- |
| Product vision | `docs/PRD.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Routes/screens | `docs/ROUTES.md` |
| Design | `docs/DESIGN.md` |
| Backend API | `vinchatbot/app/api/*` |
| Database | `migrations/*`, `docs/database/*` |
| Frontend | `frontend/app/*`, `frontend/components/*`, `frontend/lib/api.ts` |
| Tests | `tests/*` |
| Deployment | `docker-compose.yml`, `docs/DEPLOY.md` |

## R. Hạn Chế Đã Biết

- Dữ liệu học vụ demo là dữ liệu giả lập, không phải dữ liệu VinUni chính thức.
- Một số admin pages mang tính presentation/demo trừ khi phase document nói rõ đã nối backend contract.
- Student tuition vẫn là placeholder một phần nếu chưa thêm dedicated tuition endpoint.
- Chưa có SSO/SIS/Canvas thật.
- Chưa có email/push notification delivery.
- Caddy deployment giả định đã có VPS/domain setup và Qdrant Cloud bên ngoài.
- Live RAG/chat cần OpenRouter quota hợp lệ.
- Full production observability và incident response chưa hoàn chỉnh.

## S. Rủi Ro

| Rủi ro | Tác động | Giảm thiểu |
| --- | --- | --- |
| OpenRouter key hết quota | Chat trả unavailable responses. | Theo dõi quota, cấu hình fallback/provider budget, giữ health checks rõ ràng. |
| Qdrant collection mismatch | Retrieval fail hoặc trả dữ liệu cũ. | Pin collection names, re-ingest sau khi đổi embedding model. |
| Demo data bị hiểu nhầm là official data | Diễn giải sai thông tin học vụ. | Gắn nhãn demo data rõ trong UI/docs. |
| Secrets rò rỉ qua `.env` | Sự cố bảo mật. | Giữ `.env` trong gitignore, rotate keys, không paste credentials vào docs. |
| Frontend/backend contract drift | Trang lỗi hoặc empty states sai. | Cập nhật typed API helpers và backend schema tests cùng lúc. |
| Eval noise che mất regression | Tưởng RAG ổn trong khi chất lượng giảm. | Dùng multi-run eval và category-level diff reports cho thay đổi RAG lớn. |

## T. Quản Lý Thay Đổi

Cho các update sau này:

- Thêm phase document trong `docs/`, `docs/database/` hoặc `docs/frontend/`.
- Thêm hoặc update migration mới thay vì sửa migration đã apply.
- Update tests với mọi thay đổi API/schema behavior.
- Update `docs/ROUTES.md` khi đổi route/screen.
- Update tài liệu này khi một deliverable chuyển từ partial sang complete.

## U. Stakeholders

- Student user: dùng chat, dashboard, schedule, tickets, forum, notifications và academic record.
- Admin/staff user: quản lý tickets, notifications, sources, monitoring/review workflows.
- Engineering owner: bảo trì backend, frontend, database, RAG, tests và deployment.
- Demo/evaluator: xác minh hành vi end-to-end qua demo accounts và acceptance checklist.

## V. Definition Of Done

Dự án được xem là demo-ready khi:

- Demo accounts đăng nhập được.
- Các luồng chính của Student và Admin hoạt động qua browser.
- Chat trả lời grounded/cited hoặc từ chối an toàn.
- App database migrations và seeds chạy thành công.
- Backend và frontend verification commands pass.
- Deployment docs có thể được làm theo trên VPS sạch với secrets bắt buộc.
- Limitations và non-scope items được công bố rõ.

## W. Demo Script Gợi Ý

1. Đăng nhập bằng `student.cs.demo@vinuni.edu.vn`.
2. Mở dashboard và trình bày academic progress, upcoming schedule và suggestions.
3. Mở Vinnie AI và hỏi một câu policy/deadline.
4. Hỏi một câu personal app-data như deadline sắp tới hoặc thông báo quan trọng.
5. Mở chat history và cho thấy conversation đã được lưu.
6. Tạo hoặc review support ticket ở phía student.
7. Mở forum và trình bày topic/comment workflow.
8. Đăng xuất và đăng nhập bằng `admin.global.demo@vinuni.edu.vn`.
9. Trình bày admin dashboard, tickets, notifications và knowledge/source page.
10. Kết thúc bằng deployment/architecture slide hoặc `docs/ARCHITECTURE.md`.

## X. Khoảng Trống Trước Production

Trước khi dùng production thật:

- Thay demo data bằng nguồn dữ liệu production đã được duyệt.
- Tích hợp SSO/SIS/Canvas thật nếu cần.
- Hoàn tất review data retention, privacy và compliance.
- Thêm production-grade monitoring/alerts.
- Thêm quy trình backup/restore và disaster recovery.
- Harden rate limits và abuse monitoring dưới real traffic.
- Validate toàn bộ RAG answers với official-source corpus đã duyệt.
- Chạy security review cho auth/session/RBAC và prompt-injection risks.

## Y. Mẫu Sign-Off

| Khu vực | Owner | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Product scope |  |  |  |
| Backend API |  |  |  |
| Frontend UI |  |  |  |
| Database/migrations |  |  |  |
| RAG/eval |  |  |  |
| Security/privacy |  |  |  |
| Deployment |  |  |  |
| Demo readiness |  |  |  |

## Z. Checklist Bàn Giao Cuối

- [ ] `.env` được cấu hình ngoài git.
- [ ] Migrations đã apply.
- [ ] Demo data đã seed.
- [ ] Backend tests pass.
- [ ] Frontend typecheck/build pass.
- [ ] Docker deployment đã smoke-test.
- [ ] Demo accounts đã verify.
- [ ] RAG/OpenRouter/Qdrant dependencies healthy.
- [ ] Known limitations đã được truyền đạt.
- [ ] Final handover owner đã accept package.
