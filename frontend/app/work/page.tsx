"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, CurrentWork, Meta, WorkEntry, WorkPull } from "@/lib/api";

// Current Work, read by a PM: a strip of what is theirs to chase, then one row per person in RD with
// their tickets moving left to right (接下來 → 在做 → 測試中 → 完成). The interviewer reads the same tickets.

const PR_LABEL: Record<WorkPull["state"], string> = { open: "審查中", merged: "已合併", closed: "已關閉" };
const UNCLAIMED = "沒人接";
// Closed tickets a row shows before "還有 N 張"
const DONE_PREVIEW = 3;

const isActive = (e: WorkEntry) => e.state === "Active";
const isNew = (e: WorkEntry) => e.state === "New";
const isDone = (e: WorkEntry) => !!e.closed_on;
const isTesting = (e: WorkEntry) => !isActive(e) && !isNew(e) && !isDone(e);
const shortDate = (iso: string) => iso.slice(5).replace(/^0/, "").replace("-0", "/").replace("-", "/");

/** Where a ticket stands, in the words a PM would use to chase it. */
function standing(e: WorkEntry): string {
  if (isDone(e)) return `${shortDate(e.closed_on!)} 完成`;
  if (isTesting(e)) return "測試中，可以去試";
  if (isActive(e)) return e.assignee ? `${e.assignee.split(" ")[0]} 在做` : "在做";
  return e.assignee ? "排了，還沒開始" : "還沒人接";
}

interface Row {
  who: string;
  next: WorkEntry[];
  active: WorkEntry[];
  testing: WorkEntry[];
  done: WorkEntry[];
}

/** One row per person, busiest first; tickets nobody owns sit in the last row. */
function rows(items: WorkEntry[]): Row[] {
  const by = new Map<string, Row>();
  for (const e of items) {
    const who = e.assignee ?? UNCLAIMED;
    const row = by.get(who) ?? { who, next: [], active: [], testing: [], done: [] };
    (isDone(e) ? row.done : isActive(e) ? row.active : isNew(e) ? row.next : row.testing).push(e);
    by.set(who, row);
  }
  const open = (r: Row) => r.active.length + r.testing.length + r.next.length;
  return [...by.values()]
    .filter((r) => open(r) > 0 || r.done.length > 0)
    .sort(
      (a, b) =>
        Number(a.who === UNCLAIMED) - Number(b.who === UNCLAIMED) ||
        b.active.length - a.active.length ||
        open(b) - open(a),
    );
}

export default function WorkPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [product, setProduct] = useState("middleware");
  const [work, setWork] = useState<CurrentWork | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => undefined);
  }, []);

  useEffect(() => {
    setWork(null);
    setError(null);
    api
      .currentWork(product)
      .then(setWork)
      .catch((err: ApiError) => setError({ status: err.status, message: err.message }));
  }, [product, attempt]);

  const products = meta?.products ?? [];

  return (
    <div className="stack work">
      <h1>RD 在做什麼</h1>
      {products.length > 1 && (
        <div className="seg" role="group" aria-label="選擇 Product">
          {products.map((p) => (
            <button key={p.id} className={product === p.id ? "on" : ""} aria-pressed={product === p.id} onClick={() => setProduct(p.id)}>
              {p.label}
            </button>
          ))}
        </div>
      )}
      {error?.status === 409 && (
        <div className="notice warn" role="alert">
          要先連結 Azure DevOps 才看得到 RD 的票。<Link href="/settings">前往設定</Link>（約 1 分鐘）
        </div>
      )}
      {error && error.status !== 409 && (
        <div className="row notice danger" role="alert">
          <span>讀不到 RD 的票：{error.message}</span>
          <button onClick={() => setAttempt((n) => n + 1)}>重試</button>
        </div>
      )}
      {!work && !error && <p className="muted">小精靈正在翻 ADO 和 GitHub…</p>}
      {work && <Board work={work} />}
    </div>
  );
}

function Board({ work }: { work: CurrentWork }) {
  const mine = work.items.filter((e) => e.mine && !isDone(e));
  const testing = work.items.filter(isTesting);
  const unclaimed = work.items.filter((e) => isNew(e) && !e.assignee);
  const table = rows(work.items);

  return (
    <>
      <section className="card work-chase" aria-labelledby="chase">
        <h2 id="chase">你可以去追的</h2>
        {mine.length > 0 && (
          <span>
            <strong>你提的 {mine.length} 張</strong>：
            {mine.map((e, i) => (
              <span key={e.id}>
                {i > 0 && "、"}
                <a href={e.url} target="_blank" rel="noreferrer">#{e.id}</a> {standing(e)}
              </span>
            ))}
          </span>
        )}
        {testing.length > 0 && (
          <span>
            <strong>{testing.length} 張測試中</strong>，可以去試
          </span>
        )}
        {unclaimed.length > 0 && <span className="badge warn">{unclaimed.length} 張沒人接，可能已經不需要</span>}
        {mine.length + testing.length + unclaimed.length === 0 && (
          <span className="muted">目前沒有要你追的事，小精靈會繼續盯著。</span>
        )}
      </section>

      {table.length === 0 ? (
        <p className="muted">#{work.parent_id} 底下目前沒有票。</p>
      ) : (
        <div className="card work-table-box">
          <table className="work-table">
            <caption>每一列是一個人，由左到右是票往前走的方向。{mine.length > 0 && "框起來的是你提的需求。"}</caption>
            <thead>
              <tr>
                <th scope="col" className="who">
                  <span className="sr-only">負責人</span>
                </th>
                <th scope="col">接下來</th>
                <th scope="col" className="doing">在做</th>
                <th scope="col">測試中</th>
                <th scope="col" className="done">最近 {work.closed_days} 天完成</th>
              </tr>
            </thead>
            <tbody>
              {table.map((r) => (
                <WorkRow key={r.who} row={r} unclaimed={r.who === UNCLAIMED ? unclaimed : []} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="muted small">
        資料來自 <a href={work.parent_url} target="_blank" rel="noreferrer">#{work.parent_id}</a> 底下的 ADO 票
        {work.github ? "，以及內文寫了 AB# 的 GitHub PR" : "（還沒設定 GitHub，看不到 PR）"}，每 10 分鐘更新。
      </p>
    </>
  );
}

function WorkRow({ row: r, unclaimed }: { row: Row; unclaimed: WorkEntry[] }) {
  const [allDone, setAllDone] = useState(false);
  const summary = [
    r.active.length && `在做 ${r.active.length}`,
    r.testing.length && `測試 ${r.testing.length}`,
    r.next.length && `排隊 ${r.next.length}`,
  ]
    .filter(Boolean)
    .join(" · ");
  const done = allDone ? r.done : r.done.slice(0, DONE_PREVIEW);
  const queued = unclaimed.length ? [] : r.next;

  return (
    <tr>
      <th scope="row" className="who">
        <span className="name">{r.who}</span>
        {summary && <span className="sum">{summary}</span>}
      </th>
      <td>
        <div className="work-cell">
          {queued.map((e) => (
            <Ticket key={e.id} entry={e} tone="quiet" />
          ))}
          {unclaimed.length > 0 && (
            <details className="work-unclaimed">
              <summary>
                {unclaimed.length} 張還沒人接，可能已經不需要了
                <span>到 ADO 清掉或排進來</span>
              </summary>
              <ul>
                {unclaimed.map((e) => (
                  <li key={e.id}>
                    <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a> <span className="work-id">#{e.id}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </td>
      <td className="doing">
        <div className="work-cell">
          {r.active.map((e) => (
            <Ticket key={e.id} entry={e} tone="raised" />
          ))}
        </div>
      </td>
      <td>
        <div className="work-cell">
          {r.testing.map((e) => (
            <Ticket key={e.id} entry={e} tone="quiet" note="可以去試" />
          ))}
        </div>
      </td>
      <td className="done">
        <div className="work-done">
          {done.map((e) => (
            <a key={e.id} href={e.url} target="_blank" rel="noreferrer">
              {e.title} <span>{shortDate(e.closed_on!)}</span>
            </a>
          ))}
          {r.done.length > DONE_PREVIEW && (
            <button className="link small" aria-expanded={allDone} onClick={() => setAllDone((v) => !v)}>
              {allDone ? "收起" : `還有 ${r.done.length - DONE_PREVIEW} 張`}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function Ticket({ entry: e, tone, note }: { entry: WorkEntry; tone: "quiet" | "raised"; note?: string }) {
  return (
    <div className={`work-ticket ${tone}${e.mine ? " mine" : ""}`}>
      <a href={e.url} target="_blank" rel="noreferrer" className="work-title">
        {e.title}
      </a>
      <span className="work-meta">
        <span className="work-id">#{e.id}</span>
        {e.prs.map((p) => (
          <a key={`${p.repo}#${p.number}`} href={p.url} target="_blank" rel="noreferrer" title={`${p.repo}：${p.title}`} className={`pr ${p.state}`}>
            PR #{p.number} {PR_LABEL[p.state]}
          </a>
        ))}
        {note && <span>{note}</span>}
        {e.mine && (e.interview_id ? <Link href={`/interviews/${e.interview_id}`}>你提的 · 看問答</Link> : <span>你提的</span>)}
      </span>
    </div>
  );
}
