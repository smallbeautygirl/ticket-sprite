"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import Sprite from "@/components/Sprite";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [devMode, setDevMode] = useState(false);

  useEffect(() => {
    api.meta().then((m) => setDevMode(m.auth_mode === "dev")).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(email, password);
      router.push(params.get("next") || "/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 380, margin: "10vh auto 0" }}>
      <div className="card stack">
        <div className="row" style={{ gap: 14, alignItems: "center", flexWrap: "nowrap" }}>
          <Sprite pose="head" size={64} />
          <div>
          <h1 className="row" style={{ gap: 8 }}>
            開票小精靈 <span className="badge trial">試用版</span>
          </h1>
          <p className="muted small" style={{ margin: 0 }}>使用 Observ 帳號登入</p>
          </div>
        </div>
        {devMode && <div className="notice warn small">開發模式：不驗證密碼</div>}
        <form className="stack" onSubmit={submit}>
          <label className="field">
            <span>Email</span>
            <input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            <span>密碼</span>
            <div className="password-input">
              <input
                type={showPassword ? "text" : "password"}
                required={!devMode}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="icon"
                aria-label={showPassword ? "隱藏密碼" : "顯示密碼"}
                aria-pressed={showPassword}
                title={showPassword ? "隱藏密碼" : "顯示密碼"}
                onClick={() => setShowPassword((v) => !v)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
                  <circle cx="12" cy="12" r="3" />
                  {showPassword && <path d="M4 4l16 16" />}
                </svg>
              </button>
            </div>
          </label>
          {error && <div className="notice danger">{error}</div>}
          <button className="primary" disabled={busy} type="submit" style={{ justifyContent: "center" }}>
            {busy ? "登入中…" : "登入"}
          </button>
        </form>
        <p className="muted small" style={{ margin: 0 }}>密碼只會轉給 Observ 驗證，小精靈不會保存。</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
