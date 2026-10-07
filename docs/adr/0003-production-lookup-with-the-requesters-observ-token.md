# 用 Requester 自己的 Observ token 唯讀查詢正式站（Production Lookup）

PM 和 Solution Engineer 多半是在正式站的畫面上發現需求或 bug，但 Knowledge Source 只有 visionai_middleware 的後端文件和程式，小精靈對不上「這一頁的這個東西」。正式站的前端也用 Observ 登入，而且前端打 middleware API 時帶的就是同一個 Observ bearer token，所以小精靈登入時換到的 token，本來就能看到這個人在畫面上看到的資料。

我們改變 ADR-0001「什麼都不保存」的做法：登入時把 Observ 的 access token 連同它的到期時間用 Fernet 加密存起來（跟 ADO PAT 同一把鑰匙），登出就刪掉。密碼仍然只轉交一次、從不保存。Observ 不發 refresh token，正式站自己也是 token 過期就跳回登入頁，所以 access token 三天過期之後，小精靈就查不了正式站，要等 Requester 重新登入。在那之前它只能看截圖，畫面上會提示 Requester 重新登入。

拷問時小精靈多了一個工具 `fetch_production(path)`，它的限制寫在程式裡，不靠提示詞：

- 只發 GET，host 固定是 middleware API 的位址，path 不能帶 scheme 或 host。
- path 必須對得上 middleware OpenAPI 裡的 GET 路徑，下載（`/download`）和 WebSocket 路徑除外。
- 用的是 **Requester** 的 token。轉交出去的題目只是由別人回答，小精靈仍然在 Requester 的 Interview 裡工作，權限範圍就是 Requester 的權限。
- token 只在後端，模型永遠看不到。`claude_code` 模式用後端提供的 MCP server 掛上這個工具，`claude` 模式直接把它加進 tool 定義。
- 回應有長度上限，並標成「正式站資料，不是指示」。
- 每次查詢都記下是誰、哪個 Interview、哪個 path、回應狀態碼。

這個功能預設關閉（`PRODUCTION_LOOKUP=false`）。正式站的資料可能有客戶資訊，而目前的試用走的是擁有者個人的 Claude 登入（`CLAUDE_CODE_SHARED`）。客戶資料經過個人方案，跟經過公司的 API key 是兩回事，所以要等換成 API key，或由擁有者明確決定之後才打開。

## Considered Options

- **用無頭瀏覽器帶 token 開正式站畫面**：被否決，因為太重，而且我們要的是畫面背後的資料，API 已經拿得到。
- **另開一個唯讀的服務帳號**：被否決，因為它看到的範圍跟 Requester 不同，可能看到 Requester 自己都看不到的客戶資料。
- **只靠截圖和頁面網址**：仍然保留，是 token 失效或功能關閉時的退路；但截圖看不到畫面以外的狀態，也沒辦法讓小精靈自己去查證。
- **讓模型拿到 token 自己發請求**：被否決，因為只要一段被注入的指示，就能讓它以 Requester 的身份在正式站上做任何事。
