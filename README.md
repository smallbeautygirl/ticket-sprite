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

## 本機開發

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
AUTH_MODE=dev LLM_MODE=fake FERNET_KEY=$(.venv/bin/python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
  .venv/bin/uvicorn ticket_sprite.main:app --reload --port 8000
.venv/bin/python -m pytest

# frontend
cd frontend && npm install && npm run dev   # BACKEND_URL 預設為 http://localhost:8000
```

- `AUTH_MODE=dev`：輸入任何 email 都能登入，不會呼叫 Observ。
- `LLM_MODE=fake`：使用固定的假拷問員，不呼叫 Claude API。
- `ADO_DEV_PAT`：開發時讓所有人共用一個 PAT 開票。

## 待辦（v1 之後）

- Entra ID 委派 OAuth 取代個人 PAT（ADR-0001，只要換掉 `AdoCredentialProvider` 的實作）。
- 支援 Middleware 以外的 Product。
- Teams bot 私訊。
