"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { GAME_LABEL, GameId } from "@/lib/api";
import FireflyGame from "./FireflyGame";
import GameBoard from "./GameBoard";
import Minesweeper from "./Minesweeper";

const PICK_KEY = "sprite.game.pick";
// The interview page leaves a column in its left margin for the leaderboard (see .interview-side)
export const SIDE_SLOT_ID = "game-side";

/** The games on the waiting card, one at a time, with the chosen game's leaderboard. */
export default function WaitingGames({ onClose }: { onClose: () => void }) {
  const [game, setGame] = useState<GameId>("firefly");
  const [slot, setSlot] = useState<HTMLElement | null>(null);

  useEffect(() => {
    try {
      if (localStorage.getItem(PICK_KEY) === "mines") setGame("mines");
    } catch {
      // private window: start on the firefly
    }
    setSlot(document.getElementById(SIDE_SLOT_ID));
  }, []);

  function pick(g: GameId) {
    setGame(g);
    try {
      localStorage.setItem(PICK_KEY, g);
    } catch {
      // private window: remembered for this visit only
    }
  }

  return (
    <div className="games">
      <div className="row">
        <div className="seg" role="group" aria-label="選遊戲">
          {(["firefly", "mines"] as const).map((g) => (
            <button key={g} className={`small${game === g ? " on" : ""}`} aria-pressed={game === g} onClick={() => pick(g)}>
              {GAME_LABEL[g]}
            </button>
          ))}
        </div>
        <span className="spacer" />
        <button className="link small" onClick={onClose}>
          收起遊戲
        </button>
      </div>
      {game === "firefly" ? <FireflyGame /> : <Minesweeper />}
      {/* Wide screens show the board in the page's left margin; narrow ones, here under the game */}
      <div className={slot ? "board-here when-narrow" : "board-here"}>
        <GameBoard game={game} />
      </div>
      {slot && createPortal(<GameBoard game={game} />, slot)}
    </div>
  );
}
