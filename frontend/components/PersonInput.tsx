"use client";

import { useEffect, useId, useState } from "react";
import { api, Person } from "@/lib/api";

// One fetch per page load; the backend caches the list too
let people: Promise<Person[]> | null = null;

/** Email input that suggests people recently assigned work in ADO; any other email can still be typed. */
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

  useEffect(() => {
    people ??= api.adoPeople().catch(() => {
      people = null; // not connected to ADO yet: plain input, try again next time
      return [];
    });
    people.then(setOptions);
  }, []);

  return (
    <>
      <input
        type="email"
        list={listId}
        aria-label={label}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        style={style}
      />
      <datalist id={listId}>
        {options.map((p) => (
          <option key={p.email} value={p.email} label={p.display_name} />
        ))}
      </datalist>
    </>
  );
}
