"use client";

import { useEffect, useState } from "react";
import { EngineProgress } from "@/lib/api";
import Sprite from "./Sprite";

function Elapsed({ since }: { since: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const sec = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000));
  return <>{Math.floor(sec / 60)}:{String(sec % 60).padStart(2, "0")}</>;
}

/** The sprite reading while the engine works, with what it has looked at so far. */
export default function Thinking({ title, subtitle, progress }: { title: string; subtitle: string; progress: EngineProgress | null }) {
  const looked = progress ? progress.read_count + progress.searches : 0;
  const latest = progress?.reads[progress.reads.length - 1];
  return (
    <div className="card thinking">
      {/* Announce the phase once; the ticking timer and file list would be read out every second */}
      <span className="sr-only" role="status">{title}</span>
      <Sprite pose="reading" size={72} />
      <div className="stack" style={{ gap: 8, minWidth: 0, flex: 1 }}>
        <div className="stack" style={{ gap: 2 }}>
          <h3>{title}</h3>
          <span className="muted small">
            {subtitle}
            {progress && (
              <>
                {" "}· 已等 <Elapsed since={progress.started_at} />
              </>
            )}
          </span>
        </div>
        {progress && (
          <div className="stack" style={{ gap: 6 }}>
            <span className="small" style={{ color: "var(--text-2)" }}>
              {looked === 0 ? "正在讀 Request 與附件…" : `已讀 ${progress.read_count} 份文件 · 搜尋 ${progress.searches} 次`}
            </span>
            {progress.reads.length > 0 && (
              <div className="reads">
                {progress.reads.map((r) => (
                  <code key={r} className={r === latest ? "on" : ""} title={r}>
                    {r}
                  </code>
                ))}
                {progress.read_count > progress.reads.length && (
                  <span className="muted small">…另有 {progress.read_count - progress.reads.length} 份</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
