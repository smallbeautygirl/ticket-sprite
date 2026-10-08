import { describe, expect, it } from "vitest";
import { touches } from "./FireflyGame";

// "Open Question" at 13px is about 85px wide, drawn from the glow's right edge
const fly = { x: 72, y: 100 };
const word = (dx: number, dy: number) => ({ kind: "word" as const, x: fly.x + dx, y: fly.y + dy, r: 11, w: 85 });

describe("touches", () => {
  it("collects a word by its glow or anywhere on its label", () => {
    expect(touches(fly, word(0, 0))).toBe(true);
    expect(touches(fly, word(-50, 0))).toBe(true); // the glow has already passed; the label has not
    expect(touches(fly, word(-95, 2))).toBe(true);
    expect(touches(fly, word(-50, 18))).toBe(true);
  });

  it("misses a word well above or behind", () => {
    expect(touches(fly, word(-50, 40))).toBe(false);
    expect(touches(fly, word(-130, 0))).toBe(false);
  });

  it("fog has no label", () => {
    expect(touches(fly, { kind: "fog", x: fly.x - 50, y: fly.y, r: 20, w: 85 })).toBe(false);
  });
});
