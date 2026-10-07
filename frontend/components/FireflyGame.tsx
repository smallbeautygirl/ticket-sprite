"use client";

import { useEffect, useRef, useState } from "react";

// 螢火蟲收集詞彙: something to do while the sprite reads. Fly up with Space or a tap, collect
// the glowing terms, stay out of the fog. It waits paused until asked, is silent, and goes away with
// the waiting card.

const WORDS = ["Premise", "Spec", "Answer", "Assumption", "Open Question", "Handoff", "Parent", "Ticket", "New Term"];
const BEST_KEY = "sprite.game.best";
const H = 200;
const FACE = "#fff6e5"; // Sprite palette (see Sprite.tsx)
const WING = "#d9eef0";

// w: a word's label width; the label is drawn from x + r - 2 and counts as part of the word
type Thing = { kind: "word" | "fog"; x: number; y: number; r: number; text?: string; w?: number; taken?: boolean };

const FLY_R = 9;
const LABEL_HALF_H = 8;
const LABEL_REACH = 12; // as forgiving as the glow: 8 + 12 = the glow's 11 + 9

/** Whether the firefly at (x, y) touches a thing: fog by its puff, a word by its glow or its label. */
export function touches(fly: { x: number; y: number }, t: Thing): boolean {
  if (Math.hypot(t.x - fly.x, t.y - fly.y) < t.r + FLY_R) return true;
  if (t.kind !== "word" || !t.w) return false;
  const left = t.x + t.r - 2;
  const nx = Math.max(left, Math.min(fly.x, left + t.w));
  const ny = Math.max(t.y - LABEL_HALF_H, Math.min(fly.y, t.y + LABEL_HALF_H));
  return Math.hypot(nx - fly.x, ny - fly.y) < LABEL_REACH;
}

function readBest(): number {
  try {
    return Number(localStorage.getItem(BEST_KEY)) || 0;
  } catch {
    return 0;
  }
}

function saveBest(n: number) {
  try {
    localStorage.setItem(BEST_KEY, String(n));
  } catch {
    // private window: the best score lasts for this visit only
  }
}

type Pollen = { x: number; y: number; r: number };
type Colors = { sky: string; glow: string };
const FONT = "500 13px 'Noto Sans TC', sans-serif";
const LOCK_MS = 800; // after a crash, ignore the restart button for a moment: thumbs and Space are still flapping

function readColors(): Colors {
  const css = getComputedStyle(document.documentElement);
  const token = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return { sky: token("--sprite-ink", "#1c2b22"), glow: token("--glow", "#f4c542") };
}

/** Size the canvas to its box (crisp on high-DPI screens) and return its CSS width. */
function fit(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D): number {
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  canvas.width = width * dpr;
  canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return width;
}

function paint(ctx: CanvasRenderingContext2D, width: number, fly: { x: number; y: number }, pollen: Pollen[], things: Thing[], c: Colors) {
  ctx.fillStyle = c.sky;
  ctx.fillRect(0, 0, width, H);
  ctx.fillStyle = "rgba(244, 197, 66, 0.35)";
  for (const p of pollen) {
    ctx.beginPath();
    ctx.arc(p.x % (width + 40), p.y, p.r, 0, Math.PI * 2);
    ctx.fill();
  }
  for (const t of things) {
    if (t.kind === "fog") {
      ctx.fillStyle = "rgba(201, 220, 200, 0.5)";
      for (const [ox, oy, k] of [[-0.6, 0.2, 0.7], [0, 0, 1], [0.6, 0.15, 0.75]]) {
        ctx.beginPath();
        ctx.arc(t.x + ox * t.r, t.y + oy * t.r, t.r * k, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      const g = ctx.createRadialGradient(t.x, t.y, 0, t.x, t.y, t.r);
      g.addColorStop(0, c.glow);
      g.addColorStop(1, "rgba(244, 197, 66, 0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(t.x, t.y, t.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = c.glow;
      ctx.font = FONT;
      ctx.textBaseline = "middle";
      ctx.fillText(t.text ?? "", t.x + t.r - 2, t.y);
    }
  }
  // the firefly: glowing tail, wings, face
  const { x, y } = fly;
  ctx.save();
  ctx.shadowColor = c.glow;
  ctx.shadowBlur = 18;
  ctx.fillStyle = c.glow;
  ctx.beginPath();
  ctx.ellipse(x - 3, y + 9, 7, 6, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  ctx.fillStyle = WING;
  ctx.beginPath();
  ctx.ellipse(x - 11, y - 2, 8, 5, -0.5, 0, Math.PI * 2);
  ctx.ellipse(x + 9, y - 2, 8, 5, 0.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = FACE;
  ctx.beginPath();
  ctx.arc(x, y, FLY_R, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = c.sky;
  ctx.beginPath();
  ctx.arc(x - 3, y, 1.6, 0, Math.PI * 2);
  ctx.arc(x + 3.5, y, 1.6, 0, Math.PI * 2);
  ctx.fill();
}

function scatterPollen(): Pollen[] {
  return Array.from({ length: 28 }, () => ({ x: Math.random() * 1600, y: Math.random() * H, r: Math.random() * 1.4 + 0.4 }));
}

export default function FireflyGame({ onClose }: { onClose: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const flap = useRef<() => void>(() => {});
  const [phase, setPhase] = useState<"ready" | "playing" | "over">("ready");
  const [score, setScore] = useState(0);
  const [best, setBest] = useState(0);
  const [record, setRecord] = useState(false);
  const [locked, setLocked] = useState(false);

  useEffect(() => setBest(readBest()), []);

  function start() {
    if (locked) return;
    setScore(0);
    setPhase("playing");
    canvasRef.current?.focus({ preventScroll: true });
    // keep the sky clear of the sticky action bar on small screens
    canvasRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  // Before the first game: a still night with one word and one puff of fog, so it reads as a game
  useEffect(() => {
    if (phase !== "ready") return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const pollen = scatterPollen();
    const still = () => {
      const width = fit(canvas, ctx);
      ctx.font = FONT;
      const things: Thing[] = [
        { kind: "word", x: width * 0.42, y: 62, r: 11, text: "Spec", w: ctx.measureText("Spec").width },
        { kind: "fog", x: width * 0.78, y: 138, r: 22 },
      ];
      paint(ctx, width, { x: 72, y: H / 2 }, pollen, things, readColors());
    };
    still();
    window.addEventListener("resize", still);
    return () => window.removeEventListener("resize", still);
  }, [phase]);

  // After a crash, hold the restart button briefly so a flap meant for the firefly can't press it
  useEffect(() => {
    if (phase !== "over") return;
    setLocked(true);
    const t = setTimeout(() => setLocked(false), LOCK_MS);
    return () => clearTimeout(t);
  }, [phase]);

  useEffect(() => {
    if (phase !== "playing") return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const colors = readColors();
    let width = fit(canvas, ctx);
    const resize = () => {
      width = fit(canvas, ctx);
    };
    window.addEventListener("resize", resize);

    const fly = { x: 72, y: H / 2, vy: 0 };
    const pollen = scatterPollen();
    let things: Thing[] = [];
    let elapsed = 0;
    let nextWord = 0.5;
    let nextFog = 1.6;
    let got = 0;
    let wordIndex = Math.floor(Math.random() * WORDS.length);
    let last = performance.now();
    let raf = 0;
    flap.current = () => {
      fly.vy = -250;
    };
    const draw = () => paint(ctx, width, fly, pollen, things, colors);

    const step = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!document.hidden) {
        elapsed += dt;
        const speed = 150 + elapsed * 4;
        fly.vy += 700 * dt;
        fly.y += fly.vy * dt;
        // the edges are soft: bump and keep going
        if (fly.y < 14) [fly.y, fly.vy] = [14, 0];
        if (fly.y > H - 14) [fly.y, fly.vy] = [H - 14, 0];
        for (const p of pollen) p.x = (p.x - speed * 0.15 * dt + 1600) % 1600;
        nextWord -= dt;
        nextFog -= dt;
        if (nextWord <= 0) {
          const text = WORDS[wordIndex++ % WORDS.length];
          ctx.font = FONT;
          things.push({ kind: "word", x: width + 40, y: 28 + Math.random() * (H - 56), r: 11, text, w: ctx.measureText(text).width });
          nextWord = 0.9 + Math.random() * 0.8;
        }
        if (nextFog <= 0) {
          things.push({ kind: "fog", x: width + 60, y: 24 + Math.random() * (H - 48), r: 16 + Math.random() * 10 });
          nextFog = Math.max(0.7, 1.7 - elapsed / 60) + Math.random() * 0.6;
        }
        for (const t of things) t.x -= speed * (t.kind === "fog" ? 1.1 : 1) * dt;
        for (const t of things) {
          if (!touches(fly, t)) continue;
          if (t.kind === "word") {
            t.taken = true;
            got += 1;
            setScore(got);
          } else {
            draw(); // the last frame stays under the "over" card
            const isRecord = got > readBest();
            if (isRecord) saveBest(got);
            setRecord(isRecord);
            setBest(readBest());
            setPhase("over");
            return;
          }
        }
        things = things.filter((t) => t.x > -140 && !t.taken);
      }
      draw();
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      flap.current = () => {};
    };
  }, [phase]);

  return (
    <div className="game">
      <div className="game-stage">
        <canvas
          ref={canvasRef}
          tabIndex={0}
          role="img"
          aria-label="螢火蟲收集詞彙小遊戲：按空白鍵或點一下往上飛"
          onPointerDown={() => flap.current()}
          onKeyDown={(e) => {
            if (phase === "playing" && (e.key === " " || e.key === "ArrowUp")) {
              e.preventDefault();
              flap.current();
            } else if (phase !== "playing" && e.key === " ") {
              e.preventDefault(); // a leftover flap must not scroll the page or restart
            } else if (phase !== "playing" && e.key === "Enter") {
              start();
            }
          }}
        />
        {phase !== "playing" && (
          // Before the first game a tap anywhere starts; after a crash only the button restarts
          <div className="game-overlay" onClick={phase === "ready" ? start : undefined}>
            {phase === "ready" ? (
              <>
                <b>螢火蟲收集詞彙</b>
                <span className="small">等的時候玩一下：按空白鍵或點一下往上飛，收集發光的詞，閃開霧團。</span>
              </>
            ) : (
              <>
                <b>撞進霧裡了！</b>
                <span className="small">這次收集了 {score} 個詞{record ? "，新紀錄！" : "。"}</span>
              </>
            )}
            <button
              className="primary"
              disabled={locked}
              onClick={(e) => {
                e.stopPropagation();
                start();
              }}
            >
              {phase === "ready" ? "開始" : "再玩一次"}
            </button>
          </div>
        )}
      </div>
      <div className="row small muted">
        <span>收集 {score}</span>
        <span>最高 {best}</span>
        <span className="spacer" />
        <button className="link small" onClick={onClose}>
          收起遊戲
        </button>
      </div>
    </div>
  );
}
