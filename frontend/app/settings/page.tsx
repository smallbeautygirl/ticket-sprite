"use client";

import { useEffect, useState } from "react";
import { api, Me, Role, ROLE_LABEL } from "@/lib/api";

export default function Settings() {
  const [me, setMe] = useState<Me | null>(null);
  const [pat, setPat] = useState("");
  const [expires, setExpires] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    api.me().then(setMe);
  }, []);

  async function connect() {
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const ado = await api.connectAdo(pat.trim(), expires || null);
      setMe((m) => (m ? { ...m, ado } : m));
      setPat("");
      setOk(`已連結為：${ado.display_name}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    const ado = await api.disconnectAdo();
    setMe((m) => (m ? { ...m, ado } : m));
    setOk(null);
  }

  if (!me) return <p className="muted">載入中…</p>;
  const ado = me.ado;

  return (
    <div className="stack">
      <h1>設定</h1>

      <h2>預設 Role</h2>
      <div className="card row">
        <div className="seg">
          {(["pm", "fae", "rd"] as Role[]).map((r) => (
            <button
              key={r}
              className={me.default_role === r ? "on" : ""}
              onClick={async () => {
                await api.setDefaultRole(r);
                setMe({ ...me, default_role: r });
              }}
            >
              {ROLE_LABEL[r]}
            </button>
          ))}
        </div>
        <span className="muted small">新增 Request 時預設選這個 Role。</span>
      </div>

      <h2>Azure DevOps 連結</h2>
      <div className="card stack">
        {ado.connected ? (
          <div className={`notice ${ado.expired ? "danger" : ado.expiring_soon ? "warn" : "ok"}`}>
            已連結為：<b>{ado.display_name}</b>
            {ado.expires_on && <>，PAT 到期日 {ado.expires_on}</>}
            {ado.expired && "（已過期，請重新產生）"}
            {!ado.expired && ado.expiring_soon && "（即將到期，請盡快更新）"}
          </div>
        ) : ado.dev_fallback ? (
          <div className="notice warn">開發模式：目前使用共用的開發 PAT 開票。正式環境請連結自己的 PAT。</div>
        ) : (
          <div className="notice info">開票會以「你本人」的身份建立，所以需要一次性連結你的 Azure DevOps。</div>
        )}

        <ol className="steps">
          <li>
            <a href={ado.token_page} target="_blank" rel="noreferrer" className="btn">
              ① 開啟 Azure DevOps 的 Personal Access Tokens 頁面 ↗
            </a>
          </li>
          <li>按 <b>+ New Token</b>，Name 填 <code>ticket-sprite</code>，Organization 選 <b>linkerengineer</b>。</li>
          <li>Expiration 選 <b>Custom defined</b>，設到最長（一年）。</li>
          <li>
            Scopes 選 <b>Custom defined</b>，<b>只勾 Work Items → Read &amp; Write</b>，其他都不要勾。
          </li>
          <li>按 Create，複製產生的 token（只會顯示一次），貼到下面。</li>
        </ol>

        <div className="grid-2">
          <label className="field">
            <span>Personal Access Token</span>
            <input type="password" value={pat} onChange={(e) => setPat(e.target.value)} placeholder="貼上 PAT" />
          </label>
          <label className="field">
            <span>到期日（用來提醒你更新）</span>
            <input type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />
          </label>
        </div>
        {error && <div className="notice danger">{error}</div>}
        {ok && <div className="notice ok">{ok}</div>}
        <div className="row">
          <button className="primary" disabled={busy || pat.trim().length < 10} onClick={connect}>
            {busy ? "驗證中…" : "驗證並連結"}
          </button>
          {ado.connected && (
            <button className="danger" onClick={disconnect}>
              取消連結
            </button>
          )}
          <span className="muted small">PAT 會加密保存，只用來以你的身份開票與搜尋 Parent。</span>
        </div>
      </div>
    </div>
  );
}
