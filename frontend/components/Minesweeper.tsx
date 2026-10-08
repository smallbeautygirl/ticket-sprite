"use client";

import { useEffect, useRef, useState } from "react";
import { api, formatBest } from "@/lib/api";
import { Board, cleared, COLS, emptyBoard, flagsLeft, layMines, reveal, ROWS, toggleFlag } from "@/lib/minesweeper";
import { submitScore } from "./GameBoard";

// 踩地雷: the other thing to do while the sprite reads. One fixed 9×9 board with 10 mines; the clock starts on the
// first click (which is never a mine) and the leaderboard ranks the fastest clear. Right-click, F, or 插旗模式 flags.
// It looks like the classic Windows game on purpose, the same in both themes.

type Phase = "ready" | "playing" | "won" | "lost";

export default function Minesweeper() {
  const [board, setBoard] = useState<Board>(emptyBoard);
  const [phase, setPhase] = useState<Phase>("ready");
  const [startedAt, setStartedAt] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [flagMode, setFlagMode] = useState(false);
  const [focus, setFocus] = useState(Math.floor((ROWS * COLS) / 2));
  const [best, setBest] = useState<number | null>(null);
  const [record, setRecord] = useState(false);
  const [pressing, setPressing] = useState(false);
  const [blast, setBlast] = useState(-1); // the mine that went off, shown red
  const cells = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    api.leaderboard("mines", 1).then(
      (b) => setBest(b.mine?.best ?? null),
      () => undefined, // offline: the game still plays
    );
  }, []);

  useEffect(() => {
    if (phase !== "playing") return;
    const t = setInterval(() => setElapsed(performance.now() - startedAt), 100);
    return () => clearInterval(t);
  }, [phase, startedAt]);

  function restart() {
    setBoard(emptyBoard());
    setPhase("ready");
    setElapsed(0);
    setRecord(false);
    setBlast(-1);
  }

  async function win(ms: number) {
    try {
      const r = await submitScore("mines", Math.max(1000, ms));
      setRecord(r.record);
      setBest(r.mine.best);
    } catch {
      // offline: the clear is not recorded
    }
  }

  function open(i: number) {
    if (phase === "won" || phase === "lost") return;
    let b = board;
    let t0 = startedAt;
    if (phase === "ready") {
      b = layMines(b, i);
      t0 = performance.now();
      setStartedAt(t0);
      setPhase("playing");
    }
    const { board: next, boom } = reveal(b, i);
    if (boom) {
      setBlast(next.findIndex((c) => c.mine && c.open));
      setBoard(next.map((c) => (c.mine ? { ...c, open: true } : c)));
      setElapsed(performance.now() - t0);
      setPhase("lost");
      return;
    }
    setBoard(next);
    if (cleared(next)) {
      const ms = Math.round(performance.now() - t0);
      setElapsed(ms);
      setBoard(next.map((c) => (c.mine ? { ...c, flag: true } : c)));
      setPhase("won");
      win(ms);
    }
  }

  function flag(i: number) {
    if (phase !== "playing") return;
    setBoard(toggleFlag(board, i));
  }

  function press(i: number) {
    if (flagMode && !board[i].open) flag(i);
    else open(i);
  }

  function move(i: number) {
    setFocus(i);
    cells.current[i]?.focus();
  }

  function onKey(e: React.KeyboardEvent, i: number) {
    const r = Math.floor(i / COLS);
    const c = i % COLS;
    const to: Record<string, number | undefined> = {
      ArrowUp: r > 0 ? i - COLS : undefined,
      ArrowDown: r < ROWS - 1 ? i + COLS : undefined,
      ArrowLeft: c > 0 ? i - 1 : undefined,
      ArrowRight: c < COLS - 1 ? i + 1 : undefined,
    };
    if (e.key in to) {
      e.preventDefault();
      if (to[e.key] !== undefined) move(to[e.key]!);
    } else if (e.key === "f" || e.key === "F") {
      e.preventDefault();
      flag(i);
    }
  }

  const seconds = (elapsed / 1000).toFixed(1);
  const over = phase === "won" || phase === "lost";
  const led = (n: number) => String(Math.max(-99, Math.min(999, n))).padStart(3, "0");
  const face = phase === "won" ? "😎" : phase === "lost" ? "😵" : pressing ? "😮" : "🙂";

  return (
    <div className="game">
      {/* The classic Windows look: a raised grey panel, red LED counters, the face to restart */}
      <div className="ms">
        <div className="ms-head">
          <span className="ms-led" aria-label={`剩下 ${flagsLeft(board)} 面旗子`}>{led(flagsLeft(board))}</span>
          <button className="ms-face" aria-label="重新開始" onClick={restart}>
            {face}
          </button>
          <span className="ms-led" aria-label={`經過 ${Math.floor(elapsed / 1000)} 秒`}>{led(Math.floor(elapsed / 1000))}</span>
        </div>
        <div
          className="ms-grid"
          role="grid"
          aria-label="踩地雷：方向鍵移動，Enter 翻開，F 插旗"
          onPointerDown={(e) => !over && e.button === 0 && setPressing(true)}
          onPointerUp={() => setPressing(false)}
          onPointerLeave={() => setPressing(false)}
        >
          {Array.from({ length: ROWS }, (_, r) => (
            <div key={r} role="row" className="ms-row">
              {Array.from({ length: COLS }, (_, c) => {
                const i = r * COLS + c;
                const cell = board[i];
                const wrongFlag = phase === "lost" && cell.flag && !cell.mine;
                const shown = wrongFlag ? "❌" : cell.open ? (cell.mine ? "💣" : cell.adjacent || "") : cell.flag ? "🚩" : "";
                const label = wrongFlag
                  ? "插錯旗"
                  : cell.open
                    ? cell.mine
                      ? "地雷"
                      : cell.adjacent
                        ? `${cell.adjacent}`
                        : "空白"
                    : cell.flag
                      ? "已插旗"
                      : "未翻開";
                return (
                  <button
                    key={c}
                    ref={(el) => {
                      cells.current[i] = el;
                    }}
                    role="gridcell"
                    tabIndex={i === focus ? 0 : -1}
                    aria-label={`第 ${r + 1} 列第 ${c + 1} 行，${label}`}
                    className={`ms-cell${cell.open || wrongFlag ? " open" : ""}${cell.open && !cell.mine && cell.adjacent ? ` n${cell.adjacent}` : ""}${i === blast ? " blast" : ""}`}
                    onClick={() => {
                      setFocus(i);
                      press(i);
                    }}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      flag(i);
                    }}
                    onKeyDown={(e) => onKey(e, i)}
                  >
                    {shown}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="row small muted" role="status">
        {over ? (
          <span>
            {phase === "won" ? `全部清乾淨了！花了 ${seconds} 秒${record ? "，新紀錄！" : "。"}` : "踩到地雷了！"}點笑臉再來一局。
          </span>
        ) : (
          <span>{phase === "ready" ? "點任一格開始，第一格一定安全。" : "右鍵或 F 插旗；旗子插滿的數字點一下會翻開周圍。"}</span>
        )}
        <button className={`link small${flagMode ? " on" : ""}`} aria-pressed={flagMode} onClick={() => setFlagMode(!flagMode)}>
          {flagMode ? "插旗模式：開" : "插旗模式"}
        </button>
        <span className="spacer" />
        <span>最快 {best === null ? "—" : formatBest("mines", best)}</span>
      </div>
    </div>
  );
}
