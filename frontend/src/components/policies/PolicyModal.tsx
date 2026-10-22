import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/services/api";
import type { Policy } from "@/lib/policies";

/**
 * One policy's full text, read from the PDF the app ingests.
 *
 * Deliberately the PDF rather than the Markdown source: what
 * a reader sees here is what the retriever chunked, so if the
 * two ever diverge this is where it shows.
 */
export function PolicyModal({
  policy,
  onClose,
}: {
  policy: Policy;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ["policy", policy.id],
    queryFn: () => api.policyText(policy.id),
    retry: false,
  });

  // Escape closes, and the body is locked so the page behind
  // does not scroll under the dialog.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", onKey);

    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${policy.id} ${policy.title}`}
    >
      <div
        className="w-full max-w-[760px] rounded-2xl border shadow-xl"
        style={{
          borderColor: "var(--app-border)",
          background: "var(--app-surface)",
        }}
        // The dialog itself must not close on its own
        // clicks, only the scrim behind it.
        onClick={(event) => event.stopPropagation()}
      >
        <header
          className="sticky top-0 flex items-start gap-3 rounded-t-2xl border-b px-5 py-4"
          style={{
            borderColor: "var(--app-border)",
            background: "var(--app-surface)",
          }}
        >
          <span
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg"
            style={{
              background: "var(--app-accent-soft)",
              color: "var(--app-accent)",
            }}
          >
            <policy.icon size={16} />
          </span>

          <div className="min-w-0 flex-1">
            <div
              className="font-mono text-[11.5px]"
              style={{ color: "var(--app-ink-faint)" }}
            >
              {policy.id}
              {query.data
                ? ` · ${query.data.pages} page${
                    query.data.pages === 1 ? "" : "s"
                  }`
                : ""}
            </div>

            <h2 className="text-[16px] font-semibold tracking-tight">
              {policy.title}
            </h2>
          </div>

          <button
            onClick={onClose}
            className="rounded-md p-1"
            style={{ color: "var(--app-ink-muted)" }}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </header>

        <div className="px-5 py-4">
          {query.isLoading && (
            <p
              className="text-[13px]"
              style={{ color: "var(--app-ink-muted)" }}
            >
              Reading the PDF…
            </p>
          )}

          {query.isError && (
            <p
              className="text-[13px]"
              style={{ color: "var(--app-ink-muted)" }}
            >
              Could not read {policy.id}. Is the backend
              running?
            </p>
          )}

          {query.data && (
            <>
              <dl
                className="mb-4 grid grid-cols-1 gap-x-6 gap-y-1 rounded-lg border p-3 text-[12px] sm:grid-cols-2"
                style={{
                  borderColor: "var(--app-border)",
                  background: "var(--app-surface-muted)",
                }}
              >
                {Object.entries(query.data.header)
                  .filter(([key]) => key !== "title")
                  .map(([key, value]) => (
                    <div key={key} className="flex gap-2">
                      <dt
                        style={{
                          color: "var(--app-ink-faint)",
                        }}
                      >
                        {key}
                      </dt>
                      <dd className="font-medium">
                        {value}
                      </dd>
                    </div>
                  ))}
              </dl>

              <PolicyBody text={query.data.text} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * The policy text, with numbered headings picked out.
 *
 * The PDF has no styling to carry over, so headings are
 * recognised the same way the chunker recognises them - by
 * the section number at the start of a line. If a heading
 * renders as body text here, the chunker very likely missed
 * it too.
 */
function PolicyBody({ text }: { text: string }) {
  const blocks = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <div className="space-y-2">
      {blocks.map((line, index) => {
        const heading = /^(\d+(?:\.\d+)?)\s+(.+)$/.exec(
          line,
        );

        if (heading) {
          const top = !heading[1].includes(".");

          return (
            <h3
              key={index}
              className={
                top
                  ? "pt-2 text-[14px] font-semibold"
                  : "pt-1.5 text-[13px] font-medium"
              }
            >
              <span
                className="mr-2 font-mono text-[12px]"
                style={{ color: "var(--app-accent)" }}
              >
                {heading[1]}
              </span>
              {heading[2]}
            </h3>
          );
        }

        return (
          <p
            key={index}
            className="text-[13px] leading-relaxed"
            style={{ color: "var(--app-ink-muted)" }}
          >
            {line}
          </p>
        );
      })}
    </div>
  );
}
