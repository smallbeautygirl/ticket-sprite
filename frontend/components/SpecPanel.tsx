"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, InterviewDetail, Me, Meta, WORK_ITEM_TYPE, WorkItem } from "@/lib/api";
import Markdown from "./Markdown";
import PersonInput from "./PersonInput";
import Thinking from "./Thinking";

interface Props {
  d: InterviewDetail;
  me: Me | null;
  meta: Meta | null;
  onChanged: () => void;
}

// Azure DevOps Priority: how soon the team should pick it up (1 = most urgent)
const PRIORITY_LABEL: Record<number, string> = {
  1: "1 － 最高",
  2: "2 － 高",
  3: "3 － 中",
  4: "4 － 低",
};
const PRIORITY_HINT: Record<number, string> = {
  1: "必須優先處理：擋住上線、客戶已受影響或有合約時程，應立即排入目前 sprint。",
  2: "重要：應在本 sprint 或下個 sprint 完成。",
  3: "一般：排入 backlog，依團隊容量安排。",
  4: "可有可無：有空再做，延後也沒關係。",
};
// Azure DevOps Severity (Bug only): how bad the impact is, independent of urgency
const SEVERITY_HINT: Record<string, string> = {
  "1 - Critical": "系統掛掉、資料遺失，或沒有替代方案",
  "2 - High": "主要功能壞掉，替代方案很麻煩",
  "3 - Medium": "部分功能異常，有替代方案",
  "4 - Low": "外觀、文字或小瑕疵",
};

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
  const [assignee, setAssignee] = useState(d.assignee ?? "");
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
      <Thinking
        title="小精靈正在整理 Spec…"
        subtitle="把回答、Open Question 和 Assumption 寫成 Spec"
        progress={d.engine_progress}
      />
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
          <label className="field">
            <span>Assigned To（選填）</span>
            <PersonInput
              value={assignee}
              onChange={setAssignee}
              placeholder="輸入名字或 email 搜尋；留空則不指派"
            />
          </label>
          <div className="grid-2">
            <label className="field">
              <span>Priority（AI 建議 {d.suggested_priority ?? "-"}）</span>
              <select value={priority} onChange={(e) => setPriority(Number(e.target.value))}>
                {[1, 2, 3, 4].map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABEL[p]}
                  </option>
                ))}
              </select>
              <span className="small muted">{PRIORITY_HINT[priority]}</span>
            </label>
            {d.request_type === "bug" && (
              <label className="field">
                <span>Severity（AI 建議 {d.suggested_severity ?? "-"}）</span>
                <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  {(meta?.severities ?? []).map((s) => (
                    <option key={s} value={s}>
                      {s}（{SEVERITY_HINT[s] ?? ""}）
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {meta?.teams_enabled ? (
            <label className="row small">
              <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
              開票後通知 Teams 頻道
            </label>
          ) : (
            <span className="small muted">Teams 通知未設定（需要 TEAMS_WEBHOOK_URL），開票後不會發通知。</span>
          )}
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
                    assignee: assignee.trim() || null,
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
