"use client";

import { useEffect, useRef, useState } from "react";
import { api, Question } from "@/lib/api";
import Markdown from "./Markdown";
import Sprite from "./Sprite";

// Picking an option answers the question; this long a window lets a mis-tap be taken back, since an
// answer can't be changed once sent (and the last one starts the next round)
const UNDO_MS = 2500;

const RESOLVED_LABEL: Record<string, { text: string; cls: string }> = {
  answered: { text: "回答", cls: "" },
  unknown: { text: "不知道 → Open Question", cls: "unknown" },
  skipped: { text: "跳過 → 採用推薦答案（Assumption）", cls: "skipped" },
  confirmed: { text: "Premise 正確", cls: "" },
  corrected: { text: "Premise 不正確，更正為", cls: "unknown" },
};

interface Props {
  q: Question;
  isRequester: boolean;
  selectable: boolean;
  selected: boolean;
  current?: boolean; // the one question the sprite is asking right now
  onToggle: () => void;
  onChanged: () => void;
}

export default function QuestionCard({ q, isRequester, selectable, selected, current = false, onToggle, onChanged }: Props) {
  const [text, setText] = useState("");
  const [correcting, setCorrecting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ title: q.title, body: q.body, options: q.options.join("\n") });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queued, setQueued] = useState<string | null>(null); // the option about to be sent
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flush = useRef<(() => void) | null>(null); // sends the queued answer now

  // Leaving the page (or the card going away) sends what was picked rather than dropping it
  useEffect(() => () => flush.current?.(), []);

  const isPremise = q.kind === "premise";
  const pending = q.status === "pending";
  const handedOff = !!q.handoff_id;

  function cancelQueued() {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    flush.current = null;
    setQueued(null);
  }

  function choose(option: string) {
    cancelQueued();
    // A note already typed in the box goes along with the picked option
    const answer = text.trim() && text.trim() !== option ? `${option}\n${text.trim()}` : option;
    const send = () => {
      timer.current = null;
      flush.current = null;
      void api.respond(q.id, "answer", answer).then(onChanged, (err) => {
        setQueued(null);
        setError((err as Error).message);
      });
    };
    setQueued(option);
    flush.current = send;
    timer.current = setTimeout(send, UNDO_MS);
  }

  async function act(fn: () => Promise<unknown>) {
    cancelQueued();
    setBusy(true);
    setError(null);
    try {
      await fn();
      setText("");
      setCorrecting(false);
      setEditing(false);
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (q.status === "withdrawn") {
    return (
      <div className="card q resolved small muted">
        <span className="ref">{q.ref}</span> {q.title}（已撤回）
      </div>
    );
  }

  const resolved = RESOLVED_LABEL[q.status];

  return (
    <div className={`card q stack ${pending ? "pending" : "resolved"} ${q.can_respond ? "mine" : ""} ${isPremise ? "premise" : ""} ${current ? "current" : ""}`}>
      {current && (
        <span className="peek" aria-hidden="true">
          <Sprite pose="head" size={52} />
        </span>
      )}
      <div className="head">
        {selectable && <input type="checkbox" checked={selected} onChange={onToggle} aria-label="選擇以轉交" />}
        <span className="ref">{q.ref}</span>
        {isPremise && <span className="badge premise">Premise</span>}
        {q.core && <span className="badge core">核心</span>}
        <h3>{q.title}</h3>
        <span className="spacer" />
        {handedOff && <span className="badge accent">轉交 → {q.respondent.split("@")[0]}</span>}
        {pending && !q.can_respond && !handedOff && <span className="muted small">等待 {q.respondent.split("@")[0]}</span>}
      </div>

      {editing ? (
        <div className="stack">
          <input type="text" aria-label="題目標題" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          <textarea aria-label="題目內容" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
          <label className="field">
            <span>選項（一行一個）</span>
            <textarea value={draft.options} onChange={(e) => setDraft({ ...draft, options: e.target.value })} />
          </label>
          <div className="row">
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(() =>
                  api.editQuestion(q.id, {
                    title: draft.title,
                    body: draft.body,
                    options: draft.options.split("\n").map((s) => s.trim()).filter(Boolean),
                  }),
                )
              }
            >
              儲存
            </button>
            <button onClick={() => setEditing(false)}>取消</button>
          </div>
        </div>
      ) : (
        <div className="body">{isPremise ? <>「<Markdown inline text={q.body} />」</> : <Markdown text={q.body} />}</div>
      )}

      {q.ai_note && (
        <div className="evidence">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-label="AI 查證">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <span className="pre"><Markdown inline text={q.ai_note} /></span>
        </div>
      )}

      {pending && q.recommendation && (
        <div className="rec">
          <b>小精靈建議：</b>
          <Markdown inline text={q.recommendation} />
          {q.rationale && <div className="muted small"><Markdown inline text={q.rationale} /></div>}
        </div>
      )}

      {!pending && resolved && (
        <div className={`answer ${resolved.cls}`}>
          <span className="small muted">
            {resolved.text}
            {q.answered_by && ` · ${q.answered_by.split("@")[0]}`}
          </span>
          {q.answer_text && <div className="pre">{q.answer_text}</div>}
        </div>
      )}

      {q.can_respond && !editing && (
        <div className="stack">
          {!isPremise && q.options.length > 0 && (
            <div className="options" role="group" aria-label="選項">
              {q.options.map((o) => (
                <button key={o} disabled={busy} onClick={() => choose(o)} className={queued === o ? "on" : ""} aria-pressed={queued === o}>
                  {o}
                  {o === q.recommendation && <span className="tag">建議</span>}
                </button>
              ))}
            </div>
          )}
          {queued !== null && (
            <div className="queued" role="status">
              <span className="countdown" aria-hidden="true" style={{ animationDuration: `${UNDO_MS}ms` }} />
              <span>已選「{queued}」，即將送出</span>
              <span className="spacer" />
              <button className="link small" onClick={cancelQueued}>
                復原
              </button>
            </div>
          )}
          {isPremise ? (
            <>
              {correcting && (
                <textarea autoFocus placeholder="正確的情況是…" value={text} onChange={(e) => setText(e.target.value)} />
              )}
              <div className="row actions">
                {!correcting ? (
                  <>
                    <button className="primary" disabled={busy} onClick={() => act(() => api.respond(q.id, "confirm"))}>
                      對，沒錯
                    </button>
                    <button disabled={busy} onClick={() => setCorrecting(true)}>
                      不對，我來更正
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      className="primary"
                      disabled={busy || !text.trim()}
                      onClick={() => act(() => api.respond(q.id, "correct", text))}
                    >
                      送出更正
                    </button>
                    <button onClick={() => setCorrecting(false)}>取消</button>
                  </>
                )}
                <button disabled={busy} onClick={() => act(() => api.respond(q.id, "unknown"))}>
                  不知道
                </button>
              </div>
            </>
          ) : (
            <>
              <textarea
                placeholder={q.options.length > 0 ? "點選項就會送出；要補充的話，先寫在這裡再點選項，或自行輸入回答" : "你的回答"}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <div className="row actions">
                <button
                  className="primary"
                  disabled={busy || queued !== null || !text.trim()}
                  onClick={() => act(() => api.respond(q.id, "answer", text))}
                >
                  回答
                </button>
                <button disabled={busy} onClick={() => act(() => api.respond(q.id, "unknown"))} title="列入 Open Questions">
                  不知道 → Open Question
                </button>
                {q.can_skip && (
                  <button disabled={busy} onClick={() => act(() => api.respond(q.id, "skip"))} title="採用建議答案，標記為 Assumption">
                    跳過，採用建議
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {pending && isRequester && !editing && !handedOff && (
        <div className="row small">
          <button className="link" onClick={() => setEditing(true)}>
            修改題目
          </button>
          <button className="link" disabled={busy} onClick={() => act(() => api.withdraw(q.id))}>
            撤回
          </button>
        </div>
      )}
      {error && <div className="notice danger small" role="alert">{error}</div>}
    </div>
  );
}
