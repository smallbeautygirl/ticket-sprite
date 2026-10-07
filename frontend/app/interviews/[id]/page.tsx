"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, deleteConfirmText, InterviewDetail, Me, Meta, Question, ROLE_LABEL, STATUS_LABEL, TYPE_LABEL } from "@/lib/api";
import QuestionCard from "@/components/QuestionCard";
import Markdown from "@/components/Markdown";
import SpecPanel from "@/components/SpecPanel";
import Sprite from "@/components/Sprite";
import Thinking from "@/components/Thinking";
import { announceReady } from "@/lib/ready";

const ANSWERED = new Set(["answered", "confirmed", "corrected"]);

function Stepper({ status }: { status: InterviewDetail["status"] }) {
  const steps = ["Request", "拷問", "Spec", status === "decision_record" ? "Decision Record" : "ADO 票"];
  const now = status === "interviewing" ? 1 : status === "spec_draft" ? 2 : 4;
  return (
    <ol className="stepper" aria-label="進度">
      {steps.map((label, i) => (
        <li key={label} className={i < now ? "done" : i === now ? "now" : ""} aria-current={i === now ? "step" : undefined}>
          <span className="bar" />
          {i + 1} · {label}
        </li>
      ))}
    </ol>
  );
}

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
  const router = useRouter();
  const [d, setD] = useState<InterviewDetail | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [handoffTo, setHandoffTo] = useState("");
  const [handoffNotify, setHandoffNotify] = useState(true);
  const [handoffLink, setHandoffLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

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
    if (frozen && !d.engine_busy) return; // a ticketed Spec can still be regenerated
    const t = setInterval(() => {
      // A background tab keeps polling only while the sprite works, so it can say when it is done
      if (!document.hidden || d.engine_busy) load();
    }, d.engine_busy ? 2000 : 15000);
    return () => clearInterval(t);
  }, [d, load]);

  useEffect(() => {
    const onVisible = () => !document.hidden && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load]);

  const rounds = useMemo(() => (d ? byRound(d.questions) : []), [d]);

  // The sprite just finished: tell someone who went to another tab
  const before = useRef<InterviewDetail | null>(null);
  useEffect(() => {
    const prev = before.current;
    before.current = d;
    if (!d || !prev?.engine_busy || d.engine_busy) return;
    const mine = d.questions.filter((q) => q.status === "pending" && q.can_respond).length;
    if (d.engine_error) announceReady("小精靈卡住了，回來看看");
    else if (d.spec_revision && !prev.spec_revision) announceReady("新版 Spec 好了");
    else if (d.status !== "interviewing" && d.spec_markdown && !prev.spec_markdown) announceReady("Spec 好了");
    else if (mine > 0) announceReady(`題目來了（${mine}）`);
    else if (d.engine_done) announceReady("問完了，可以產出 Spec");
  }, [d]);

  if (error && !d) return <div className="notice danger" role="alert">{error}</div>;
  if (!d) return <p className="muted">載入中…</p>;

  const interviewing = d.status === "interviewing";
  const pending = d.questions.filter((q) => q.status === "pending");
  const myPending = pending.filter((q) => q.can_respond);
  // In the order shown (premises first in each round): the first one still waiting for me
  const done = interviewing && d.engine_done && !d.engine_busy;
  const currentId = rounds.flatMap(([, qs]) => qs).find((q) => q.status === "pending" && q.can_respond)?.id;
  const live = d.questions.filter((q) => q.status !== "withdrawn");
  const tally = {
    answered: live.filter((q) => ANSWERED.has(q.status)).length,
    open: live.filter((q) => q.status === "unknown").length,
    assumed: live.filter((q) => q.status === "skipped").length,
  };
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
      setCopied(false);
      setSelected(new Set());
    });
  }

  // navigator.clipboard only exists on https or localhost; the VM is served over plain http
  async function copyLink(text: string) {
    try {
      if (navigator.clipboard) await navigator.clipboard.writeText(text);
      else {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        area.remove();
        if (!ok) throw new Error();
      }
      setCopied(true);
    } catch {
      setError("無法自動複製，請手動選取上面的連結。");
    }
  }

  async function doDelete() {
    if (!d || !confirm(deleteConfirmText({ title: d.title, ticket_id: d.ticket_id }))) return;
    await run(async () => {
      await api.deleteInterview(id);
      router.push("/");
    });
  }

  async function doStop() {
    if (!confirm("要停止小精靈嗎？這一輪的進度會丟掉，之後可以按「重試」重新開始。")) return;
    await run(() => api.stop(id));
  }

  async function doFinish() {
    if (pending.length && !confirm(`還有 ${pending.length} 題未回答，會列為 Open Questions。確定要產出 Spec？`)) return;
    await run(() => api.finish(id));
  }

  return (
    <div className="stack interview" style={{ gap: 20 }}>
      <div className="stack" style={{ gap: 6 }}>
        <div className="row">
          <span className="badge accent">{STATUS_LABEL[d.status]}</span>
          <span className="badge">{TYPE_LABEL[d.request_type]}</span>
          <span className="badge">{ROLE_LABEL[d.role]}</span>
          <span className="badge">
            To {ROLE_LABEL[d.audience]}
            {d.assignee ? ` · ${d.assignee.split("@")[0]}` : ""}
          </span>
          <span className="muted small">Template · {d.template_label}</span>
          <span className="spacer" />
          {d.is_requester && (
            <button
              className="link danger small"
              disabled={busy}
              onClick={doDelete}
            >
              刪除
            </button>
          )}
        </div>
        <h1>{d.title}</h1>
        <span className="muted small">
          Requester {d.requester} · {new Date(d.created_at).toLocaleString("zh-TW")}
        </span>
      </div>

      <Stepper status={d.status} />

      <div className="interview-cols">
      <div className="interview-main stack">

      <details className="card" open={d.questions.length === 0}>
        <summary style={{ cursor: "pointer" }}>
          <b>需求原文</b>
          {d.attachments.length > 0 && <span className="muted small">（{d.attachments.length} 個附件）</span>}
        </summary>
        <div className="pre" style={{ marginTop: 10 }}>{d.request_text || "（無文字）"}</div>
        {d.attachments.length > 0 && (
          <div className="row" style={{ marginTop: 10 }}>
            {d.attachments.map((a) => (
              <a key={a.id} className="badge" href={`/api/interviews/${d.id}/attachments/${a.id}`} target="_blank" rel="noreferrer">
                {a.filename}
              </a>
            ))}
          </div>
        )}
      </details>

      {d.summary && (
        <div className="notice info stack" style={{ gap: 2 }}>
          <b className="small" style={{ color: "var(--accent-strong)" }}>小精靈目前的理解</b>
          <span><Markdown inline text={d.summary} /></span>
        </div>
      )}

      {d.unknown_warning && interviewing && (
        <div className="notice warn">
          已有 {d.unknown_core_count} 題核心問題回答「不知道」，建議先釐清再開票（仍可送出）。
        </div>
      )}

      {rounds.map(([r, qs]) => (
        <section key={r} className="stack">
          <div className="row" style={{ alignItems: "baseline", gap: 12, marginTop: 12 }}>
            <h2 style={{ margin: 0 }}>第 {r} 輪</h2>
            <span className="muted small">
              {qs.filter((q) => q.status !== "withdrawn").length} 題 · 已回答 {qs.filter((q) => q.status !== "pending" && q.status !== "withdrawn").length}
            </span>
          </div>
          {qs.map((q) => (
            <QuestionCard
              key={q.id}
              q={q}
              isRequester={d.is_requester}
              selectable={selectable(q)}
              current={q.id === currentId}
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
        <>
          <Thinking
            title="小精靈正在翻書找資料…"
            subtitle={`查閱 Knowledge Source，準備第 ${(rounds.length ? rounds[rounds.length - 1][0] : 0) + 1} 輪問題`}
            progress={d.engine_progress}
            onStop={d.is_requester ? doStop : undefined}
          />
          {d.questions.length === 0 && (
            <div className="stack" aria-hidden="true">
              {[0, 1].map((i) => (
                <div key={i} className="card stack" style={{ gap: 12 }}>
                  <div className="sk" style={{ width: 90, height: 16 }} />
                  <div className="sk" style={{ width: "65%", height: 20 }} />
                  <div className="sk" style={{ width: "90%", height: 12 }} />
                </div>
              ))}
            </div>
          )}
        </>
      )}
      {d.engine_error && (
        <div className="notice danger row" role="alert">
          {d.engine_error}
          <span className="spacer" />
          {d.is_requester && <button onClick={() => run(() => api.retry(id))}>重試</button>}
        </div>
      )}
      {done && (
        <div className="card done-card" role="status">
          <span className="hop" aria-hidden="true">
            <Sprite pose="ticket" size={76} />
          </span>
          <div className="stack" style={{ gap: 4, flex: "1 1 200px", minWidth: 0 }}>
            <h3>{d.question_budget !== null && d.questions_asked >= d.question_budget ? "題數問滿了！" : "問完了！"}</h3>
            <span className="small" style={{ color: "var(--text-2)" }}>
              {d.question_budget !== null && d.questions_asked >= d.question_budget
                ? `已經問滿 ${d.question_budget} 題，可以產出 Spec 了。沒問到的部分會寫成 Assumption 或 Open Question。`
                : "小精靈認為已經問完了，可以產出 Spec。"}
            </span>
          </div>
          {d.is_requester && (
            <button className="primary" disabled={busy} onClick={doFinish}>
              產出 Spec
            </button>
          )}
        </div>
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
          <button className="link" onClick={() => copyLink(handoffLink)}>
            {copied ? "已複製" : "複製"}
          </button>
        </div>
      )}

      {error && <div className="notice danger" role="alert">{error}</div>}

      {d.status !== "interviewing" && <SpecPanel d={d} me={me} meta={meta} onChanged={load} onStop={doStop} />}

      {d.is_requester && interviewing && (!done || selected.size > 0) && (
        <div className="sticky-bar stack">
          {selected.size > 0 ? (
            <div className="row">
              <span>轉交 {selected.size} 題給</span>
              <input
                type="email"
                aria-label="轉交對象的 email"
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
        <div className="notice ok with-sprite">
          <Sprite pose="ticket" size={56} />
          轉給你的題目都回答完了，謝謝！
        </div>
      )}
      </div>

      <aside className="interview-aside stack">
        <section className="card stack">
          <div className="row" style={{ alignItems: "baseline" }}>
            <h2 style={{ fontSize: 17 }}>Spec 成形中</h2>
            <span className="spacer" />
            <span className="muted small">
              {d.question_budget === 0
                ? "不拷問，直接寫 Spec"
                : d.question_budget
                  ? `已問 ${d.questions_asked}／最多 ${d.question_budget} 題`
                  : `已問 ${d.questions_asked} 題`}
            </span>
          </div>
          {!!d.question_budget && (
            <div
              className="budget-bar"
              role="progressbar"
              aria-label="題數"
              aria-valuemin={0}
              aria-valuemax={d.question_budget}
              aria-valuenow={d.questions_asked}
            >
              <span style={{ width: `${Math.min(100, (d.questions_asked / d.question_budget) * 100)}%` }} />
            </div>
          )}
          <div className="tally">
            <div className={tally.answered ? "ok" : ""}>
              <b>{tally.answered}</b>
              <span>Answer</span>
            </div>
            <div className={tally.open ? "warn" : ""}>
              <b>{tally.open}</b>
              <span>Open</span>
            </div>
            <div>
              <b>{tally.assumed}</b>
              <span>Assumption</span>
            </div>
          </div>
          {live.length > 0 ? (
            <ul className="qlist">
              {live.map((q) => (
                <li key={q.id}>
                  <span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted)" }}>{q.ref}</span> {q.title}
                  </span>
                  {q.status === "pending" ? (
                    q.can_respond ? (
                      <span style={{ color: "var(--warn)" }}>待回答</span>
                    ) : (
                      <span className="muted">{q.respondent.split("@")[0]}</span>
                    )
                  ) : q.status === "unknown" ? (
                    <span style={{ color: "var(--warn)" }}>Open</span>
                  ) : q.status === "skipped" ? (
                    <span className="muted">Assumption</span>
                  ) : (
                    <span style={{ color: "var(--ok)" }}>已回答</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small" style={{ margin: 0 }}>
              回答越多，Spec 越完整。答不出來就選「不知道」，會列為 Open Question 交給 RD。
            </p>
          )}
        </section>

        {d.new_terms.length > 0 && (
          <section className="card stack" style={{ gap: 8 }}>
            <h2 style={{ fontSize: 17 }}>New Terms</h2>
            <span className="muted small">會列在 Spec 中，交給 RD 決定是否收進詞彙表</span>
            {d.new_terms.map((t) => (
              <div key={t.term} className="stack" style={{ gap: 2, padding: "8px 12px", borderRadius: "var(--radius-sm)", background: "var(--surface-2)" }}>
                <b>{t.term}</b>
                <span className="small" style={{ color: "var(--text-2)" }}><Markdown inline text={t.meaning} /></span>
                {t.conflict && (
                  <div className="term-conflict small">
                    <b>⚠ 詞彙衝突</b> <Markdown inline text={t.conflict.replace(/^與\s*/, "")} />
                  </div>
                )}
              </div>
            ))}
          </section>
        )}
      </aside>
      </div>
    </div>
  );
}
