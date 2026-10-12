"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Sprite from "@/components/Sprite";
import { api, ApiError, CurrentWork, Meta, WorkEntry, WorkPull } from "@/lib/api";

// Current Work, read by a PM: first what is theirs to chase, then who in RD is doing what.
// The interviewer reads the same tickets and points out a Request that overlaps one.

// A chase group shows this many before "再看 N 張", so the card reads at a glance
const CHASE_PREVIEW = 4;

const PR_LABEL: Record<WorkPull["state"], string> = { open: "審查中", merged: "已合併", closed: "已關閉" };
const PR_BADGE: Record<WorkPull["state"], string> = { open: "accent", merged: "ok", closed: "" };

const isActive = (e: WorkEntry) => e.state === "Active";
const isNew = (e: WorkEntry) => e.state === "New";
const isDone = (e: WorkEntry) => !!e.closed_on;
const isTesting = (e: WorkEntry) => !isActive(e) && !isNew(e) && !isDone(e);

/** Where a ticket stands, in the words a PM would use to chase it. */
function standing(e: WorkEntry): string {
  if (isDone(e)) return `${e.closed_on!.slice(5).replace("-", "/")} 完成`;
  if (isTesting(e)) return "測試中，可以去試";
  if (isActive(e)) return e.assignee ? `${e.assignee} 在做` : "在做，但沒指派";
  return e.assignee ? `${e.assignee} 排了，還沒開始` : "還沒人接";
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
  const items = work.items;
  const active = items.filter(isActive);
  const testing = items.filter(isTesting);
  const queued = items.filter(isNew);
  const done = items.filter(isDone);
  const mine = items.filter((e) => e.mine);
  const unclaimed = queued.filter((e) => !e.assignee);
  const people = lanes(active);

  return (
    <>
      <p className="work-lead">
        {people.length} 個人手上有 <strong>{active.length}</strong> 張在做、<strong>{testing.length}</strong> 張測試中，
        另外 <strong>{queued.length}</strong> 張排隊還沒開始。
      </p>

      <section className="card work-chase" aria-labelledby="chase">
        <h2 id="chase">你可以去追的</h2>
        {mine.length + testing.length + unclaimed.length === 0 ? (
          <div className="row">
            <Sprite pose="head" size={44} />
            <span className="muted">目前沒有要你追的事，小精靈會繼續盯著。</span>
          </div>
        ) : (
          <div className="work-chase-groups">
            <ChaseGroup
              title="你提的需求"
              hint="從小精靈開的票現在到哪了"
              rows={mine}
              empty="你還沒從小精靈開過這個 Product 的票。"
              note={(e) => standing(e)}
            />
            <ChaseGroup
              title="測試中，可以去試"
              hint="PR 合併了，等人驗收"
              rows={testing}
              empty="現在沒有在測試的票。"
            />
            <ChaseGroup
              title="還沒人接"
              hint="要排進來的話，找 RD 討論優先順序"
              rows={unclaimed}
              empty="排隊的票都有人了。"
              warn
            />
          </div>
        )}
      </section>

      <section className="stack" aria-labelledby="lanes" style={{ gap: 8 }}>
        <h2 id="lanes">誰在做什麼</h2>
        {people.length === 0 ? (
          <p className="muted">現在沒有 Active 的票。</p>
        ) : (
          <div className="work-lanes">
            {people.map(([who, rows]) => (
              <div key={who} className="card work-lane">
                <h3>
                  {who} <span className="muted small">{rows.length} 張</span>
                </h3>
                <ul className="work-items">
                  {rows.map((e) => (
                    <WorkItem key={e.id} entry={e} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      {queued.length > 0 && (
        <details className="advanced work-more">
          <summary>
            排隊中，還沒開始 <span className="muted small">{queued.length} 張</span>
          </summary>
          <ul className="work-items">
            {queued.map((e) => (
              <WorkItem key={e.id} entry={e} note={e.assignee ?? "還沒人接"} />
            ))}
          </ul>
        </details>
      )}
      {done.length > 0 && (
        <details className="advanced work-more">
          <summary>
            最近 {work.closed_days} 天完成 <span className="muted small">{done.length} 張</span>
          </summary>
          <ul className="work-items">
            {done.map((e) => (
              <WorkItem key={e.id} entry={e} note={standing(e)} />
            ))}
          </ul>
        </details>
      )}

      <p className="muted small">
        資料來自 <a href={work.parent_url} target="_blank" rel="noreferrer">#{work.parent_id}</a> 底下的 ADO 票
        {work.github ? "，以及內文寫了 AB# 的 GitHub PR" : "（還沒設定 GitHub，看不到 PR）"}，每 10 分鐘更新。
      </p>
    </>
  );
}

/** Active tickets per person, busiest first; tickets nobody owns sit last. */
function lanes(active: WorkEntry[]): [string, WorkEntry[]][] {
  const by = new Map<string, WorkEntry[]>();
  for (const e of active) {
    const who = e.assignee ?? "未指派";
    by.set(who, [...(by.get(who) ?? []), e]);
  }
  return [...by.entries()].sort(
    ([a, x], [b, y]) => Number(a === "未指派") - Number(b === "未指派") || y.length - x.length,
  );
}

function ChaseGroup(props: {
  title: string;
  hint: string;
  rows: WorkEntry[];
  empty: string;
  note?: (e: WorkEntry) => string;
  warn?: boolean;
}) {
  const { title, hint, rows, empty, note, warn } = props;
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, CHASE_PREVIEW);
  return (
    <div className="work-chase-group">
      <h3>
        {title} <span className={`badge ${warn && rows.length ? "warn" : ""}`}>{rows.length}</span>
      </h3>
      <p className="muted small">{hint}</p>
      {rows.length === 0 ? (
        <p className="muted small">{empty}</p>
      ) : (
        <>
          <ul className="work-items">
            {shown.map((e) => (
              <WorkItem key={e.id} entry={e} note={note?.(e) ?? e.assignee ?? undefined} />
            ))}
          </ul>
          {rows.length > CHASE_PREVIEW && (
            <button className="link small" aria-expanded={all} onClick={() => setAll((v) => !v)}>
              {all ? "收起" : `再看 ${rows.length - CHASE_PREVIEW} 張`}
            </button>
          )}
        </>
      )}
    </div>
  );
}

function WorkItem({ entry: e, note }: { entry: WorkEntry; note?: string }) {
  return (
    <li className="work-item">
      <a href={e.url} target="_blank" rel="noreferrer" className="work-title">
        {e.title}
      </a>
      <span className="work-meta">
        <span className="work-id">#{e.id}</span>
        {note && <span>{note}</span>}
        {e.prs.map((p) => (
          <a
            key={`${p.repo}#${p.number}`}
            href={p.url}
            target="_blank"
            rel="noreferrer"
            className={`badge ${PR_BADGE[p.state]}`}
            title={`${p.repo}：${p.title}`}
          >
            PR #{p.number} {PR_LABEL[p.state]}
          </a>
        ))}
        {e.mine && e.interview_id && <Link href={`/interviews/${e.interview_id}`}>看當初的問答</Link>}
      </span>
    </li>
  );
}
