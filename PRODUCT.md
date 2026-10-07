# Product

<!-- impeccable:product-schema 1 -->

> 名詞依 [CONTEXT.md](CONTEXT.md)；功能細節見 [docs/spec.md](docs/spec.md)。

## Platform

web

## Users

- **Requester（主要使用者）**：公司內的 PM、FAE、RD。手上有一個來自 Customer 或內部的需求或 bug，要把它變成一張 RD 能直接開工的 Azure DevOps Ticket。多半在上班時間、桌機上使用：開需求、回答拷問、檢查並修改 Spec、開票。
- **Respondent（被 Handoff 的同事）**：典型是 RD 把產品面問題轉給 PM。從 Teams 頻道的 @ 或連結點進來，常常是在**手機**上，只回答轉給自己的幾題就離開。
- **RD（Ticket 的讀者）**：不一定進小精靈，在 ADO 上讀 Spec。Spec 的內容依 Audience 調整。

## Product Purpose

讓 PM / FAE / RD 透過網頁上一輪一輪的 AI 拷問（grill-with-docs），把模糊的需求整理成 Spec，再以**自己的身份**開成 ADO Ticket。

**成功的定義：PM / FAE 開一張好票更快、更輕鬆。** 降低開票的時間與心理負擔是首要目標。內容完整、RD 少回問、抓出誤解與用詞衝突是隨之而來的效果，不能為了它們讓流程變重。

## Positioning

拷問會對照 Product 的 Knowledge Source（visionai_middleware 的 main branch：詞彙表、ADR、文件，RD 另含程式碼），所以能抓出用詞衝突（New Term）和對現況的錯誤理解（Premise 驗證）。產出直接是可開票的 Spec，並以本人身份開進 ADO，不是一般的聊天機器人或表單。

## Operating Context

- 流程：新增需求（Role × Request Type 決定預設 Interview Template）→ 一輪一輪回答（回答／不知道／跳過，或 Handoff）→ 「夠了，產出 Spec」→ 預覽、編輯 Spec → 開票，或存成 Decision Record。
- 每一輪 AI 可能要等幾分鐘，因為它會實際去查文件與程式碼；等待時要讓人知道它在做什麼。
- 外部系統：Observ 帳號登入、Azure DevOps（個人 PAT）、Teams 頻道通知（開票、Handoff、催促）。
- 目前是試用版，部署在公司內部的 VM 上，只開放給少數同事。

## Capabilities and Constraints

- Product 目前只有 Middleware。
- 介面語言是中文；領域名詞保留英文（Spec、Premise、Open Question、Assumption、Handoff、Parent…），用詞以 CONTEXT.md 為準，畫面上 Interview 顯示為「需求」。
- PM、FAE 只能讀文件，產出精簡、產品層級的 Spec；RD 可讀程式碼。
- 一個 Request 最多一張 Ticket；開票後 Spec 凍結，可重新產出並推回 ADO 描述。
- v1 不做：Customer 進入系統、自動拆 Task、Middleware 以外的 Product、Teams bot 私訊、Entra OAuth。

## Brand Commitments

- 名稱：「開票小精靈」（Ticket Sprite），固定。
- 角色：螢火蟲小精靈（`frontend/components/Sprite.tsx`，姿勢有 logo、head、reading、ticket），固定。
- 語氣：親切、口語，例如「小精靈正在翻書找資料…」「夠了，產出 Spec」「轉給你的題目都回答完了，謝謝！」，固定。

## Evidence on Hand

- `frontend/app/new/page.tsx` 的三個範例取自試用期間的真實需求。
- 目前沒有使用數據、使用者回饋整理或成效指標，未來的設計工作不得杜撰。

## Product Principles

1. **讓開票變輕鬆。** 每個決定先問：這會讓 PM / FAE 更快開出好票，還是更累？
2. **隨時可以喊停。** 拷問是幫忙，不是關卡；不知道、跳過、提早產出 Spec 都要一樣容易。
3. **用對的詞。** 介面與 Spec 都遵守 CONTEXT.md，衝突要顯示出來，不能悄悄蓋過。
4. **等待要透明。** AI 工作要花時間，就讓人看到它讀了什麼、還要多久。
5. **轉交的人只做自己那幾題。** 從手機點進來的 Respondent 要能馬上看懂、回答完就走。
