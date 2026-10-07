// 螢火蟲小精靈. "logo" is a simplified head that stays legible at ~28px.
type Pose = "logo" | "head" | "reading" | "ticket";

const INK = "var(--sprite-ink)";
const GLOW = "#F4C542";
const FACE = "#FFF6E5";
const WING = "#D9EEF0";
const BLUSH = "#F6B8A0";

function Blush({ y }: { y: number }) {
  return (
    <>
      <ellipse cx="45" cy={y} rx="5" ry="3" fill={BLUSH} stroke="none" />
      <ellipse cx="75" cy={y} rx="5" ry="3" fill={BLUSH} stroke="none" />
    </>
  );
}

function Body() {
  return (
    <>
      <circle cx="60" cy="100" r="16" fill={GLOW} stroke="none" opacity="0.35" />
      <ellipse cx="34" cy="70" rx="16" ry="10" transform="rotate(-30 34 70)" fill={WING} />
      <ellipse cx="86" cy="70" rx="16" ry="10" transform="rotate(30 86 70)" fill={WING} />
      <ellipse cx="60" cy="98" rx="11" ry="9" fill={GLOW} />
      <path d="M52 46 Q46 32 38 26" />
      <path d="M68 46 Q74 32 82 26" />
      <circle cx="38" cy="26" r="5" fill={GLOW} />
      <circle cx="82" cy="26" r="5" fill={GLOW} />
      <circle cx="60" cy="66" r="24" fill={FACE} />
    </>
  );
}

function Art({ pose }: { pose: Pose }) {
  switch (pose) {
    case "logo":
      return (
        <>
          <ellipse cx="60" cy="100" rx="14" ry="11" fill={GLOW} />
          <path d="M50 44 Q44 30 36 24" />
          <path d="M70 44 Q76 30 84 24" />
          <circle cx="34" cy="22" r="8" fill={GLOW} />
          <circle cx="86" cy="22" r="8" fill={GLOW} />
          <circle cx="60" cy="66" r="26" fill={FACE} />
          <circle cx="50" cy="66" r="5" fill={INK} stroke="none" />
          <circle cx="70" cy="66" r="5" fill={INK} stroke="none" />
        </>
      );
    case "head":
      return (
        <>
          <Body />
          <circle cx="51" cy="66" r="3" fill={INK} stroke="none" />
          <circle cx="69" cy="66" r="3" fill={INK} stroke="none" />
          <Blush y={74} />
          <path d="M55 76 Q60 81 65 76" />
        </>
      );
    case "reading":
      return (
        <>
          <circle className="sprite-glow" cx="60" cy="96" r="24" fill={GLOW} stroke="none" opacity="0.3" />
          <ellipse cx="34" cy="58" rx="16" ry="10" transform="rotate(-30 34 58)" fill={WING} />
          <ellipse cx="86" cy="58" rx="16" ry="10" transform="rotate(30 86 58)" fill={WING} />
          <path d="M52 34 Q46 20 38 14" />
          <path d="M68 34 Q74 20 82 14" />
          <circle cx="38" cy="14" r="5" fill={GLOW} />
          <circle cx="82" cy="14" r="5" fill={GLOW} />
          <circle cx="60" cy="56" r="24" fill={FACE} />
          <path d="M49 60 Q51 58 53 60" />
          <path d="M67 60 Q69 58 71 60" />
          <Blush y={64} />
          <path d="M30 86 L60 92 L90 86 L90 108 L60 114 L30 108Z" fill="#FFFFFF" />
          <path d="M60 92 L60 114" />
          <path d="M38 95 L52 98" />
          <path d="M68 98 L82 95" />
        </>
      );
    case "ticket":
      return (
        <>
          <Body />
          <path d="M48 66 Q51 62 54 66" />
          <path d="M66 66 Q69 62 72 66" />
          <Blush y={74} />
          <path d="M54 75 Q60 83 66 75" />
          <g transform="rotate(-12 100 92)">
            <rect x="86" y="82" width="28" height="20" rx="3" fill={GLOW} />
            <path d="M94 85 L94 99" strokeDasharray="2 3" />
          </g>
          <path stroke="#E9A23B" d="M104 60 l1.5 4 4 1.5 -4 1.5 -1.5 4 -1.5 -4 -4 -1.5 4 -1.5z" />
        </>
      );
  }
}

export default function Sprite({ pose = "head", size = 64 }: { pose?: Pose; size?: number }) {
  return (
    <svg
      className="sprite"
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      stroke={INK}
      strokeWidth={pose === "logo" ? 6 : size < 80 ? 3 : 2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <Art pose={pose} />
    </svg>
  );
}
