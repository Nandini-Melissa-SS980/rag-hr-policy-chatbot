import { useState } from "react";
import { ChevronRight, FileText } from "lucide-react";
import type { SearchResult, Source } from "@/types/api";
import { policyById } from "@/lib/policies";
import { cn, scoreTone } from "@/lib/utils";

interface SourcesPanelProps {
  sources?: Source[];
  retrieved?: SearchResult[];
}

/**
 * The citation evidence under an answer.
 *
 * This is the part of the product worth protecting: an answer
 * the reader can check against the passage it came from. The
 * cited chips are what the model claimed; the expandable
 * retrieved list is what the index actually served, and the
 * two being different is exactly the failure the Week-11
 * drill was about.
 */
export function SourcesPanel({
  sources,
  retrieved,
}: SourcesPanelProps) {
  const [open, setOpen] = useState(false);

  const hasCited = Boolean(sources?.length);
  const hasRetrieved = Boolean(retrieved?.length);

  if (!hasCited && !hasRetrieved) return null;

  return (
    <div className="mt-3">
      {hasCited && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className="text-[11.5px] font-medium"
            style={{ color: "var(--app-ink-faint)" }}
          >
            Sources
          </span>

          {sources!.map((source) => {
            const policy = policyById(source.policy_id);

            return (
              <span
                key={source.chunk_id}
                title={policy?.title ?? source.source_file}
                className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11.5px]"
                style={{
                  borderColor: "var(--app-border)",
                  background: "var(--app-surface-muted)",
                  color: "var(--app-ink-muted)",
                }}
              >
                <FileText size={10} />
                {source.policy_id}
                <span style={{ color: "var(--app-ink-faint)" }}>
                  §{source.section}
                </span>
              </span>
            );
          })}
        </div>
      )}

      {hasRetrieved && (
        <div className="mt-2">
          <button
            onClick={() => setOpen((value) => !value)}
            className="flex items-center gap-1 text-[11.5px] transition-colors"
            style={{ color: "var(--app-ink-faint)" }}
            aria-expanded={open}
          >
            <ChevronRight
              size={12}
              className={cn(
                "transition-transform",
                open && "rotate-90",
              )}
            />
            {open ? "Hide" : "Show"} retrieved chunks (
            {retrieved!.length})
          </button>

          {open && (
            <ul className="mt-2 space-y-1.5">
              {retrieved!.map((chunk) => {
                const tone = scoreTone(chunk.score);
                const empty = chunk.text.trim().length < 40;

                return (
                  <li
                    key={chunk.chunk_id}
                    className="rounded-lg border p-2.5"
                    style={{
                      borderColor: "var(--app-border)",
                      background: "var(--app-surface-muted)",
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-[11.5px] font-medium">
                        {chunk.metadata.policy_id}
                        <span
                          style={{
                            color: "var(--app-ink-faint)",
                          }}
                        >
                          {" "}
                          §{chunk.metadata.section}
                        </span>
                      </span>

                      {empty && (
                        <span
                          className="rounded px-1 py-px text-[9.5px] font-medium tracking-wide uppercase"
                          style={{
                            background: "var(--app-border)",
                            color: "var(--app-ink-faint)",
                          }}
                          title="This chunk is a heading with no body text"
                        >
                          heading only
                        </span>
                      )}

                      <span
                        className="ml-auto font-mono text-[11px]"
                        style={{ color: "var(--app-ink-faint)" }}
                      >
                        {chunk.score.toFixed(3)}
                      </span>
                    </div>

                    <div
                      className="mt-1.5 h-1 overflow-hidden rounded-full"
                      style={{ background: "var(--app-border)" }}
                    >
                      <div
                        className={cn(
                          "h-full rounded-full",
                          tone.className,
                        )}
                        style={{
                          width: `${Math.max(4, Math.min(100, chunk.score * 100))}%`,
                        }}
                      />
                    </div>

                    <p
                      className="mt-1.5 line-clamp-3 text-[12px] leading-relaxed"
                      style={{ color: "var(--app-ink-muted)" }}
                    >
                      {chunk.text.trim() || "—"}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
