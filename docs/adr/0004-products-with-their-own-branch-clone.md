# 每個 Product 各有一份追自己分支的 clone

小精靈原本只服務 Middleware，Knowledge Source、預設 Parent 和給 AI 的說明都寫死在設定和 prompt 裡。北捷模擬器（`apps/taipei_MRT_simulation`）之後會是另一個產品，但目前還在 lighthouse-saas-api 的 `feat/taipei-mrt-simulation` 分支上，沒有進 `main`。我們把「Product」做成一份清單（`backend/ticket_sprite/products.py`）：每個 Product 記錄自己的分支、目錄、預設 Parent、PM 和 FAE 除了文件以外能看的畫面檔、任何人都不需要看的大量資料，以及給 AI 的產品說明。每筆 Interview 記住它的 Product，Knowledge Source、prompt 和開票的預設 Parent 都依它決定。

每個 Product 在 `KNOWLEDGE_ROOT` 底下有自己的 clone，同步方式從 `pull --ff-only` 改成「fetch 指定分支，再強制切到它」。功能分支可能被 rebase 或 force-push，`--ff-only` 遇到就會卡在舊版；唯讀 clone 沒有自己的改動需要保留。本機路徑當來源時，分支可能只以遠端追蹤 ref 存在（那份工作目錄 fetch 過但沒 checkout 過），所以兩種 ref 都會試。

這和 ADR-0002「不依據還沒上線的程式」有意識地衝突：北捷目前只存在於功能分支，拷問只能對照它。等北捷合進 `main`，把 `TAIPEI_MRT_BRANCH` 改成 `main` 即可，不用改程式。

## 考慮過的做法

- **北捷當成 Middleware 的「客戶專案」欄位**：北捷是獨立的程式碼與產品，對照 middleware 的文件只會問出不相干的題目。
- **同一份 clone 用 worktree 放多個分支**：省一點硬碟，但同步和失敗處理綁在一起，一個分支壞了會拖累另一個；repo 只有約 60MB，各自 clone 比較單純。
- **Product 設定全部放環境變數**：畫面檔規則、隱藏規則和 AI 說明是程式的一部分，放程式碼裡才能測試；只有會隨部署改變的分支、目錄、Parent 和啟用清單（`PRODUCTS_ENABLED`）放環境變數。
