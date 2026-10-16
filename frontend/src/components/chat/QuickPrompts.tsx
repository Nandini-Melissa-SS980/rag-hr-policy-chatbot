import { QUICK_PROMPTS } from "@/lib/policies";

interface QuickPromptsProps {
  onPick: (question: string) => void;
  disabled?: boolean;
}

export function QuickPrompts({
  onPick,
  disabled,
}: QuickPromptsProps) {
  return (
    <div className="mt-8">
      <p
        className="mb-3 text-center text-[12.5px] font-medium"
        style={{ color: "var(--app-ink-muted)" }}
      >
        Choose a quick prompt
      </p>

      <div className="flex flex-wrap justify-center gap-2">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt.label}
            onClick={() => onPick(prompt.question)}
            disabled={disabled}
            title={prompt.question}
            className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12.5px] transition-colors disabled:opacity-50"
            style={{
              borderColor: "var(--app-border)",
              background: "var(--app-surface)",
              color: "var(--app-ink-muted)",
            }}
            onMouseEnter={(event) => {
              if (disabled) return;
              event.currentTarget.style.borderColor =
                "var(--app-accent)";
              event.currentTarget.style.color =
                "var(--app-accent)";
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.borderColor =
                "var(--app-border)";
              event.currentTarget.style.color =
                "var(--app-ink-muted)";
            }}
          >
            <prompt.icon size={13} />
            {prompt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
