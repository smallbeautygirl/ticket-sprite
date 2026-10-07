# 開票小精靈 v1 Spec

> 名詞依 [CONTEXT.md](../CONTEXT.md)；架構決策見 [docs/adr](adr/)。

## 1. 目的

PM / FAE / RD 遇到一個需求時，在網頁上被 AI 拷問（grill-with-docs），把自己與 Customer 的需求整理成一份 Spec，再以**自己的身份**開成一張 Azure DevOps Ticket 交給 RD。拷問會對照 Product 的 Knowledge Source（目前為 visionai_middleware），抓出用詞衝突與對現況的誤解。

## 2. 使用者旅程

### 2.1 PM 開 Feature（主流程）
1. 用 Observ 帳密登入。
2. 新增 Request：選 Role（預設 PM）、Request Type（Feature）、輸入文字、上傳附件。
3. 小精靈依 Role × Type 選預設 Interview Template（可手動換）。
4. AI 一輪一輪出題；每題附推薦答案。Requester 對每題：**回答 / 不知道 / 跳過（讓 AI 決定）**，或 **Handoff** 給同事。
5. AI 判斷問完，或 Requester 按「夠了，產出 Spec」。
6. 預覽並編輯 Spec，填開票欄位（Parent、Priority…），確認後以本人身份開票，並可勾選發 Teams 通知。

### 2.2 RD 發起釐清（Clarify）
1. RD 新增 Request：Role = RD、Type = Task（或 Feature），貼上「我的理解 + 想問的問題」。
2. AI 解析成 **Premise** 與 **問題**；對照程式碼**驗證每條 Premise**（必做），補漏問的題、把題目改寫成好回答的形式（附選項，不附推薦答案）。
3. RD 檢視、修改、刪除後，把題目 Handoff 給 PM（例：Kevin）。小精靈產生連結，可選擇在 Teams 頻道 @Kevin。
4. Kevin 先確認／糾正 Premise，再回答問題。AI 可直接對 Kevin 追問（限原題延伸）。
5. 回到 RD：產出 Spec → 開 Task / Feature 票，或存成 **Decision Record**（不開票）。

### 2.3 Bug（快速模板）
重現步驟 / 預期 / 實際 / 環境 / 影響範圍；FAE 版多問版本、log、懷疑模組，並可追到程式碼。

## 3. 功能需求

### 3.1 登入與身份
- 登入：後端轉呼叫 Observ `POST {OBSERV_BASE}/apiserver/users/token`（email + password），再以 `GET {OBSERV_BASE}/auth/users/me` 取得 id / email。不保存密碼，小精靈發自己的 session cookie。
- 開發模式 `AUTH_MODE=dev`：任意 email 登入，不打 Observ。
- **ADO Credential**（ADR-0001）：v1 為個人 PAT。
  - 設定頁：一鍵開啟 `https://dev.azure.com/{org}/_usersSettings/tokens`、圖文步驟（Scopes 只勾 Work Items: Read & Write）、貼上後立即驗證並顯示「已連結為：{displayName}」、填到期日。
  - PAT 以 Fernet 加密保存；到期前 14 天在 UI 提醒；開票時 401 → 導回設定頁。
  - 抽象層 `AdoCredentialProvider`，之後換成 Entra 委派 OAuth 只換實作。
  - 開發模式可設 `ADO_DEV_PAT` 給所有人共用（僅限 dev）。

### 3.2 Request 與 Interview
- 欄位：Product（v1 固定 Middleware，UI 隱藏）、Role（PM/FAE/RD，預設 PM）、Request Type（Feature/Bug/Task）、文字、附件（圖片、PDF、文字檔、log；單檔 ≤ 20MB）。
- 預設 Interview Template：

  | Role \ Type | Feature | Bug | Task |
  |---|---|---|---|
  | PM | `grill_product` | `quick_bug` | `clarify` |
  | FAE | `grill_technical` | `quick_bug_technical` | `clarify` |
  | RD | `clarify` | `quick_bug_technical` | `clarify` |

- 每題的回應：
  - **Answer** → Spec 正文。
  - **不知道** → Open Question。
  - **跳過** → 採 AI 推薦答案，成為 Assumption（標示未確認）。
  - **Premise** 的回應為「正確」或「不正確，正確的是…」。
  - 「不知道」超過 3 題核心題時顯示軟性警告，不擋送出。
- Interview 可暫停續答（狀態保存在 DB）。
- 所有登入者可瀏覽所有 Interview（列表 + 詳情）。

### 3.3 拷問引擎
- Claude API（`claude-opus-5-5`，adaptive thinking），工具為唯讀的 `list_files` / `grep` / `read_file`，限制在 Knowledge Source 目錄內。
  - PM：只能讀文件（`CONTEXT.md`、`docs/**`、`README*`）。
  - FAE / RD：可讀全部程式碼。
- 每一輪輸出結構化 JSON：本輪問題（含選項、推薦答案、理由、是否為 Premise）、是否已問完、New Terms。
- 一輪的題目必須是「前提都已確定」的問題（design tree 的 frontier）；下一輪在本輪所有題目都有回應後才產生。
- Handoff 出去的題目：**不附推薦答案**，只附選項；追問題目自動指給同一位 Respondent。
- Clarify 模板的第一輪為「準備」：解析 RD 輸入 → Premise + 問題，對照程式碼驗證 Premise 並附驗證說明，補題與改寫。

### 3.4 Handoff
- Requester 可勾選一或多題轉交給同事（email）。被轉交者登入後在「待我回答」看到題目。
- 通知：產生連結；可選擇在 Teams 頻道 @ 對方。
- 2 個工作天未回應 → 頻道再 @ 一次，最多 2 次；之後通知 Requester。
- Requester 可收回題目（自己回答或改標為 Open Question）。

### 3.5 Spec
- 語言：中文，專有名詞保留英文。
- Feature：背景／Customer 原話 → 問題陳述 → 使用情境 → 範圍（做 / 不做）→ 驗收條件（Given/When/Then）→ 相關模組（模組層級）→ Assumptions → Open Questions → New Terms。
- Bug：摘要 → 環境 → 重現步驟 → 預期 → 實際 → 影響範圍與嚴重度 → 懷疑模組 → Assumptions → Open Questions → New Terms。
- Task（Clarify）：背景 → 已確認的 Premise（含糾正）→ 問答結論 → 決定事項 → 後續行動 → Open Questions → New Terms。
- 每題記錄 Respondent；Spec 中標註「由 Kevin 回答」等。
- Requester 預覽並可編輯（Markdown），確認後凍結。

### 3.6 開票
- Feature → User Story；Bug → Bug；Task → Task。
- 欄位：
  - Title：AI 建議，可改。
  - Description：Spec 轉 HTML，加上回到 Interview 的連結。
  - Parent：預設 #41152，可搜尋（輸入 id 或標題關鍵字）更換。
  - Area Path：`Deliver team`。
  - Iteration、Assigned To：留空。
  - Priority（1–4）／Severity（Bug）：AI 建議、Requester 確認。
  - Tags：`ticket-sprite; role:{pm|fae|rd}`。
- 附件同步上傳到 Ticket。
- 開票後 Spec 凍結，Interview 狀態為 `ticketed`，記錄 Ticket id / URL。
- 不開票：存成 Decision Record（狀態 `decision_record`），有分享連結。
- 開票後可選擇發 Teams 頻道通知（預設勾選）。

### 3.7 Notification（Teams Workflows webhook）
- `TEAMS_WEBHOOK_URL`：POST Adaptive Card；@mention 使用 `msteams.entities`（以 email 當 id）。
- 事件：開票、Handoff、Handoff 催促、催促上限通知 Requester。

### 3.8 Knowledge Source（ADR-0002）
- 專用 clone：`KNOWLEDGE_ROOT/lighthouse-saas-api`，追蹤 `main`，每小時 `git pull --ff-only`；Product 指向其中的 `apps/visionai_middleware`。
- 初次可由本機 `/opt/lighthouse-saas-api` clone（`git clone --branch main`）。

## 4. 非功能
- 部署：本 VM，docker compose（postgres + backend + frontend）。
- 技術：FastAPI + SQLAlchemy (async) + Postgres；Anthropic Python SDK；Next.js。
- 秘密：`ANTHROPIC_API_KEY`、`SESSION_SECRET`、`FERNET_KEY`、`TEAMS_WEBHOOK_URL` 從環境變數讀取。

## 5. v1 不做
客戶進入系統、RD 收票後回小精靈討論、自動拆 Task、寫回 middleware repo、Middleware 以外的 Product、Teams bot 私訊、Entra OAuth（另案申請）。

## 6. 驗收
- 後端單元／整合測試：登入（dev + Observ mock）、建立 Interview、回應三種動作、Premise、Handoff 與收回、催促排程、Spec 產生、開票（ADO mock）、PAT 驗證、Knowledge Source 路徑限制。
- 以假 LLM 跑完整 PM Feature 流程與 RD Clarify 流程。
