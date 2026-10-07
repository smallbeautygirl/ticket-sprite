"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Sprite from "@/components/Sprite";
import { api, deleteConfirmText, InterviewSummary, ROLE_LABEL, STATUS_LABEL, TYPE_LABEL } from "@/lib/api";

type Scope = "for-me" | "mine" | "all";
const SCOPES: { id: Scope; label: string }[] = [
  { id: "for-me", label: "待我回答" },
  { id: "mine", label: "我發起的" },
  { id: "all", label: "全部" },
];

const ONBOARDING_KEY = "sprite.onboarding.dismissed";

const STATUS_BADGE: Record<InterviewSummary["status"], string> = {
  interviewing: "accent",
  spec_draft: "warn",
  ticketed: "ok",
  decision_record: "",
};

function TrashIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 7h16" />
      <path d="M10 11v6M14 11v6" />
      <path d="M6 7l1 13h10l1-13" />
      <path d="M9 7V4h6v3" />
    </svg>
  );
}

export default function Home() {
  return (
    <Suspense>
      <Requests />
    </Suspense>
  );
}

function Requests() {
  const router = useRouter();
  // 使用說明 in the top bar links here with ?guide=1 to bring the card back
  const guide = useSearchParams().get("guide") === "1";
  const [scope, setScope] = useState<Scope>("mine");
  const [items, setItems] = useState<InterviewSummary[] | null>(null);
  const [forMeCount, setForMeCount] = useState(0);
  const [me, setMe] = useState<string | null>(null);
  const [adoReady, setAdoReady] = useState<boolean | null>(null);
  const [startedOne, setStartedOne] = useState<boolean | null>(null);
  const [dismissed, setDismissed] = useState(true); // until storage is read, so the card doesn't flash
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0); // bumped by 重試

  useEffect(() => {
    api
      .me()
      .then((m) => {
        setMe(m.email);
        setAdoReady((m.ado.connected || m.ado.dev_fallback) && !m.ado.expired);
      })
      .catch(() => {});
    api.listInterviews("mine").then((rows) => setStartedOne(rows.length > 0)).catch(() => {});
    try {
      setDismissed(localStorage.getItem(ONBOARDING_KEY) === "1");
    } catch {
      setDismissed(false);
    }
    api
      .listInterviews("for-me")
      .then((rows) => {
        setForMeCount(rows.length);
        if (rows.length) setScope("for-me");
      })
      .catch(() => {}); // the list below reports the failure
  }, []);

  useEffect(() => {
    let current = true; // a slow answer for the previous tab must not overwrite this one
    setItems(null);
    setLoadError(null);
    api
      .listInterviews(scope)
      .then((rows) => current && setItems(rows))
      .catch((err) => current && setLoadError((err as Error).message));
    return () => {
      current = false;
    };
  }, [scope, attempt]);

  function dismiss() {
    if (guide) router.replace("/");
    setDismissed(true);
    try {
      localStorage.setItem(ONBOARDING_KEY, "1");
    } catch {
      // private window: hidden for this visit only
    }
  }

  const showOnboarding =
    guide || (!dismissed && adoReady !== null && startedOne !== null && !(adoReady && startedOne));

  async function remove(i: InterviewSummary) {
    if (!confirm(deleteConfirmText(i))) return;
    setError(null);
    try {
      await api.deleteInterview(i.id);
      setItems((rows) => rows?.filter((r) => r.id !== i.id) ?? null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="stack">
      <div className="row">
        <h1>需求</h1>
        <span className="spacer" />
        <Link href="/new" className="btn primary">＋ 新增需求</Link>
      </div>
      <div className="seg" role="group" aria-label="篩選需求">
        {SCOPES.map((s) => (
          <button key={s.id} className={scope === s.id ? "on" : ""} aria-pressed={scope === s.id} onClick={() => setScope(s.id)}>
            {s.label}
            {s.id === "for-me" && forMeCount > 0 && ` (${forMeCount})`}
          </button>
        ))}
      </div>
      {showOnboarding && (
        <section className="card stack onboarding" aria-label="開始使用">
          <div className="row" style={{ alignItems: "center" }}>
            <Sprite pose="head" size={48} />
            <div className="stack" style={{ gap: 2, flex: 1, minWidth: 0 }}>
              <h2 style={{ margin: 0, fontSize: 19 }}>開始使用開票小精靈</h2>
              <span className="muted small">
                寫下需求 → 小精靈拷問你，把模糊的地方問清楚 → 整理成 Spec → 以你的身份開成 ADO 票。隨時都能按「夠了，產出 Spec」提早結束。
              </span>
            </div>
            <button className="link small" onClick={dismiss}>
              {guide ? "關閉" : "不再顯示"}
            </button>
          </div>
          <ol>
            <li className={adoReady ? "done" : ""}>
              <span className="check" aria-hidden="true">{adoReady ? "✓" : "1"}</span>
              <span className="what">連結 Azure DevOps（約 1 分鐘，開票時要用）</span>
              {!adoReady && (
                <Link href="/settings" className="btn small">
                  前往設定
                </Link>
              )}
            </li>
            <li className={startedOne ? "done" : ""}>
              <span className="check" aria-hidden="true">{startedOne ? "✓" : "2"}</span>
              <span className="what">開第一筆需求（可以從範例開始）</span>
              {!startedOne && (
                <Link href="/new" className="btn small primary">
                  新增需求
                </Link>
              )}
            </li>
          </ol>
        </section>
      )}
      {error && <div className="notice danger" role="alert">{error}</div>}
      <div className="card list" style={{ padding: 0 }}>
        {items === null &&
          (loadError ? (
            <div className="row" role="alert" style={{ padding: 16 }}>
              <span>讀不到需求列表：{loadError}</span>
              <button onClick={() => setAttempt((n) => n + 1)}>重試</button>
            </div>
          ) : (
            <p className="muted" style={{ padding: 16 }}>載入中…</p>
          ))}
        {items?.length === 0 && (
          <p className="muted" style={{ padding: 16 }}>
            {scope === "for-me" ? "目前沒有轉交給你的題目。" : "還沒有需求。"}
          </p>
        )}
        {items?.map((i) => (
          <div key={i.id} className="item-row">
          <Link href={`/interviews/${i.id}`} className="item">
            <span className={`badge ${STATUS_BADGE[i.status]}`}>{STATUS_LABEL[i.status]}</span>
            <span className="badge">{i.product_label}</span>
            <span className="badge">{TYPE_LABEL[i.request_type]}</span>
            <span className="title">{i.title}</span>
            {i.ticket_id && <span className="small">#{i.ticket_id}</span>}
            <span className="muted small">
              {ROLE_LABEL[i.role]} · {i.requester.split("@")[0]} · {new Date(i.created_at).toLocaleDateString("zh-TW")}
            </span>
          </Link>
          {me === i.requester && (
            <button className="icon danger" aria-label={`刪除 ${i.title}`} title="刪除" onClick={() => remove(i)}>
              <TrashIcon />
            </button>
          )}
          </div>
        ))}
      </div>
    </div>
  );
}
