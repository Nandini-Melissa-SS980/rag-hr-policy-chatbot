import { useQuery } from "@tanstack/react-query";
import { POLICIES } from "@/lib/policies";
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
          HR360 Bot answers only from these six documents
          {stats.data
            ? `, split into ${stats.data.count} searchable passages`
            : ""}
          . A question outside them should be refused rather
          than answered.
        </p>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {POLICIES.map((policy) => (
            <article
              key={policy.id}
              className="rounded-xl border p-4"
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
            </article>
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
          parental leave, pensions, expenses, private medical
          cover, and training budgets. Questions on these
          should return a refusal — if one is answered
          confidently, that is a bug worth reporting.
        </div>
      </div>
    </div>
  );
}
