"use client";

import { useEffect, useState } from "react";
import { EngineProgress } from "@/lib/api";
import { canNotify } from "@/lib/ready";
import FireflyGame from "./FireflyGame";
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

/** The sprite reading while the engine works, with what it has looked at so far. onStop lets the Requester call it off. */
export default function Thinking({
  title,
  subtitle,
  progress,
  onStop,
}: {
  title: string;
  subtitle: string;
  progress: EngineProgress | null;
  onStop?: () => void;
}) {
  const looked = progress ? progress.read_count + progress.searches : 0;
  const latest = progress?.reads[progress.reads.length - 1];
  const [playing, setPlaying] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("unsupported");
  useEffect(() => setPermission(canNotify() ? Notification.permission : "unsupported"), []);
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
      <div className="wait-extras small">
        <span className="muted">
          {permission === "granted" ? "好了會通知你，也會在分頁標題打勾，可以先去忙別的。" : "切到別的分頁也沒關係，好了分頁標題會打勾。"}
        </span>
        {permission === "default" && (
          <button className="link small" onClick={() => Notification.requestPermission().then(setPermission)}>
            好了也發通知給我
          </button>
        )}
        {!playing && (
          <button className="link small" onClick={() => setPlaying(true)}>
            等的時候玩一下
          </button>
        )}
        {onStop && (
          <button className="link small" onClick={onStop}>
            停止
          </button>
        )}
      </div>
      {playing && <FireflyGame onClose={() => setPlaying(false)} />}
    </div>
  );
}
