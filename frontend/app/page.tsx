"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, InterviewSummary, ROLE_LABEL, STATUS_LABEL, TYPE_LABEL } from "@/lib/api";

type Scope = "for-me" | "mine" | "all";
const SCOPES: { id: Scope; label: string }[] = [
  { id: "for-me", label: "待我回答" },
  { id: "mine", label: "我發起的" },
  { id: "all", label: "全部" },
];

const STATUS_BADGE: Record<InterviewSummary["status"], string> = {
  interviewing: "accent",
  spec_draft: "warn",
  ticketed: "ok",
  decision_record: "",
};

export default function Home() {
  const [scope, setScope] = useState<Scope>("mine");
  const [items, setItems] = useState<InterviewSummary[] | null>(null);
  const [forMeCount, setForMeCount] = useState(0);

  useEffect(() => {
    api.listInterviews("for-me").then((rows) => {
      setForMeCount(rows.length);
      if (rows.length) setScope("for-me");
    });
  }, []);

  useEffect(() => {
    setItems(null);
    api.listInterviews(scope).then(setItems);
  }, [scope]);

  return (
    <div className="stack">
      <div className="row">
        <h1>Interviews</h1>
        <span className="spacer" />
        <Link href="/new" className="btn primary">＋ 新增 Request</Link>
      </div>
      <div className="seg">
        {SCOPES.map((s) => (
          <button key={s.id} className={scope === s.id ? "on" : ""} onClick={() => setScope(s.id)}>
            {s.label}
            {s.id === "for-me" && forMeCount > 0 && ` (${forMeCount})`}
          </button>
        ))}
      </div>
      <div className="card list" style={{ padding: 0 }}>
        {items === null && <p className="muted" style={{ padding: 16 }}>載入中…</p>}
        {items?.length === 0 && (
          <p className="muted" style={{ padding: 16 }}>
            {scope === "for-me" ? "目前沒有轉交給你的題目。" : "還沒有 Interview。"}
          </p>
        )}
        {items?.map((i) => (
          <Link key={i.id} href={`/interviews/${i.id}`} className="item">
            <span className={`badge ${STATUS_BADGE[i.status]}`}>{STATUS_LABEL[i.status]}</span>
            <span className="badge">{TYPE_LABEL[i.request_type]}</span>
            <span className="title">{i.title}</span>
            {i.ticket_id && <span className="small">#{i.ticket_id}</span>}
            <span className="muted small">
              {ROLE_LABEL[i.role]} · {i.requester.split("@")[0]} · {new Date(i.created_at).toLocaleDateString("zh-TW")}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
