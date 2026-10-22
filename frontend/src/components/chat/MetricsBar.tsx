import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { RequestMetrics } from "@/types/api";
import { cn, scoreTone } from "@/lib/utils";

/**
 * What one question cost, under its answer.
 *
 * Four labelled figures, because four are what you act on:
 * how well retrieval matched, how long it took, how many
 * tokens it burned, and what that cost. The per-stage split
 * expands, since the headline is the total and the split only
 * matters once you are optimising.
 *
 * Shown on failed requests too. Retrieval still ran, so the
 * score and the time are real; tokens and cost are zero
 * because no model was reached, which is the honest figure
 * rather than a missing one.
 */
export function MetricsBar({
  metrics,
}: {
  metrics: RequestMetrics;
}) {
  const [open, setOpen] = useState(false);

  const tone = scoreTone(metrics.top_score);

  const stages = Object.entries(metrics.stages);

  const failed = metrics.trace_id === "generation-failed";

  const retrievalOnly =
    metrics.trace_id === "retrieval-only";

  return (
    <div
      className="mt-2.5 rounded-lg border px-3 py-2"
      style={{
        borderColor: "var(--app-border)",
        background: "var(--app-surface-muted)",
      }}
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
        <Figure label="Score">
          <span
            className={cn(
              "inline-block h-1.5 w-1.5 rounded-full",
              tone.className,
            )}
          />
          <span className="tabular">
            {metrics.top_score.toFixed(3)}
          </span>
          <span style={{ color: "var(--app-ink-faint)" }}>
            / {metrics.retrieved} chunks
          </span>
        </Figure>

        <Figure label="Time">
          <span className="tabular">
            {formatMs(metrics.duration_ms)}
          </span>
        </Figure>

        <Figure label="Tokens">
          <span className="tabular">
            {metrics.total_tokens.toLocaleString()}
          </span>
        </Figure>

        <Figure label="Cost">
          <span className="tabular">
            {formatCost(metrics.cost_usd)}
          </span>
        </Figure>

        {stages.length > 0 && (
          <button
            onClick={() => setOpen((value) => !value)}
            className="ml-auto flex items-center gap-0.5 text-[11.5px]"
            style={{ color: "var(--app-ink-faint)" }}
            aria-expanded={open}
          >
            <ChevronRight
              size={11}
              className={cn(
                "transition-transform",
                open && "rotate-90",
              )}
            />
            per stage
          </button>
        )}
      </div>

      {(failed || retrievalOnly) && (
        <p
          className="mt-1.5 text-[11px]"
          style={{ color: "var(--app-ink-faint)" }}
        >
          {failed
            ? "Retrieval ran; no model was reached, so tokens and cost are zero."
            : "Retrieval only — no model was called, so tokens and cost are zero."}
        </p>
      )}

      {open && stages.length > 0 && (
        <div
          className="mt-2 space-y-1 border-t pt-2"
          style={{ borderColor: "var(--app-border)" }}
        >
          {stages.map(([name, stage]) => (
            <div
              key={name}
              className="flex flex-wrap items-baseline gap-x-4 text-[11.5px]"
            >
              <span
                className="w-[84px] shrink-0 font-mono"
                style={{ color: "var(--app-ink)" }}
              >
                {name}
              </span>

              <span
                className="tabular w-[72px] shrink-0"
                style={{ color: "var(--app-ink-muted)" }}
              >
                {formatMs(stage.duration_ms)}
              </span>

              <span
                className="tabular w-[84px] shrink-0"
                style={{ color: "var(--app-ink-muted)" }}
              >
                {(
                  stage.input_tokens +
                  stage.output_tokens
                ).toLocaleString()}{" "}
                tok
              </span>

              <span
                className="tabular"
                style={{ color: "var(--app-ink-muted)" }}
              >
                {stage.cost_usd > 0
                  ? formatCost(stage.cost_usd)
                  : "free"}
              </span>
            </div>
          ))}

          <div
            className="pt-1 font-mono text-[10.5px]"
            style={{ color: "var(--app-ink-faint)" }}
          >
            {metrics.trace_id}
            {metrics.model !== "none" &&
              ` · ${metrics.model} · prompt ${metrics.prompt_version}`}
          </div>
        </div>
      )}
    </div>
  );
}

function Figure({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <span className="flex items-center gap-1.5 text-[12px]">
      <span
        className="font-medium"
        style={{ color: "var(--app-ink-faint)" }}
      >
        {label}:
      </span>
      <span
        className="flex items-center gap-1"
        style={{ color: "var(--app-ink)" }}
      >
        {children}
      </span>
    </span>
  );
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;

  return `${(ms / 1000).toFixed(2)} s`;
}

function formatCost(usd: number): string {
  // Below a tenth of a cent, six decimals say more than a
  // rounded "$0.00" that reads as free.
  if (usd === 0) return "$0.000000";

  if (usd < 0.001) return `$${usd.toFixed(6)}`;

  return `$${usd.toFixed(4)}`;
}
