"use client";

import GameBoard from "@/components/GameBoard";

// Everyone's all-time bests in the waiting games. The games themselves live on the waiting card.
export default function LeaderboardPage() {
  return (
    <div className="stack">
      <h1>排行榜</h1>
      <p className="muted">等小精靈翻書時玩的小遊戲，每個人只算歷來最好的一次。</p>
      <div className="boards">
        <div className="card">
          <GameBoard game="firefly" limit={20} title="螢火蟲收集詞彙 · 收集最多" />
        </div>
        <div className="card">
          <GameBoard game="mines" limit={20} title="踩地雷 · 9×9 最快清完" />
        </div>
      </div>
    </div>
  );
}
