# Knowledge Source 讀取專用的 main clone，不讀開發者的工作目錄

Interview 對照的是 visionai_middleware，但我們不直接讀 `/opt/lighthouse-saas-api`。小精靈在同一台 VM 上維護一份自己的 `main` clone，每小時 pull 一次。那份共用的 checkout 是開發者的工作目錄：它可能停在任何 feature branch 上，也可能有還沒 commit 的改動。如果拿它當依據，Premise 的驗證和 Bug 的拷問就會根據「還沒上線的程式」，而且只要有人切 branch，依據就會跟著悄悄改變。
