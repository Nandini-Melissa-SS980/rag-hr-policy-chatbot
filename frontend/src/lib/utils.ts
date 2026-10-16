import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function uid(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );
}

export function formatRelative(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h ago`;

  return `${Math.floor(seconds / 86_400)}d ago`;
}

/**
 * A conversation title from its first question.
 *
 * Trimmed on a word boundary so a long question does not
 * produce a title that ends mid-word.
 */
export function titleFrom(question: string): string {
  const clean = question.trim().replace(/\s+/g, " ");

  if (clean.length <= 38) return clean;

  const cut = clean.slice(0, 38);
  const lastSpace = cut.lastIndexOf(" ");

  return `${cut.slice(0, lastSpace > 18 ? lastSpace : 38)}…`;
}

/**
 * Retrieval scores run roughly 0.5-0.9 on this corpus. The
 * bands match the backend's own 0.45 abstention threshold so
 * a chip's colour means the same thing the API means.
 */
export function scoreTone(score: number): {
  label: string;
  className: string;
} {
  if (score >= 0.75)
    return {
      label: "strong",
      className: "bg-emerald-500",
    };

  if (score >= 0.6)
    return {
      label: "fair",
      className: "bg-amber-500",
    };

  return { label: "weak", className: "bg-rose-500" };
}
