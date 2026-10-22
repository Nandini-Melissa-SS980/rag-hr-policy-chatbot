import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  MessageBubble,
  PendingBubble,
} from "@/components/chat/MessageBubble";
import { Logo } from "@/components/brand/Logo";
import { PromptComposer } from "@/components/chat/PromptComposer";
import { QuickPrompts } from "@/components/chat/QuickPrompts";
import { api, ApiError } from "@/services/api";
import { uid } from "@/lib/utils";
import type { ChatTurn, Conversation } from "@/types/api";

interface ChatPageProps {
  active: Conversation | null;
  appendTurn: (
    turn: ChatTurn,
    conversationId?: string | null,
  ) => string;
  updateTurn: (
    conversationId: string,
    turnId: string,
    patch: Partial<ChatTurn>,
  ) => void;
}

export function ChatPage({
  active,
  appendTurn,
  updateTurn,
}: ChatPageProps) {
  const [retrievalOnly, setRetrievalOnly] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const turns = active?.turns ?? [];

  const ask = useMutation({
    mutationFn: async (question: string) => {
      const userTurn: ChatTurn = {
        id: uid(),
        role: "user",
        content: question,
        createdAt: Date.now(),
      };

      const conversationId = appendTurn(userTurn);

      const startedAt = Date.now();

      // Retrieval always runs: in retrieval-only mode it is
      // the answer, and otherwise it is the evidence shown
      // under the generated one. It also means a 429 on
      // generation still leaves the user something real.
      const retrieved = await api.search({ question });

      if (retrievalOnly) {
        // /api/search writes no trace, so these are measured
        // here rather than read back from one. Tokens and
        // cost are genuinely zero: no model was called.
        // Labelled "retrieval-only" so a zero is never read
        // as a missing measurement.
        appendTurn(
          {
            id: uid(),
            role: "assistant",
            metrics: {
              trace_id: "retrieval-only",
              model: "none",
              prompt_version: "-",
              duration_ms: Date.now() - startedAt,
              total_tokens: 0,
              cost_usd: 0,
              top_score: retrieved[0]?.score ?? 0,
              retrieved: retrieved.length,
              stages: {},
            },
            content: retrieved.length
              ? `Retrieved ${retrieved.length} passage${retrieved.length === 1 ? "" : "s"} from the policy index. No answer was generated.`
              : "Nothing in the policy documents matched that question.",
            retrieved,
            createdAt: Date.now(),
          },
          conversationId,
        );

        return;
      }

      const pendingId = uid();

      appendTurn(
        {
          id: pendingId,
          role: "assistant",
          content: "",
          createdAt: Date.now(),
        },
        conversationId,
      );

      try {
        const response = await api.chat({ question });

        updateTurn(conversationId, pendingId, {
          content: response.answer,
          sources: response.sources,
          metrics: response.metrics,
          retrieved,
        });
      } catch (error) {
        const message =
          error instanceof ApiError && error.isQuota
            ? "The language model is unavailable — the OpenAI account has no credits. Retrieval still works: switch to Retrieval only to see the passages this question matches."
            : error instanceof Error
              ? error.message
              : "Something went wrong.";

        updateTurn(conversationId, pendingId, {
          error: message,
          retrieved,
        });
      }
    },
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length, ask.isPending]);

  const empty = turns.length === 0;

  // The pending turn is rendered by PendingBubble, so an
  // empty assistant turn is not drawn twice.
  const visible = turns.filter(
    (turn) =>
      !(
        turn.role === "assistant" &&
        !turn.content &&
        !turn.error
      ),
  );

  const waiting =
    ask.isPending ||
    turns.some(
      (turn) =>
        turn.role === "assistant" &&
        !turn.content &&
        !turn.error,
    );

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        {/* polite, not assertive: an answer arriving should be
            announced once the reader is idle, not interrupt
            them mid-sentence. */}
        <div
          className="mx-auto w-full max-w-[760px] px-4 py-6"
          aria-live="polite"
          aria-busy={waiting}
        >
          {empty ? (
            <div className="pt-10 pb-4 text-center sm:pt-14">
              <Logo
                size={72}
                className="mx-auto"
                gradientId="hr360-welcome"
              />

              <h1 className="mt-4 text-[30px] leading-tight font-semibold tracking-tight sm:text-[34px]">
                Ask HR
                <span style={{ color: "var(--app-accent)" }}>
                  360
                </span>{" "}
                Bot
              </h1>

              <p
                className="mx-auto mt-2 max-w-[420px] text-[14px] leading-relaxed"
                style={{ color: "var(--app-ink-muted)" }}
              >
                Answers come only from the indexed HR policies,
                with the passage they came from shown
                alongside.
              </p>
            </div>
          ) : (
            visible.map((turn) => (
              <MessageBubble key={turn.id} turn={turn} />
            ))
          )}

          {waiting && <PendingBubble />}

          <div ref={bottom} />
        </div>
      </div>

      <div
        className="border-t"
        style={{
          borderColor: "var(--app-border)",
          background: "var(--app-surface)",
        }}
      >
        <div className="mx-auto w-full max-w-[760px] px-4 py-4">
          <PromptComposer
            onSubmit={(question) => ask.mutate(question)}
            disabled={waiting}
            retrievalOnly={retrievalOnly}
            onRetrievalOnlyChange={setRetrievalOnly}
            autoFocus={empty}
          />

          {empty && (
            <QuickPrompts
              onPick={(question) => ask.mutate(question)}
              disabled={waiting}
            />
          )}
        </div>
      </div>
    </div>
  );
}
