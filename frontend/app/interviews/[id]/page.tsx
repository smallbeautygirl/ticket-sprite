"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, InterviewDetail, Me, Meta, Question, ROLE_LABEL, STATUS_LABEL, TYPE_LABEL } from "@/lib/api";
import QuestionCard from "@/components/QuestionCard";
import SpecPanel from "@/components/SpecPanel";

function byRound(questions: Question[]): [number, Question[]][] {
  const groups = new Map<number, Question[]>();
  for (const q of questions) {
    const list = groups.get(q.round) ?? [];
    list.push(q);
    groups.set(q.round, list);
  }
  // Premises first within a round: confirm the ground before answering questions
  return Array.from(groups.entries()).map(([r, qs]) => [
    r,
    [...qs.filter((q) => q.kind === "premise"), ...qs.filter((q) => q.kind !== "premise")],
  ]);
}

export default function InterviewPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [d, setD] = useState<InterviewDetail | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [handoffTo, setHandoffTo] = useState("");
  const [handoffNotify, setHandoffNotify] = useState(true);
  const [handoffLink, setHandoffLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api
      .interview(id)
      .then((x) => {
        setD(x);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, [id]);

  useEffect(() => {
    load();
    api.me().then(setMe).catch(() => {});
    api.meta().then(setMeta).catch(() => {});
  }, [load]);

  // Poll fast while the engine works, slowly otherwise (Handoff answers arrive from others)
  useEffect(() => {
    if (!d) return;
    const frozen = d.status === "ticketed" || d.status === "decision_record";
    if (frozen) return;
    const t = setInterval(load, d.engine_busy ? 2000 : 15000);
    return () => clearInterval(t);
  }, [d, load]);

  const rounds = useMemo(() => (d ? byRound(d.questions) : []), [d]);

  if (error && !d) return <div className="notice danger">{error}</div>;
  if (!d) return <p className="muted">載入中…</p>;

  const interviewing = d.status === "interviewing";
  const pending = d.questions.filter((q) => q.status === "pending");
  const myPending = pending.filter((q) => q.can_respond);
  const selectable = (q: Question) =>
    !meta?.single_user && d.is_requester && interviewing && q.status === "pending" && q.respondent === d.requester;

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function doHandoff() {
    await run(async () => {
      const res = await api.handoff(id, Array.from(selected), handoffTo, handoffNotify);
      setHandoffLink(res.link);
      setSelected(new Set());
    });
  }

  async function doFinish() {
    if (pending.length && !confirm(`還有 ${pending.length} 題未回答，會列為 Open Questions。確定要產出 Spec？`)) return;
    await run(() => api.finish(id));
  }

  return (
    <div className="stack">
      <div className="stack" style={{ gap: 6 }}>
        <div className="row">
          <span className="badge accent">{STATUS_LABEL[d.status]}</span>
          <span className="badge">{TYPE_LABEL[d.request_type]}</span>
          <span className="badge">{ROLE_LABEL[d.role]}</span>
          <span className="muted small">{d.template_label}</span>
        </div>
        <h1>{d.title}</h1>
        <span className="muted small">
          Requester {d.requester} · {new Date(d.created_at).toLocaleString("zh-TW")}
        </span>
      </div>

      <details className="card" open={d.questions.length === 0}>
        <summary style={{ cursor: "pointer" }}>
          <b>Request 原文</b>
          {d.attachments.length > 0 && <span className="muted small">（{d.attachments.length} 個附件）</span>}
        </summary>
        <div className="pre" style={{ marginTop: 10 }}>{d.request_text || "（無文字）"}</div>
        {d.attachments.length > 0 && (
          <div className="row" style={{ marginTop: 10 }}>
            {d.attachments.map((a) => (
              <a key={a.id} className="badge" href={`/api/interviews/${d.id}/attachments/${a.id}`} target="_blank" rel="noreferrer">
                📎 {a.filename}
              </a>
            ))}
          </div>
        )}
      </details>

      {d.summary && (
        <div className="notice info">
          <b>目前理解：</b>
          {d.summary}
        </div>
      )}

      {d.unknown_warning && interviewing && (
        <div className="notice warn">
          已有 {d.unknown_core_count} 題核心問題回答「不知道」，建議先釐清再開票（仍可送出）。
        </div>
      )}

      {rounds.map(([r, qs]) => (
        <section key={r} className="stack">
          <h2>第 {r} 輪</h2>
          {qs.map((q) => (
            <QuestionCard
              key={q.id}
              q={q}
              isRequester={d.is_requester}
              selectable={selectable(q)}
              selected={selected.has(q.id)}
              onToggle={() => {
                const next = new Set(selected);
                if (next.has(q.id)) next.delete(q.id);
                else next.add(q.id);
                setSelected(next);
              }}
              onChanged={load}
            />
          ))}
        </section>
      ))}

      {interviewing && d.engine_busy && (
        <div className="card row">
          <span className="spinner" /> AI 正在查閱 Knowledge Source 並出題…
        </div>
      )}
      {d.engine_error && (
        <div className="notice danger row">
          {d.engine_error}
          <span className="spacer" />
          {d.is_requester && <button onClick={() => run(() => api.retry(id))}>重試</button>}
        </div>
      )}
      {interviewing && d.engine_done && !d.engine_busy && (
        <div className="notice ok">AI 認為已經問完了，可以產出 Spec。</div>
      )}

      {d.new_terms.length > 0 && (
        <details className="card">
          <summary style={{ cursor: "pointer" }}>
            <b>New Terms</b> <span className="muted small">（{d.new_terms.length}，會列在 Spec 中交給 RD 決定是否收進詞彙表）</span>
          </summary>
          <ul>
            {d.new_terms.map((t) => (
              <li key={t.term}>
                <b>{t.term}</b>：{t.meaning}
                {t.conflict && <span className="badge warn" style={{ marginLeft: 6 }}>與 {t.conflict} 衝突</span>}
              </li>
            ))}
          </ul>
        </details>
      )}

      {d.handoffs.length > 0 && (
        <section className="stack">
          <h2>轉交</h2>
          <div className="card list" style={{ padding: 0 }}>
            {d.handoffs.map((h) => (
              <div key={h.id} className="item row" style={{ padding: "10px 14px" }}>
                <span className={`badge ${h.status === "open" ? "accent" : h.status === "completed" ? "ok" : ""}`}>
                  {h.status === "open" ? "等待回答" : h.status === "completed" ? "已回答" : "已收回"}
                </span>
                <span>{h.to}</span>
                {h.status === "open" && <span className="muted small">還有 {h.pending} 題 · 已提醒 {h.reminders_sent} 次</span>}
                <span className="spacer" />
                {d.is_requester && h.status === "open" && interviewing && (
                  <button className="link" onClick={() => run(() => api.recall(h.id))}>
                    收回
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {handoffLink && (
        <div className="notice ok row">
          已轉交。連結：<code>{handoffLink}</code>
          <button className="link" onClick={() => navigator.clipboard.writeText(handoffLink)}>
            複製
          </button>
        </div>
      )}

      {error && <div className="notice danger">{error}</div>}

      {d.status !== "interviewing" && <SpecPanel d={d} me={me} meta={meta} onChanged={load} />}

      {d.is_requester && interviewing && (
        <div className="sticky-bar stack">
          {selected.size > 0 ? (
            <div className="row">
              <span>轉交 {selected.size} 題給</span>
              <input
                type="email"
                placeholder="同事的 email，例如 kevin@linkervision.com"
                value={handoffTo}
                onChange={(e) => setHandoffTo(e.target.value)}
                style={{ flex: 1, width: "auto", minWidth: 200 }}
              />
              <label className="row small">
                <input type="checkbox" checked={handoffNotify} onChange={(e) => setHandoffNotify(e.target.checked)} />
                在 Teams 頻道 @對方
              </label>
              <button className="primary" disabled={busy || !handoffTo.includes("@")} onClick={doHandoff}>
                轉交
              </button>
              <button onClick={() => setSelected(new Set())}>取消</button>
            </div>
          ) : (
            <div className="row">
              <span className="muted small">
                {myPending.length > 0
                  ? meta?.single_user
                    ? `你還有 ${myPending.length} 題待回答。要問別人時，把題目複製給對方，再代為填入回答。`
                    : `你還有 ${myPending.length} 題待回答；勾選題目可轉交給同事。`
                  : pending.length > 0
                    ? `等待其他人回答 ${pending.length} 題。`
                    : d.engine_busy
                      ? "AI 出題中…"
                      : "目前沒有待回答的題目。"}
              </span>
              <span className="spacer" />
              <button className="primary" disabled={busy || d.engine_busy} onClick={doFinish}>
                夠了，產出 Spec
              </button>
            </div>
          )}
        </div>
      )}
      {!d.is_requester && interviewing && myPending.length === 0 && (
        <div className="notice ok">轉給你的題目都回答完了，謝謝！</div>
      )}
    </div>
  );
}
