"use client";

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

export default function Markdown({ text }: { text: string }) {
  const html = useMemo(() => {
    const raw = marked.parse(text || "", { async: false }) as string;
    return typeof window === "undefined" ? "" : DOMPurify.sanitize(raw);
  }, [text]);
  return <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}
