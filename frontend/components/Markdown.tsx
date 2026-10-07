"use client";

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

export default function Markdown({ text, inline = false }: { text: string; inline?: boolean }) {
  const html = useMemo(() => {
    const raw = (inline ? marked.parseInline(text || "", { async: false }) : marked.parse(text || "", { async: false })) as string;
    return typeof window === "undefined" ? "" : DOMPurify.sanitize(raw);
  }, [text, inline]);
  if (inline) return <span className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
  return <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}
