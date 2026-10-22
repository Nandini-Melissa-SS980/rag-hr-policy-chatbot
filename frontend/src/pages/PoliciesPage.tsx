import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { POLICIES, type Policy } from "@/lib/policies";
import { PolicyModal } from "@/components/policies/PolicyModal";
import { api } from "@/services/api";

/**
 * What the bot can actually answer from.
 *
 * Worth a page of its own: the commonest failure in a
 * policy assistant is a confident answer about a subject the
 * corpus does not cover, so telling people what IS covered
 * is a product feature rather than documentation.
 */
export function PoliciesPage() {
  const [open, setOpen] = useState<Policy | null>(
    null,
  );

  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    retry: false,
  });

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[760px] px-4 py-8">
        <h1 className="text-[22px] font-semibold tracking-tight">
          Indexed policies
        </h1>

        <p
          className="mt-1.5 text-[13.5px] leading-relaxed"
          style={{ color: "var(--app-ink-muted)" }}
        >
          HR360 Bot answers only from these{" "}
          {POLICIES.length} documents
          {stats.isLoading
            ? ", loading the passage count…"
            : stats.data
              ? `, split into ${stats.data.count} searchable passages`
              : " (passage count unavailable — the backend is not reachable)"}
          . A question outside them should be refused rather
          than answered.
        </p>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {POLICIES.map((policy) => (
            <button
              key={policy.id}
              onClick={() => setOpen(policy)}
              className="cursor-pointer rounded-xl border p-4 text-left transition-shadow hover:shadow-md"
              style={{
                borderColor: "var(--app-border)",
                background: "var(--app-surface)",
              }}
            >
              <div className="flex items-center gap-2">
                <span
                  className="grid h-7 w-7 place-items-center rounded-lg"
                  style={{
                    background: "var(--app-accent-soft)",
                    color: "var(--app-accent)",
                  }}
                >
                  <policy.icon size={14} />
                </span>

                <span
                  className="font-mono text-[11.5px]"
                  style={{ color: "var(--app-ink-faint)" }}
                >
                  {policy.id}
                </span>
              </div>

              <h2 className="mt-2.5 text-[14px] font-medium">
                {policy.title}
              </h2>

              <p
                className="mt-1 text-[12.5px] leading-relaxed"
                style={{ color: "var(--app-ink-muted)" }}
              >
                {policy.summary}
              </p>
            </button>
          ))}
        </div>

        <div
          className="mt-6 rounded-xl border p-4 text-[12.5px] leading-relaxed"
          style={{
            borderColor: "var(--app-border)",
            background: "var(--app-surface-muted)",
            color: "var(--app-ink-muted)",
          }}
        >
          <strong style={{ color: "var(--app-ink)" }}>
            Not covered:
          </strong>{" "}
          notice periods and resignation, maternity and
          parental leave, pensions, private medical cover,
          and training budgets. Questions on these should
          return a refusal — if one is answered confidently,
          that is a bug worth reporting.
          <p className="mt-2">
            <strong style={{ color: "var(--app-ink)" }}>
              Partly covered:
            </strong>{" "}
            home-office equipment and the desk allowance are
            in HR-206 §5, but travel and other expenses are
            not. A question about claiming expenses may be
            answered from the equipment clause, which is the
            wrong answer to the right-sounding question.
          </p>
        </div>
      </div>

      {open && (
        <PolicyModal
          policy={open}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
