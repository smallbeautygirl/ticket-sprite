# 兩種身份：Observ 帳密登入，ADO 以使用者本人委派開票

小精靈用 Observ 的 `POST /users/token`（email + 密碼）確認「你是誰」，跟 middleware PM console 用同一套，不在 Keycloak 另外註冊 client。小精靈不保存密碼。Observ 的 token 無法拿來呼叫 Azure DevOps，而 Ticket 又必須以 Requester 本人的身份建立（Created By 要是本人，不能是服務帳號），所以 ADO 憑證是第二種、獨立的身份。這個憑證包在一層「ADO 憑證」抽象後面：v1 用個人 PAT（只開 Work Items 讀寫權限，加密保存，有引導式設定頁和到期提醒）；同時申請 Entra ID app 註冊，核准後換成委派 OAuth（scope `499b84ac-1321-427f-aa17-267ca6975798/.default`），使用者只要授權一次。

## Considered Options

- **共用服務帳號開票**：被否決，因為 Ticket 會失去 Requester 本人的身份。
- **另外註冊一個 Keycloak OIDC client**：被否決，因為要多一道管理員手續，而 Observ 的帳密 API 已經夠用。
- **Keycloak 把 Entra 設成身份提供者（brokering），一次登入就拿到兩種身份**：被否決，因為要動到平台共用的 Keycloak 設定。
- **Azure DevOps 舊版 OAuth**：已停用，不再開放新應用程式申請。
