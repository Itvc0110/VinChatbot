# Deploy VinChatbot lên VPS Ubuntu (Docker + Caddy + auto-deploy)

Kiến trúc: **Caddy** (auto-HTTPS) → **frontend** (Next.js) → **backend** (FastAPI).
**Qdrant** dùng Qdrant Cloud (không container hóa). Auto-deploy bằng **GitHub Actions SSH**:
mỗi lần push lên nhánh `dholmes`, Actions SSH vào VPS, `git reset --hard origin/dholmes`
rồi `docker compose up -d --build`.

> Lưu ý quan trọng: backend cần `OPENROUTER_API_KEY` còn hạn mức ở **runtime** (embed query +
> chat + rerank cho mỗi câu hỏi), không chỉ lúc ingest. Nếu key hết hạn mức → `/chat` trả 503.

---

## 0. Fork repo (vì remote hiện tại là Itvc0110/VinChatbot)
```bash
gh repo fork Itvc0110/VinChatbot --clone=false --remote=false
# Tạo fork tại github.com/dholmes0207/VinChatbot
```
Trên máy local, trỏ push sang fork và đẩy nhánh dholmes:
```bash
git remote add fork git@github.com:dholmes0207/VinChatbot.git
git push fork dholmes
```

## 1. Chuẩn bị VPS (chạy 1 lần)
```bash
# Cài Docker + compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # logout/login lại để áp dụng

# Mở firewall cho web
sudo ufw allow 80,443/tcp

# Clone fork về server
git clone -b dholmes git@github.com:dholmes0207/VinChatbot.git /opt/vinchatbot
cd /opt/vinchatbot
```

> Server cần SSH key đọc được fork (deploy key hoặc key cá nhân). Thêm public key của VPS
> vào GitHub (Settings → SSH keys, hoặc Deploy keys của fork).

## 2. Tạo `.env` trên server
`.env` **không** nằm trong git (đã gitignore). Tạo thủ công trên VPS:
```bash
cp .env.example .env
nano .env
```
Điền tối thiểu:
- `OPENROUTER_API_KEY` — key còn hạn mức
- `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION=vinuni_documents` — trỏ Qdrant Cloud đã có data
- `DOMAIN=chatbot.tendomain.com` — domain public của bạn
- `TLS_EMAIL=ban@email.com` — email đăng ký Let's Encrypt

## 3. Trỏ DNS
Tạo bản ghi **A** cho `DOMAIN` → IP công khai của VPS. Đợi DNS lan truyền (`dig +short DOMAIN`
phải ra IP VPS) **trước khi** chạy compose, để Caddy xin được chứng chỉ.

## 4. Chạy lần đầu
```bash
cd /opt/vinchatbot
docker compose up -d --build
docker compose logs -f caddy   # xem Caddy xin chứng chỉ HTTPS
```
Truy cập: `https://DOMAIN` → giao diện chat. Kiểm tra backend:
`docker compose exec backend curl -s localhost:8000/health`.

## 5. Bật auto-deploy (GitHub Actions)
Trên fork `dholmes0207/VinChatbot` → **Settings → Secrets and variables → Actions**, thêm:

| Secret | Giá trị |
|---|---|
| `DEPLOY_HOST` | IP/hostname VPS |
| `DEPLOY_USER` | user SSH (vd `deploy` hoặc `root`) |
| `DEPLOY_SSH_KEY` | **private** key SSH (public key tương ứng nằm trong `~/.ssh/authorized_keys` của VPS) |
| `DEPLOY_PORT` | cổng SSH (thường `22`) |
| `DEPLOY_PATH` | `/opt/vinchatbot` |

Từ giờ: `git push fork dholmes` → workflow `.github/workflows/deploy.yml` tự deploy.
Có thể chạy tay tại tab **Actions → Deploy → Run workflow**.

---

## Vận hành nhanh
```bash
docker compose ps               # trạng thái
docker compose logs -f backend  # log backend
docker compose restart backend  # restart 1 service
docker compose down             # tắt
```

## Lưu ý
- `.env` chỉ sống trên server, không bao giờ commit. Đổi `.env` xong phải `docker compose up -d`
  (hoặc `restart`) để nạp lại.
- Đổi embedding model ⇒ phải re-ingest vào collection mới (xem README); không đổi nóng được.
- Form feedback của frontend ghi file cục bộ trong container (ephemeral) — mất khi rebuild;
  nếu cần giữ thì mount thêm volume.
- Caddy chỉ xin được cert khi DNS đã trỏ đúng và cổng 80/443 mở.
