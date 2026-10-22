import { Clock, Coins, Hash, Target } from "lucide-react";
import type { RequestMetrics } from "@/types/api";
import { scoreTone } from "@/lib/utils";

/**
 * What one question cost, under its answer.
 *
 * Four numbers, because four are what you act on: how well
 * retrieval matched, how long it took, how many tokens it
 * burned, and what that cost. The per-stage split sits behind
 * a hover, since the headline is the total and the split only
 * matters once you are optimising.
 */
export function MetricsBar({
  metrics,
}: {
  metrics: RequestMetrics;
}) {
  const tone = scoreTone(metrics.top_score);

  const stages = Object.entries(metrics.stages);

  // Retrieval costs latency and no money; generation costs
  // both. Naming which is which is the useful part.
  const stageHint = stages
    .map(
      ([name, stage]) =>
        `${name} ${stage.duration_ms.toFixed(0)}ms` +
        (stage.cost_usd > 0
          ? ` $${stage.cost_usd.toFixed(6)}`
          : " free"),
    )
    .join("  ·  ");

  return (
    <div
      className="mt-2.5 flex flex-wrap items-center gap-x-3.5 gap-y-1.5 rounded-lg border px-2.5 py-1.5 text-[11.5px]"
      style={{
        borderColor: "var(--app-border)",
        background: "var(--app-surface-muted)",
        color: "var(--app-ink-muted)",
      }}
      title={stageHint}
    >
      <span
        className="inline-flex items-center gap-1"
        title={`Top retrieval score (${tone.label})`}
      >
        <Target size={11} />
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${tone.className}`}
        />
        <span className="tabular">
          {metrics.top_score.toFixed(3)}
        </span>
        <span style={{ color: "var(--app-ink-faint)" }}>
          · {metrics.retrieved} chunks
        </span>
      </span>

      <span
        className="inline-flex items-center gap-1"
        title={stageHint || "Total wall clock"}
      >
        <Clock size={11} />
        <span className="tabular">
          {formatMs(metrics.duration_ms)}
        </span>
      </span>

      <span
        className="inline-flex items-center gap-1"
        title="Prompt + completion tokens"
      >
        <Hash size={11} />
        <span className="tabular">
          {metrics.total_tokens.toLocaleString()} tok
        </span>
      </span>

      <span
        className="inline-flex items-center gap-1"
        title={
          metrics.cost_usd > 0
            ? "Tokens at the configured list price"
            : "No cost recorded - either no model was called, or token prices are unset"
        }
      >
        <Coins size={11} />
        <span className="tabular">
          {formatCost(metrics.cost_usd)}
        </span>
      </span>

      <span
        className="ml-auto font-mono text-[10.5px]"
        style={{ color: "var(--app-ink-faint)" }}
        title={`${metrics.model} · prompt ${metrics.prompt_version}`}
      >
        {metrics.trace_id}
      </span>
    </div>
  );
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;

  return `${(ms / 1000).toFixed(2)}s`;
}

function formatCost(usd: number): string {
  // Below a tenth of a cent, six decimals say more than a
  // rounded "$0.00" that reads as free.
  if (usd === 0) return "$0";

  if (usd < 0.001) return `$${usd.toFixed(6)}`;

  return `$${usd.toFixed(4)}`;
}
