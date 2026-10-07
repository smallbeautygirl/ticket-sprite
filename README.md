# 開票小精靈 (Ticket Sprite)

PM / FAE / RD 把一個需求丟進來，AI 用 grill-with-docs 的方式一輪一輪拷問，對照 middleware 的詞彙表、ADR 和程式碼，最後整理成 Spec，並以**你本人的身份**開成 Azure DevOps 票。

- 名詞：[CONTEXT.md](CONTEXT.md)
- 規格：[docs/spec.md](docs/spec.md)
- 決策：[docs/adr/](docs/adr/)

## 架構

```
frontend (Next.js, :3000) ──/api/*──▶ backend (FastAPI, :8000) ──▶ Postgres
                                         ├─▶ Observ  /apiserver/users/token, /auth/users/me   （登入）
                                         ├─▶ Claude API（claude-opus-5-5，唯讀工具：list_files / grep / read_file）
                                         ├─▶ Knowledge Source：專用的 main clone（每小時 pull）
                                         ├─▶ Azure DevOps REST（以使用者自己的 PAT 開票）
                                         └─▶ Teams Workflows webhook（通知、轉交、催促）
```

## 部署（這台 VM）

```bash
cp .env.example .env      # 填入 SESSION_SECRET、FERNET_KEY、ANTHROPIC_API_KEY、TEAMS_WEBHOOK_URL
docker compose up -d --build
# 開 http://<vm>:3000
```

- `SPRITE_PORT` 可以改對外的 port。
- Knowledge Source 第一次會從 `/opt/lighthouse-saas-api` clone `main` 分支到 volume。注意：用本機路徑當來源時，只看得到那份工作目錄已經 fetch 過的 `main`。要永遠追 GitHub 上的 `main`，就把 `KNOWLEDGE_REPO_SOURCE` 改成 GitHub URL，並掛一把唯讀的 deploy key。
- Teams 通知：在頻道建一個 Workflows「收到 webhook 時發文到頻道」，把 URL 填進 `TEAMS_WEBHOOK_URL`。

## 單人試用（沒有 API key，用自己的 Claude Code）

拷問改由 `claude -p` 執行，用的是你自己的 Claude 登入。因為個人帳號不能替別人服務，這個模式**只開放 `OWNER_EMAIL` 登入，也不能轉交題目**。

```bash
cp .env.example .env    # OWNER_EMAIL=你的 email、SPRITE_UID / SPRITE_GID / CLAUDE_DIR，再產生 SESSION_SECRET / FERNET_KEY
docker compose -f docker-compose.single-user.yml up -d --build   # 開 http://<vm>:3000
```

- 後端 image 內含 Claude Code CLI（版本由 `backend/Dockerfile` 的 `CLAUDE_CODE_VERSION` 固定），登入則掛進你的 `~/.claude`（`CLAUDE_DIR`），所以要先在主機上用 `claude` 登入過。容器以 `SPRITE_UID` 執行，`data/` 和 `~/.claude` 的檔案擁有者不會變。
- 開機會自動起來：Docker 開機啟動，兩個服務都是 `restart: unless-stopped`。要停用 `docker compose -f docker-compose.single-user.yml down`。
- 資料（SQLite、附件、Knowledge Source clone）放在 `data/`。Knowledge Source 的來源 repo 若是群組共用（例如 `/opt/lighthouse-saas-api` 屬於 `docker` 群組），把那個群組的 gid 填進 `KNOWLEDGE_SOURCE_GID`。
- 改了程式碼後重跑上面的 `up -d --build`。
- 暫時開放給同事試用（還沒有 API key 時）：`.env` 設 `CLAUDE_CODE_SHARED=true`，並把可登入的人列在 `ALLOWED_EMAILS`（含自己）。轉交也會打開。這等於把**個人的 Claude 方案**分給別人用（使用條款與額度都算在擁有者身上），拿到 API key 後請改回 `LLM_MODE=claude`。
- 不用 Docker 也可以：`(cd frontend && npm run build) && scripts/trial.sh start`（後端 127.0.0.1:8020，前端 0.0.0.0:3000；`scripts/trial.sh stop` 停止），但開機不會自動起來。

- PM、FAE 角色：CLI 在一份只有文件（含 spec）的複本裡執行，看不到程式碼，產出的 Spec 也會精簡、不寫實作細節。RD 角色：直接在產品目錄執行。工作目錄以外的讀取一律被拒絕（`--permission-mode dontAsk`）。
- 每一輪可能要等幾分鐘，因為 CLI 會實際去查文件和程式碼。

## 本機開發

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
AUTH_MODE=dev LLM_MODE=fake FERNET_KEY=$(.venv/bin/python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
  .venv/bin/uvicorn ticket_sprite.main:app --reload --port 8020
.venv/bin/python -m pytest

# frontend
cd frontend && npm install && npm run dev   # BACKEND_URL 預設為 http://localhost:8020
```

- `AUTH_MODE=dev`：輸入任何 email 都能登入，不會呼叫 Observ。
- `LLM_MODE=fake`：使用固定的假拷問員，不呼叫 Claude API。
- `ADO_DEV_PAT`：開發時讓所有人共用一個 PAT 開票。

## 待辦（v1 之後）

- Entra ID 委派 OAuth 取代個人 PAT（ADR-0001，只要換掉 `AdoCredentialProvider` 的實作）。
- 支援 Middleware 以外的 Product。
- Teams bot 私訊。
