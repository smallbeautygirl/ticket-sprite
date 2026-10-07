"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, InterviewDetail, Me, Meta, WORK_ITEM_TYPE, WorkItem } from "@/lib/api";
import Markdown from "./Markdown";
import PersonInput from "./PersonInput";
import Thinking from "./Thinking";

/** Opened inside the click so the browser allows it; pointed at the ticket once ADO has created it. */
function openPendingTab(): Window | null {
  const tab = window.open("", "_blank");
  if (!tab) return null;
  tab.opener = null; // the ADO page must not reach back into this one
  tab.document.title = "開票中…";
  tab.document.body.innerHTML =
    '<p style="font:16px sans-serif;color:#33463a;padding:64px 24px;text-align:center">' +
    "開票中…<br>完成後會自動打開 Azure DevOps 上的票。</p>";
  return tab;
}

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
  const [lookup, setLookup] = useState<"idle" | "busy" | "done">("idle"); // the free search for a Parent
  const [boardParents, setBoardParents] = useState<WorkItem[]>([]);
  const [searching, setSearching] = useState(false); // the free search for a Parent off the board
  const [priority, setPriority] = useState<number>(d.suggested_priority ?? 2);
  const [severity, setSeverity] = useState<string>(d.suggested_severity ?? "3 - Medium");
  const [assignee, setAssignee] = useState(d.assignee ?? "");
  const [wiType, setWiType] = useState<string | null>(null); // null = the default for this Request Type
  const ticketType = wiType ?? meta?.default_work_item_type[d.request_type] ?? WORK_ITEM_TYPE[d.request_type];
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
    if (!adoReady) return;
    api.boardParents().then(setBoardParents).catch(() => {});
    if (d.default_parent_id) {
      api.searchWorkItems(String(d.default_parent_id)).then((r) => setParent(r[0] ?? null)).catch(() => {});
    }
  }, [adoReady, d.default_parent_id]);

  // The chosen Parent stays selectable even when it isn't on the board (default or searched)
  const parentOptions = [...boardParents];
  if (parent && !parentOptions.some((w) => w.id === parent.id)) parentOptions.unshift(parent);

  async function search() {
    if (!query.trim() || lookup === "busy") return;
    setLookup("busy");
    setError(null);
    try {
      setResults(await api.searchWorkItems(query));
      setLookup("done");
    } catch (err) {
      setError((err as Error).message);
      setLookup("idle");
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
  const rewriting = d.engine_busy && !!d.spec_markdown;

  function regenerate() {
    const warn = d.status === "ticketed"
      ? "用最新的規則重新產出 Spec？\n新版會先給你看，確認後才會更新 ADO 票的描述。"
      : d.status === "decision_record"
        ? "用最新的規則重新產出 Spec？\n新版會先給你看，確認後才會取代這份 Decision Record。"
      : "用最新的規則重新產出 Spec？\n目前的內容（包含你手動改過的地方）會被取代。";
    if (confirm(warn)) run(() => api.regenerateSpec(d.id));
  }

  function applyRevision() {
    run(async () => {
      try {
        await api.applySpecRevision(d.id, false);
      } catch (err) {
        // 409: the description was edited in ADO after the ticket was opened
        if (!(err instanceof ApiError && err.status === 409)) throw err;
        if (!confirm(`${err.message}\n\n仍要更新嗎？`)) return;
        await api.applySpecRevision(d.id, true);
      }
    });
  }

  const rewritingCard = rewriting && (
    <Thinking
      title="小精靈正在重新產出 Spec…"
      subtitle={
        d.status === "ticketed"
          ? "完成後會先給你看，確認了才更新 ADO 票"
          : frozen
            ? "完成後會先給你看，確認了才取代這份 Decision Record"
            : "完成後會取代目前的 Spec 草稿"
      }
      progress={d.engine_progress}
    />
  );

  if (frozen) {
    return (
      <div className="stack">
        {d.status === "ticketed" && d.ticket_url && (
          <div className="notice ok">
            已開成 {d.ticket_type ?? "ADO 票"}：
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
        {rewritingCard}
        {d.spec_revision && !rewriting && (
          <div className="card stack revision">
            <div className="row">
              <h2 style={{ margin: 0 }}>新版 Spec</h2>
              <span className="badge warn">{d.status === "ticketed" ? "尚未更新到 ADO" : "尚未採用"}</span>
            </div>
            <Markdown text={d.spec_revision} />
            {error && <div className="notice danger" role="alert">{error}</div>}
            <div className="row">
              <button className="primary" disabled={busy} onClick={applyRevision}>
                {busy ? "更新中…" : d.status === "ticketed" ? `更新 ADO #${d.ticket_id} 的描述` : "採用新版"}
              </button>
              <button disabled={busy} onClick={() => run(() => api.discardSpecRevision(d.id))}>
                放棄新版
              </button>
            </div>
          </div>
        )}
        <div className="card stack">
          <div className="row">
            <h2 style={{ margin: 0 }}>{d.title}</h2>
            <span className="spacer" />
            {d.is_requester && !d.spec_revision && (
              <button disabled={busy || d.engine_busy} onClick={regenerate}>
                重新產出 Spec
              </button>
            )}
          </div>
          {d.spec_revision && (
            <span className="muted small">{d.status === "ticketed" ? "目前 ADO 上的版本：" : "目前的版本："}</span>
          )}
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
      {rewritingCard}
      <div className="card stack">
        <div className="row">
          <h2 style={{ margin: 0 }}>Spec 預覽</h2>
          <span className="spacer" />
          {d.is_requester && (
            <>
              <button disabled={busy || d.engine_busy} onClick={regenerate}>
                重新產出
              </button>
              <button onClick={() => setEditing(!editing)}>{editing ? "預覽" : "編輯"}</button>
            </>
          )}
        </div>
        <label className="field">
          <span>Ticket 標題</span>
          <input type="text" value={title} disabled={!d.is_requester} onChange={(e) => setTitle(e.target.value)} />
        </label>
        {editing ? (
          <textarea rows={24} value={markdown} onChange={(e) => setMarkdown(e.target.value)} style={{ fontFamily: "var(--font-mono)", fontSize: 13 }} />
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
          <h2 style={{ margin: 0 }}>開票（{ticketType}）</h2>
          {!adoReady && (
            <div className="notice warn">
              還沒連結 Azure DevOps，<Link href="/settings">先到設定頁連結</Link>（約 1 分鐘）。
            </div>
          )}
          <div className="stack" style={{ gap: 6 }}>
            <label className="field">
              <span>Parent（看板「目前 iteration」上的 User Story）</span>
              <select
                value={parentId ?? ""}
                disabled={!adoReady}
                onChange={(e) => {
                  const id = e.target.value ? Number(e.target.value) : null;
                  setParentId(id);
                  setParent(parentOptions.find((w) => w.id === id) ?? null);
                }}
              >
                <option value="">不掛 Parent</option>
                {parentId && !parentOptions.some((w) => w.id === parentId) && (
                  <option value={parentId}>#{parentId}</option>
                )}
                {parentOptions.map((w) => (
                  <option key={w.id} value={w.id}>
                    #{w.id} {w.title}
                    {w.work_item_type !== "User Story" ? `（${w.work_item_type}）` : ""}
                    {w.state && w.state !== "New" ? ` · ${w.state}` : ""}
                  </option>
                ))}
              </select>
            </label>
            {!searching ? (
              <button className="link small" style={{ alignSelf: "flex-start" }} disabled={!adoReady} onClick={() => setSearching(true)}>
                找不到？搜尋其他 work item
              </button>
            ) : (
              <>
                <div className="row">
                  <input
                    type="text"
                    autoFocus
                    aria-label="搜尋 Parent work item"
                    placeholder="輸入 work item id 或標題關鍵字"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setResults([]);
                      setLookup("idle");
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") search();
                      if (e.key === "Escape") {
                        setResults([]);
                        setSearching(false);
                      }
                    }}
                    style={{ flex: 1, width: "auto" }}
                  />
                  <button onClick={search} disabled={lookup === "busy" || !query.trim()}>
                    {lookup === "busy" ? "搜尋中…" : "搜尋"}
                  </button>
                  <button
                    className="link small"
                    onClick={() => {
                      setResults([]);
                      setSearching(false);
                    }}
                  >
                    取消
                  </button>
                </div>
                {lookup === "done" && results.length === 0 && (
                  <span className="muted small" role="status">
                    找不到符合「{query.trim()}」的 work item，換個關鍵字或直接輸入 id 試試。
                  </span>
                )}
                {results.length > 0 && (
                  <div className="card list" style={{ padding: 0 }}>
                    {results.map((w) => (
                      <button
                        key={w.id}
                        type="button"
                        className="item"
                        onClick={() => {
                          setParentId(w.id);
                          setParent(w);
                          setResults([]);
                          setSearching(false);
                        }}
                      >
                        <span className="badge">{w.work_item_type}</span>
                        <span className="title">
                          #{w.id} {w.title}
                        </span>
                        <span className="muted small">{w.state}</span>
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
          <div className="row">
            <span className="muted small">票的類型</span>
            <div className="seg" role="group" aria-label="票的類型">
              {(meta?.work_item_types ?? ["Task", "User Story", "Bug"]).map((t) => (
                <button key={t} className={ticketType === t ? "on" : ""} aria-pressed={ticketType === t} onClick={() => setWiType(t)}>
                  {t}
                </button>
              ))}
            </div>
            <span className="muted small">
              {ticketType === "Task"
                ? "一般需求開 Task，掛在 Parent（User Story）底下。"
                : ticketType === "User Story"
                  ? "完整的新功能才開 User Story，Parent 應該選 Feature。"
                  : "Bug 會多帶 Severity 和 Repro Steps。"}
            </span>
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
            {ticketType === "Bug" && (
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
          {error && <div className="notice danger" role="alert">{error}</div>}
          <div className="row">
            <button
              className="primary"
              disabled={busy || !adoReady || !title.trim()}
              onClick={() => {
                const tab = openPendingTab();
                run(async () => {
                  try {
                    await saveIfDirty();
                    const created = await api.createTicket(d.id, {
                      title,
                      parent_id: parentId,
                      priority,
                      severity: ticketType === "Bug" ? severity : null,
                      notify,
                      assignee: assignee.trim() || null,
                      work_item_type: ticketType,
                    });
                    tab?.location.replace(created.ticket_url);
                  } catch (err) {
                    tab?.close();
                    throw err;
                  }
                });
              }}
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
