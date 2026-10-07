"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { api, Person } from "@/lib/api";

// One fetch per page load; the backend caches the list too
let people: Promise<Person[]> | null = null;

const MAX_SHOWN = 8;

function matches(p: Person, q: string): boolean {
  const s = q.trim().toLowerCase();
  return !s || p.display_name.toLowerCase().includes(s) || p.email.includes(s);
}

/** Email combobox suggesting people recently assigned work in ADO; any other email can still be typed. */
export default function PersonInput({
  value,
  onChange,
  placeholder,
  label,
  style,
}: {
  value: string;
  onChange: (email: string) => void;
  placeholder?: string;
  label?: string;
  style?: React.CSSProperties;
}) {
  const listId = useId();
  const [options, setOptions] = useState<Person[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    people ??= api.adoPeople().catch(() => {
      people = null; // not connected to ADO yet: plain input, try again next time
      return [];
    });
    people.then(setOptions);
  }, []);

  const shown = useMemo(
    () => options.filter((p) => matches(p, value) && p.email !== value.trim().toLowerCase()).slice(0, MAX_SHOWN),
    [options, value],
  );
  const expanded = open && shown.length > 0;

  useEffect(() => setActive(0), [value]);

  function pick(p: Person) {
    onChange(p.email);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => (expanded ? (i + 1) % shown.length : 0));
    } else if (e.key === "ArrowUp" && expanded) {
      e.preventDefault();
      setActive((i) => (i - 1 + shown.length) % shown.length);
    } else if (e.key === "Enter" && expanded) {
      e.preventDefault();
      pick(shown[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div
      ref={box}
      className="person-input"
      style={style}
      onBlur={(e) => {
        if (!box.current?.contains(e.relatedTarget as Node)) setOpen(false);
      }}
    >
      <input
        type="email"
        role="combobox"
        aria-label={label}
        aria-expanded={expanded}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={expanded ? `${listId}-${active}` : undefined}
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        autoComplete="off"
      />
      {expanded && (
        <ul id={listId} role="listbox" className="person-list">
          {shown.map((p, i) => (
            <li
              key={p.email}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "on" : ""}
              onMouseDown={(e) => e.preventDefault()} // keep focus in the input
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(p)}
            >
              <span className="avatar" aria-hidden="true">
                {p.display_name.trim().charAt(0).toUpperCase()}
              </span>
              <span className="who">
                <b>{p.display_name}</b>
                <span>{p.email}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
