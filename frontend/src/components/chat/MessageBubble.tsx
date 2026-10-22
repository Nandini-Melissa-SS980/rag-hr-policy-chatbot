import { useId } from "react";
import ReactMarkdown from "react-markdown";
import { User, TriangleAlert } from "lucide-react";
import { BotGlyph } from "@/components/brand/Logo";
import type { ChatTurn } from "@/types/api";
import { MetricsBar } from "./MetricsBar";
import { SourcesPanel } from "./SourcesPanel";

function Avatar({ role }: { role: ChatTurn["role"] }) {
  const isUser = role === "user";

  // An SVG gradient is referenced by a document-wide id, and
  // a transcript renders many of these. Without a unique id
  // per instance every avatar after the first silently reuses
  // the first one's gradient.
  const gradientId = useId();

  return (
    <span
      className="grid h-7 w-7 shrink-0 place-items-center rounded-lg"
      style={{
        background: isUser
          ? "var(--app-surface-muted)"
          : "var(--app-accent)",
        color: isUser ? "var(--app-ink-muted)" : "#fff",
      }}
      aria-hidden
    >
      {isUser ? (
        <User size={14} />
      ) : (
        <BotGlyph
          size={17}
          className="text-white"
          gradientId={gradientId}
        />
      )}
    </span>
  );
}

export function PendingBubble() {
  return (
    <div className="flex gap-3 px-1 py-3">
      <Avatar role="assistant" />
      <div className="flex items-center gap-1 pt-1.5">
        <span
          className="dot-flashing flex gap-1"
          aria-label="Thinking"
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--app-ink-faint)" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--app-ink-faint)" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--app-ink-faint)" }}
          />
        </span>
      </div>
    </div>
  );
}

export function MessageBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";

  return (
    <div className="flex gap-3 px-1 py-3">
      <Avatar role={turn.role} />

      <div className="min-w-0 flex-1">
        <div
          className="mb-1 text-[11.5px] font-medium"
          style={{ color: "var(--app-ink-faint)" }}
        >
          {isUser ? "You" : "HR360 Bot"}
        </div>

        {turn.error ? (
          <div
            className="flex items-start gap-2 rounded-lg border p-3 text-[13px] leading-relaxed"
            style={{
              borderColor: "var(--app-danger-border)",
              background: "var(--app-danger-surface)",
              color: "var(--app-danger-ink)",
            }}
            role="alert"
          >
            <TriangleAlert size={15} className="mt-px shrink-0" />
            <div>{turn.error}</div>
          </div>
        ) : (
          <div
            className="answer-prose text-[14px] leading-relaxed"
            style={{ color: "var(--app-ink)" }}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap">
                {turn.content}
              </p>
            ) : (
              <ReactMarkdown>{turn.content}</ReactMarkdown>
            )}
          </div>
        )}

        {!isUser && turn.metrics && (
          <MetricsBar metrics={turn.metrics} />
        )}

        {!isUser && (
          <SourcesPanel
            sources={turn.sources}
            retrieved={turn.retrieved}
          />
        )}
      </div>
    </div>
  );
}
