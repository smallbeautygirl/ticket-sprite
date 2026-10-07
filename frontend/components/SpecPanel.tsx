"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, InterviewDetail, Me, Meta, WORK_ITEM_TYPE, WorkItem } from "@/lib/api";
import Markdown from "./Markdown";

interface Props {
  d: InterviewDetail;
  me: Me | null;
  meta: Meta | null;
  onChanged: () => void;
}

export default function SpecPanel({ d, me, meta, onChanged }: Props) {
  const [title, setTitle] = useState(d.title || "");
  const [markdown, setMarkdown] = useState(d.spec_markdown || "");
  const [editing, setEditing] = useState(false);
  const [parent, setParent] = useState<WorkItem | null>(null);
  const [parentId, setParentId] = useState<number | null>(d.default_parent_id);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<WorkItem[]>([]);
  const [priority, setPriority] = useState<number>(d.suggested_priority ?? 2);
  const [severity, setSeverity] = useState<string>(d.suggested_severity ?? "3 - Medium");
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const adoReady = !!me && (me.ado.connected || me.ado.dev_fallback) && !me.ado.expired;
  const dirty = title !== (d.title || "") || markdown !== (d.spec_markdown || "");

  useEffect(() => {
    setTitle(d.title || "");
    setMarkdown(d.spec_markdown || "");
  }, [d.title, d.spec_markdown]);

  useEffect(() => {
    if (!adoReady || !d.default_parent_id) return;
    api.searchWorkItems(String(d.default_parent_id)).then((r) => setParent(r[0] ?? null)).catch(() => {});
  }, [adoReady, d.default_parent_id]);

  async function search() {
    if (!query.trim()) return;
    try {
      setResults(await api.searchWorkItems(query));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const saveIfDirty = async () => {
    if (dirty) await api.saveSpec(d.id, title, markdown);
  };

  const frozen = d.status === "ticketed" || d.status === "decision_record";

  if (frozen) {
    return (
      <div className="stack">
        {d.status === "ticketed" && d.ticket_url && (
          <div className="notice ok">
            已開票：
            <a href={d.ticket_url} target="_blank" rel="noreferrer">
              #{d.ticket_id} {d.title}
            </a>
            {d.parent_id && <span className="muted">（Parent #{d.parent_id}）</span>}
          </div>
        )}
        {d.status === "decision_record" && (
          <div className="notice info">
            已存成 Decision Record，分享這個頁面的連結即可：
            <code style={{ marginLeft: 6 }}>{typeof window !== "undefined" ? window.location.href : ""}</code>
          </div>
        )}
        <div className="card">
          <h2 style={{ marginTop: 0 }}>{d.title}</h2>
          <Markdown text={d.spec_markdown || ""} />
        </div>
      </div>
    );
  }

  if (!d.spec_markdown) {
    return d.engine_busy ? (
      <div className="card row">
        <span className="spinner" /> AI 正在整理 Spec…
      </div>
    ) : null;
  }

  return (
    <div className="stack">
      <div className="card stack">
        <div className="row">
          <h2 style={{ margin: 0 }}>Spec 預覽</h2>
          <span className="spacer" />
          {d.is_requester && (
            <button onClick={() => setEditing(!editing)}>{editing ? "預覽" : "編輯"}</button>
          )}
        </div>
        <label className="field">
          <span>Ticket 標題</span>
          <input type="text" value={title} disabled={!d.is_requester} onChange={(e) => setTitle(e.target.value)} />
        </label>
        {editing ? (
          <textarea rows={24} value={markdown} onChange={(e) => setMarkdown(e.target.value)} style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }} />
        ) : (
          <Markdown text={markdown} />
        )}
        {d.is_requester && dirty && (
          <div className="row">
            <button disabled={busy} onClick={() => run(() => api.saveSpec(d.id, title, markdown))}>
              儲存修改
            </button>
          </div>
        )}
      </div>

      {d.is_requester && (
        <div className="card stack">
          <h2 style={{ margin: 0 }}>開票（{WORK_ITEM_TYPE[d.request_type]}）</h2>
          {!adoReady && (
            <div className="notice warn">
              還沒連結 Azure DevOps，<Link href="/settings">先到設定頁連結</Link>（約 1 分鐘）。
            </div>
          )}
          <div className="stack">
            <span className="muted small">Parent</span>
            <div className="row">
              {parentId ? (
                <span>
                  <b>#{parentId}</b> {parent?.id === parentId ? `${parent.title}（${parent.work_item_type}）` : ""}
                </span>
              ) : (
                <span className="muted">不掛 Parent</span>
              )}
              {parentId && (
                <button className="link" onClick={() => setParentId(null)}>
                  移除
                </button>
              )}
            </div>
            <div className="row">
              <input
                type="text"
                placeholder="輸入 work item id 或標題關鍵字，換一個 Parent"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
                style={{ flex: 1, width: "auto" }}
                disabled={!adoReady}
              />
              <button onClick={search} disabled={!adoReady}>
                搜尋
              </button>
            </div>
            {results.length > 0 && (
              <div className="card list" style={{ padding: 0 }}>
                {results.map((w) => (
                  <a
                    key={w.id}
                    className="item"
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      setParentId(w.id);
                      setParent(w);
                      setResults([]);
                    }}
                  >
                    <span className="badge">{w.work_item_type}</span>
                    <span className="title">
                      #{w.id} {w.title}
                    </span>
                    <span className="muted small">{w.state}</span>
                  </a>
                ))}
              </div>
            )}
          </div>
          <div className="grid-2">
            <label className="field">
              <span>Priority（AI 建議 {d.suggested_priority ?? "-"}）</span>
              <select value={priority} onChange={(e) => setPriority(Number(e.target.value))}>
                {[1, 2, 3, 4].map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            {d.request_type === "bug" && (
              <label className="field">
                <span>Severity（AI 建議 {d.suggested_severity ?? "-"}）</span>
                <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  {(meta?.severities ?? []).map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <label className="row small">
            <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
            開票後通知 Teams 頻道
          </label>
          {error && <div className="notice danger">{error}</div>}
          <div className="row">
            <button
              className="primary"
              disabled={busy || !adoReady || !title.trim()}
              onClick={() =>
                run(async () => {
                  await saveIfDirty();
                  await api.createTicket(d.id, {
                    title,
                    parent_id: parentId,
                    priority,
                    severity: d.request_type === "bug" ? severity : null,
                    notify,
                  });
                })
              }
            >
              {busy ? "處理中…" : "以我的身份開票"}
            </button>
            <button
              disabled={busy}
              onClick={() =>
                run(async () => {
                  await saveIfDirty();
                  await api.decisionRecord(d.id, title);
                })
              }
            >
              不開票，存成 Decision Record
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
