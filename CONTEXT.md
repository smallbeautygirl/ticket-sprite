# 開票小精靈 (Ticket Sprite)

讓 PM / FAE / RD 把一個需求透過網頁上的拷問整理成 Spec，並以自己的身份開成一張 Azure DevOps 票交給 RD。

## Language

### 人與身份

**Requester**:
在小精靈發起 Interview、最後以自己身份開票的人。
_Avoid_: User, 使用者, 提單人

**Respondent**:
回答某一題的人；預設是 Requester，題目被 Handoff 後則是被轉交的同事。
_Avoid_: Answerer, 回覆者

**Role**:
Requester 本次 Interview 所採用的身份：PM、FAE 或 RD（預設 PM）；只決定預設的 Interview Template 與 Knowledge Source 深度，不代表權限。
_Avoid_: 權限, 職稱

**Customer**:
提出原始需求的外部客戶；不會進入小精靈，其資料由 Requester 以 Attachment 帶入。
_Avoid_: Client

### 拷問

**Request**:
Requester 帶進來的一個原始需求（文字加 Attachment），是一次 Interview 的起點。
_Avoid_: 需求單, Ticket

**Request Type**:
Request 的分類：Feature、Bug 或 Task（Task 主要用於 RD 發起的 Interview）。
_Avoid_: Category, Kind

**Interview**:
針對一個 Request 的一連串問答，可暫停後續答，結束時產出一份 Spec。
_Avoid_: Session, 對話, Chat

**Interview Template**:
決定 Interview 怎麼問的方式（例如 grill-with-docs、快速 bug 回報）；預設值由 Role × Request Type 決定。
_Avoid_: Prompt, Skill, 問卷

**Answer**:
Respondent 對一題的明確回答，寫入 Spec 正文。

**Premise**:
Requester 對現況的理解陳述，交由 Respondent 確認或糾正；在回答問題之前先確認。AI 會先對照 Knowledge Source 驗證。
_Avoid_: 假設, 理解, Context

**Handoff**:
把一題或多題轉交給公司內另一位同事回答；被轉交者成為那些題目的 Respondent。典型情境是 RD 把產品面問題轉給 PM。
_Avoid_: 指派, Assign, 轉寄

**Open Question**:
Respondent 回答「不知道」的題目；在 Spec 中列為未解，交由 RD 或後續釐清。
_Avoid_: TBD, 待確認

**Assumption**:
Respondent 選擇「跳過 / 讓 AI 決定」時採用的 AI 建議答案；在 Spec 中標示為未經確認。
_Avoid_: Default, 預設答案

**Product**:
Request 所針對的產品；決定 Knowledge Source 與預設 Parent。目前只有 Middleware。
_Avoid_: App, Project, 模組

**Knowledge Source**:
Interview 時用來對照用詞與現況的資料來源（Product 的文件，FAE 另含程式碼）。Middleware 的 Knowledge Source 為 visionai_middleware 的 main branch。
_Avoid_: Docs, Context

**New Term**:
Interview 中出現、Knowledge Source 詞彙表裡沒有或與其衝突的名詞；列在 Spec 中，由 RD 決定是否收進該產品的詞彙表。
_Avoid_: Glossary update

### 產出

**Spec**:
Interview 的產出，整合 Requester 與 Customer 的需求；保存在小精靈，開票時寫入 Ticket 的 Description 並附回連結，之後即凍結（後續修改在 ADO 進行）。
_Avoid_: PRD, 需求文件

**Ticket**:
由 Spec 開出的一張 Azure DevOps work item；一個 Request 最多對應一張 Ticket（Feature → User Story，Bug → Bug，Task → Task）。開票後的討論與拆 Task 都在 ADO 進行。
_Avoid_: Work item, 單, Issue

**Decision Record**:
不開票就結束的 Interview 所留下的 Spec，保存在小精靈並可分享連結。
_Avoid_: 會議記錄, Memo

**Parent**:
Ticket 所掛的上層 ADO work item；預設為 Middleware（#41152）。
_Avoid_: Epic, Feature（指上層時）

**Notification**:
發到團隊 Teams channel 的訊息：開票通知、Handoff 通知與催促（@ Respondent）。
_Avoid_: Alert（middleware 中 Alert 指 Gate 健康告警）

**ADO Credential**:
Requester 用來以本人身份開票的 Azure DevOps 憑證（v1 為個人 PAT，之後改為 Entra 委派授權），與登入小精靈的 Observ 身份分開。
_Avoid_: Token, 登入
