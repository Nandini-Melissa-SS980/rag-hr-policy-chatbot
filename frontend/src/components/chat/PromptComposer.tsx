import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { ArrowUp, Database, MessageSquareText } from "lucide-react";
import { cn } from "@/lib/utils";

interface PromptComposerProps {
  onSubmit: (question: string) => void;
  disabled?: boolean;
  retrievalOnly: boolean;
  onRetrievalOnlyChange: (value: boolean) => void;
  autoFocus?: boolean;
}

const MAX_HEIGHT = 180;

export function PromptComposer({
  onSubmit,
  disabled,
  retrievalOnly,
  onRetrievalOnlyChange,
  autoFocus,
}: PromptComposerProps) {
  const [value, setValue] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);

  // Grow with the content, then scroll. A fixed-height box
  // hides the start of a long question while it is typed.
  useEffect(() => {
    const node = textarea.current;
    if (!node) return;

    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus) textarea.current?.focus();
  }, [autoFocus]);

  function send() {
    const question = value.trim();
    if (!question || disabled) return;

    onSubmit(question);
    setValue("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    send();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter breaks the line.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border shadow-sm"
      style={{
        borderColor: "var(--app-border)",
        background: "var(--app-surface)",
      }}
    >
      <textarea
        ref={textarea}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder="Ask about an HR policy…"
        aria-label="Ask about an HR policy"
        className="w-full resize-none bg-transparent px-4 pt-3.5 pb-2 text-[14px] leading-relaxed outline-none"
        style={{ color: "var(--app-ink)" }}
      />

      <div className="flex items-center gap-2 px-3 pt-1 pb-3">
        <button
          type="button"
          onClick={() => onRetrievalOnlyChange(!retrievalOnly)}
          title={
            retrievalOnly
              ? "Showing retrieved passages only. No model call, so this works without API credits."
              : "Generating an answer from the retrieved passages."
          }
          className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] font-medium transition-colors"
          style={{
            borderColor: retrievalOnly
              ? "var(--app-accent)"
              : "var(--app-border)",
            background: retrievalOnly
              ? "var(--app-accent-soft)"
              : "transparent",
            color: retrievalOnly
              ? "var(--app-accent)"
              : "var(--app-ink-muted)",
          }}
          aria-pressed={retrievalOnly}
        >
          {retrievalOnly ? (
            <Database size={13} />
          ) : (
            <MessageSquareText size={13} />
          )}
          {retrievalOnly ? "Retrieval only" : "Generate answer"}
        </button>

        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className={cn(
            "ml-auto grid h-8 w-8 place-items-center rounded-lg text-white transition-opacity",
            (disabled || !value.trim()) &&
              "cursor-not-allowed opacity-40",
          )}
          style={{ background: "var(--app-accent)" }}
          aria-label="Send"
        >
          <ArrowUp size={16} />
        </button>
      </div>
    </form>
  );
}
