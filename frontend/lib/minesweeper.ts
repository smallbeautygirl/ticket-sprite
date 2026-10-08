// 踩地雷 rules, kept apart from the drawing so they can be tested. One fixed board (9×9, 10 mines):
// everyone races the same difficulty, and the leaderboard ranks the fastest clear.

export const ROWS = 9;
export const COLS = 9;
export const MINES = 10;

export type Cell = { mine: boolean; adjacent: number; open: boolean; flag: boolean };
export type Board = Cell[]; // row-major, ROWS × COLS

export function emptyBoard(): Board {
  return Array.from({ length: ROWS * COLS }, () => ({ mine: false, adjacent: 0, open: false, flag: false }));
}

export function neighbours(i: number): number[] {
  const r = Math.floor(i / COLS);
  const c = i % COLS;
  const out: number[] = [];
  for (let dr = -1; dr <= 1; dr++) {
    for (let dc = -1; dc <= 1; dc++) {
      const rr = r + dr;
      const cc = c + dc;
      if ((dr || dc) && rr >= 0 && rr < ROWS && cc >= 0 && cc < COLS) out.push(rr * COLS + cc);
    }
  }
  return out;
}

/** Lay the mines after the first click, away from it and its neighbours, so the first click always opens an area. */
export function layMines(board: Board, first: number, random: () => number = Math.random): Board {
  const keepClear = new Set([first, ...neighbours(first)]);
  const spots = board.map((_, i) => i).filter((i) => !keepClear.has(i));
  for (let k = spots.length - 1; k > 0; k--) {
    const j = Math.floor(random() * (k + 1));
    [spots[k], spots[j]] = [spots[j], spots[k]];
  }
  const mines = new Set(spots.slice(0, MINES));
  return board.map((cell, i) => ({
    ...cell,
    mine: mines.has(i),
    adjacent: neighbours(i).filter((n) => mines.has(n)).length,
  }));
}

/**
 * Open a cell: an empty one opens its whole empty area. Opening a number whose flags already account for
 * its mines opens the rest of its neighbours (chording). boom is true when a mine was opened.
 */
export function reveal(board: Board, i: number): { board: Board; boom: boolean } {
  const next = board.map((cell) => ({ ...cell }));
  const target = next[i];
  if (target.flag) return { board, boom: false };
  let start = [i];
  if (target.open) {
    const around = neighbours(i);
    if (!target.adjacent || around.filter((n) => next[n].flag).length !== target.adjacent) return { board, boom: false };
    start = around.filter((n) => !next[n].flag && !next[n].open);
  }
  let boom = false;
  const queue = [...start];
  while (queue.length) {
    const k = queue.pop()!;
    const cell = next[k];
    if (cell.flag || (cell.open && k !== i)) continue;
    cell.open = true;
    if (cell.mine) boom = true;
    else if (cell.adjacent === 0) queue.push(...neighbours(k).filter((n) => !next[n].open));
  }
  return { board: next, boom };
}

export function toggleFlag(board: Board, i: number): Board {
  if (board[i].open) return board;
  return board.map((cell, k) => (k === i ? { ...cell, flag: !cell.flag } : cell));
}

/** Every safe cell is open. */
export function cleared(board: Board): boolean {
  return board.every((cell) => cell.mine || cell.open);
}

export function flagsLeft(board: Board): number {
  return MINES - board.filter((cell) => cell.flag).length;
}
