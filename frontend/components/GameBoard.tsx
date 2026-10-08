"use client";

import { useEffect, useState } from "react";
import { api, formatBest, GAME_LABEL, GameId, Leaderboard } from "@/lib/api";

const SCORES_EVENT = "sprite:scores";

/** Save a finished game and tell every board on the page to refresh. */
export async function submitScore(game: GameId, score: number) {
  const r = await api.saveScore(game, score);
  window.dispatchEvent(new CustomEvent(SCORES_EVENT, { detail: game }));
  return r;
}

/** One game's leaderboard: the top players' all-time bests, and where you stand if you are below them. */
export default function GameBoard({ game, limit = 5, title }: { game: GameId; limit?: number; title?: string }) {
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    const load = () =>
      api.leaderboard(game, limit).then(
        (b) => live && (setBoard(b), setFailed(false)),
        () => live && setFailed(true),
      );
    load();
    const onScores = (e: Event) => (e as CustomEvent<GameId>).detail === game && load();
    window.addEventListener(SCORES_EVENT, onScores);
    return () => {
      live = false;
      window.removeEventListener(SCORES_EVENT, onScores);
    };
  }, [game, limit]);

  return (
    <section className="game-board small" aria-label={`${GAME_LABEL[game]}排行榜`}>
      <b>{title ?? `排行榜 · ${GAME_LABEL[game]}`}</b>
      {failed ? (
        <span className="muted">排行榜暫時載入不了。</span>
      ) : !board ? (
        <span className="muted">載入中…</span>
      ) : board.top.length === 0 ? (
        <span className="muted">還沒有人上榜，來搶第一！</span>
      ) : (
        <ol>
          {board.top.map((p, i) => (
            <li key={i} className={p.me ? "me" : undefined}>
              <span className="muted">{i + 1}</span>
              <span className="name" title={p.name}>{p.name}</span>
              <span>{formatBest(game, p.best)}</span>
            </li>
          ))}
        </ol>
      )}
      {board?.mine && !board.top.some((p) => p.me) && (
        <span className="muted">
          你目前第 {board.mine.rank} 名 · {formatBest(game, board.mine.best)}
        </span>
      )}
    </section>
  );
}
