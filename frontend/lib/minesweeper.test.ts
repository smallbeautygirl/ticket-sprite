import { describe, expect, it } from "vitest";
import { cleared, COLS, emptyBoard, layMines, MINES, neighbours, reveal, toggleFlag, type Board } from "./minesweeper";

/** A board drawn as text: * is a mine, anything else is safe. */
function board(rows: string[]): Board {
  const b = emptyBoard();
  rows.join("").split("").forEach((ch, i) => (b[i].mine = ch === "*"));
  return b.map((cell, i) => ({ ...cell, adjacent: neighbours(i).filter((n) => b[n].mine).length }));
}

const at = (r: number, c: number) => r * COLS + c;

describe("layMines", () => {
  it("never puts a mine on or next to the first click", () => {
    for (let seed = 0; seed < 300; seed++) {
      let s = seed;
      const random = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
      const first = seed % 81;
      const b = layMines(emptyBoard(), first, random);
      expect(b.filter((c) => c.mine)).toHaveLength(MINES);
      for (const i of [first, ...neighbours(first)]) expect(b[i].mine).toBe(false);
    }
  });
});

describe("reveal", () => {
  const corner = board([
    "........*",
    ".........",
    ".........",
    ".........",
    ".........",
    ".........",
    ".........",
    ".........",
    "*.......*",
  ]);

  it("opens the whole empty area from an empty cell", () => {
    const { board: b, boom } = reveal(corner, at(4, 4));
    expect(boom).toBe(false);
    expect(b[at(0, 0)].open).toBe(true);
    expect(b[at(0, 7)].open).toBe(true); // the number next to the mine opens, the mine does not
    expect(b[at(0, 8)].open).toBe(false);
    expect(cleared(b)).toBe(true);
  });

  it("reports a mine", () => {
    expect(reveal(corner, at(0, 8)).boom).toBe(true);
  });

  it("leaves a flagged cell shut", () => {
    const flagged = toggleFlag(corner, at(0, 8));
    expect(reveal(flagged, at(0, 8))).toEqual({ board: flagged, boom: false });
  });

  it("opens a number's other neighbours once its mines are flagged", () => {
    const b = board([
      "*........",
      "..*......",
      ".........",
      ".........",
      ".........",
      ".........",
      ".........",
      ".........",
      ".........",
    ]);
    let s = reveal(b, at(1, 1)).board; // a 2
    expect(s[at(1, 1)].adjacent).toBe(2);
    expect(reveal(s, at(1, 1)).board).toBe(s); // no flags yet: nothing happens
    s = toggleFlag(toggleFlag(s, at(0, 0)), at(1, 2));
    const after = reveal(s, at(1, 1));
    expect(after.boom).toBe(false);
    expect(after.board[at(0, 1)].open && after.board[at(2, 2)].open).toBe(true);
  });

  it("chording onto a wrong flag sets off the real mine", () => {
    const b = board([
      "*........",
      ".........",
      ".........",
      ".........",
      ".........",
      ".........",
      ".........",
      ".........",
      ".........",
    ]);
    let s = reveal(b, at(1, 1)).board;
    s = toggleFlag(s, at(0, 1)); // wrong cell
    expect(reveal(s, at(1, 1)).boom).toBe(true);
  });
});
