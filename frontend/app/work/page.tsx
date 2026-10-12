"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, CurrentWork, Meta, WorkEntry, WorkPull } from "@/lib/api";

// Current Work: what RD is doing under the Product's Parent, so a PM can check before filing a Request.
// The interviewer reads the same list and points out a Request that overlaps a ticket.

const GROUPS: { id: string; label: string; has: (e: WorkEntry) => boolean }[] = [
  { id: "active", label: "進行中", has: (e) => e.state === "Active" },
  { id: "testing", label: "測試中", has: (e) => !["Active", "New"].includes(e.state) && !e.closed_on },
  { id: "new", label: "尚未開始", has: (e) => e.state === "New" },
  { id: "closed", label: "最近完成", has: (e) => !!e.closed_on },
];

const PR_LABEL: Record<WorkPull["state"], string> = { open: "審查中", merged: "已合併", closed: "已關閉" };
const PR_BADGE: Record<WorkPull["state"], string> = { open: "accent", merged: "ok", closed: "" };

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
      <h1>進行中的工作</h1>
      <p className="muted">
        RD 現在手上的票，以及最近完成的票。開新需求前可以先看看是不是已經有人在做；小精靈拷問時也會對照這份清單，需求跟哪張票重疊就會問你。
      </p>
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
          要先連結 Azure DevOps 才看得到票。<Link href="/settings">前往設定</Link>（約 1 分鐘）
        </div>
      )}
      {error && error.status !== 409 && (
        <div className="row notice danger" role="alert">
          <span>讀不到工作清單：{error.message}</span>
          <button onClick={() => setAttempt((n) => n + 1)}>重試</button>
        </div>
      )}
      {!work && !error && <p className="muted">載入中…</p>}
      {work && (
        <>
          <p className="muted small">
            來源：<a href={work.parent_url} target="_blank" rel="noreferrer">#{work.parent_id}</a> 底下的票，「最近完成」是{" "}
            {work.closed_days} 天內關閉的。每 10 分鐘更新一次。
            {!work.github && " 目前沒有設定 GitHub，看不到 PR 狀態。"}
          </p>
          {work.items.length === 0 && <p className="muted">目前沒有進行中的票。</p>}
          {GROUPS.map((g) => {
            const rows = work.items.filter(g.has);
            if (!rows.length) return null;
            return (
              <section key={g.id} className="stack" style={{ gap: 6 }} aria-label={g.label}>
                <h2 className="work-group">
                  {g.label} <span className="muted small">{rows.length}</span>
                </h2>
                <div className="card list" style={{ padding: 0 }}>
                  {rows.map((e) => (
                    <WorkRow key={e.id} entry={e} />
                  ))}
                </div>
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}

function WorkRow({ entry: e }: { entry: WorkEntry }) {
  const who = [e.assignee ?? "未指派", e.closed_on ? `${e.closed_on} 完成` : e.iteration].filter(Boolean).join(" · ");
  return (
    <div className="item-row work-row">
      <a href={e.url} target="_blank" rel="noreferrer" className="item">
        <span className="muted small">#{e.id}</span>
        <span className="title">{e.title}</span>
        <span className="muted small">{who}</span>
      </a>
      {e.prs.length > 0 && (
        <span className="work-prs">
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
        </span>
      )}
    </div>
  );
}
