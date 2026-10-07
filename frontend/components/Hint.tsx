"use client";

import { useId, useState } from "react";

/** A "?" next to a label: shows a short explanation on hover, keyboard focus or tap. */
export default function Hint({ label, children }: { label: string; children: React.ReactNode }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <span className="hint" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className="hint-btn"
        aria-label={`${label}是什麼？`}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      >
        ?
      </button>
      {open && (
        <span role="tooltip" id={id} className="hint-pop">
          {children}
        </span>
      )}
    </span>
  );
}
