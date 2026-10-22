import {
  ArrowDown,
  BookOpen,
  ClipboardCheck,
  Cpu,
  Database,
  Eye,
  FileSearch,
  MessageSquare,
  Plug,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

/**
 * How a question becomes an answer.
 *
 * Two diagrams, because they answer different questions. The
 * first is the request path - what happens, in order, to one
 * question. The second is the component map: which of the
 * twelve weeks' pieces exist and how they relate.
 *
 * Drawn in layout rather than as an image so it reflows on a
 * phone, recolours with the theme, and stays crisp.
 */
export function FlowPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[860px] px-4 py-8">
        <h1 className="text-[22px] font-semibold tracking-tight">
          How it works
        </h1>

        <p
          className="mt-1.5 text-[13.5px] leading-relaxed"
          style={{ color: "var(--app-ink-muted)" }}
        >
          One question, end to end. Everything before the
          model call is deterministic &mdash; the model
          phrases an answer the filters have already
          selected.
        </p>

        <h2 className="mt-7 mb-3 text-[15px] font-medium">
          The request path
        </h2>

        <div className="space-y-2">
          {STEPS.map((step, index) => (
            <div key={step.title}>
              <Step {...step} index={index + 1} />
              {index < STEPS.length - 1 && <Arrow />}
            </div>
          ))}
        </div>

        <h2 className="mt-9 mb-3 text-[15px] font-medium">
          What it is built from
        </h2>

        <Panel>
          <Hero
            icon={MessageSquare}
            title="Single entry point"
            body="python -m app.desk, or the chat UI. Both land on the same answering path."
          />

          <Arrow />

          <div className="grid gap-2.5 sm:grid-cols-2">
            {PILLARS.map((pillar) => (
              <Pillar key={pillar.title} {...pillar} />
            ))}
          </div>

          <Arrow />

          <Hero
            icon={ClipboardCheck}
            title="Integrated evaluation suite"
            body="32 cases against the whole application, not the parts. Assertions first, then the judge."
            muted
          />
        </Panel>

        <h2 className="mt-9 mb-3 text-[15px] font-medium">
          Where the time and money go
        </h2>

        <Panel>
          <div className="space-y-2.5">
            {BUDGET.map((row) => (
              <div
                key={row.stage}
                className="flex flex-wrap items-baseline gap-x-3 gap-y-1"
              >
                <span
                  className="w-[104px] shrink-0 font-mono text-[12px]"
                  style={{ color: "var(--app-ink)" }}
                >
                  {row.stage}
                </span>

                <span
                  className="tabular w-[76px] shrink-0 text-[12px]"
                  style={{ color: "var(--app-accent)" }}
                >
                  {row.latency}
                </span>

                <span
                  className="tabular w-[68px] shrink-0 text-[12px]"
                  style={{ color: "var(--app-accent)" }}
                >
                  {row.cost}
                </span>

                <span
                  className="min-w-0 text-[12.5px]"
                  style={{ color: "var(--app-ink-muted)" }}
                >
                  {row.why}
                </span>
              </div>
            ))}
          </div>

          <p
            className="mt-3 text-[12px] leading-relaxed"
            style={{ color: "var(--app-ink-faint)" }}
          >
            All of the spend is generation; all of the
            latency is retrieval. They are different
            bottlenecks and scale differently, which is why
            the cost fix is fewer input tokens and the
            scaling fix is a second worker.
          </p>
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------

interface StepProps {
  icon: LucideIcon;
  title: string;
  body: string;
  note?: string;
}

const STEPS: StepProps[] = [
  {
    icon: MessageSquare,
    title: "A question arrives",
    body: "From the chat UI or the command line, with the asker's employee id.",
  },
  {
    icon: UserCheck,
    title: "Resolve who is asking",
    body: "Entity and grade are read from the employee record, and the as-of date from the question.",
    note: "Before retrieval, not after. Retrieving first is how a correctly cited clause becomes a different employee's answer.",
  },
  {
    icon: ShieldCheck,
    title: "Guard",
    body: "A question about a colleague, or about a subject the corpus does not hold, is refused here.",
    note: "Before retrieval too: a pension question scores 0.61 against an annual-leave clause, so no threshold can catch it afterwards.",
  },
  {
    icon: Database,
    title: "Retrieve, filtered",
    body: "Chroma search scoped to this entity, then superseded editions dropped and the entity annex ranked above the handbook.",
    note: "Entity is enforced in the query; the edition window is applied after, because Chroma cannot express a date range.",
  },
  {
    icon: FileSearch,
    title: "Decide",
    body: "Nothing relevant means refuse. A clause saying a human decides means hand off to an HR business partner.",
    note: "A handoff is preferred over a confident guess on anything the policy marks discretionary.",
  },
  {
    icon: Cpu,
    title: "Answer — the only model call",
    body: "The model phrases what the filters selected. With no key it returns the clause verbatim instead.",
    note: "Everything above this line is deterministic, which is why the whole system stays demonstrable without an API key.",
  },
  {
    icon: Eye,
    title: "Cite and log",
    body: "Clause, version and effective date on the answer; one trace id with per-stage latency, tokens and cost in the log.",
    note: "Grade, band, tenure and leave balance never reach the log. The employee id does, because the support drill searches on it.",
  },
];

function Step({
  icon: Icon,
  title,
  body,
  note,
  index,
}: StepProps & { index: number }) {
  return (
    <div
      className="flex gap-3 rounded-xl border p-3.5"
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
        <Icon size={15} />
      </span>

      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span
            className="tabular font-mono text-[11px]"
            style={{ color: "var(--app-ink-faint)" }}
          >
            {String(index).padStart(2, "0")}
          </span>
          <h3 className="text-[14px] font-medium">
            {title}
          </h3>
        </div>

        <p
          className="mt-0.5 text-[12.5px] leading-relaxed"
          style={{ color: "var(--app-ink-muted)" }}
        >
          {body}
        </p>

        {note && (
          <p
            className="mt-1.5 border-l-2 pl-2.5 text-[12px] leading-relaxed"
            style={{
              borderColor: "var(--app-accent)",
              color: "var(--app-ink-faint)",
            }}
          >
            {note}
          </p>
        )}
      </div>
    </div>
  );
}

const PILLARS = [
  {
    icon: BookOpen,
    title: "RAG",
    body: "Retrieve policy clauses and cite them with version and effective date.",
    weeks: "Weeks 3–6",
  },
  {
    icon: Cpu,
    title: "Agent",
    body: "A hand-built loop with four enforced budgets, choosing tools and deciding when to escalate.",
    weeks: "Weeks 7–8",
  },
  {
    icon: Plug,
    title: "MCP",
    body: "Policy search and HRIS exposed over stdio; external tools discovered at runtime from config.",
    weeks: "Week 9",
  },
  {
    icon: Eye,
    title: "Observability",
    body: "One trace id per request with per-stage latency, tokens, cost, prompt version and context ids.",
    weeks: "Week 11",
  },
];

function Pillar({
  icon: Icon,
  title,
  body,
  weeks,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  weeks: string;
}) {
  return (
    <div
      className="rounded-xl border p-3.5"
      style={{
        borderColor: "var(--app-border)",
        background: "var(--app-surface)",
      }}
    >
      <div className="flex items-center justify-between">
        <span style={{ color: "var(--app-accent)" }}>
          <Icon size={15} />
        </span>
        <span
          className="font-mono text-[10.5px]"
          style={{ color: "var(--app-ink-faint)" }}
        >
          {weeks}
        </span>
      </div>

      <h3 className="mt-1.5 text-[14px] font-medium">
        {title}
      </h3>

      <p
        className="mt-0.5 text-[12.5px] leading-relaxed"
        style={{ color: "var(--app-ink-muted)" }}
      >
        {body}
      </p>
    </div>
  );
}

const BUDGET = [
  {
    stage: "resolve",
    latency: "0.1 ms",
    cost: "free",
    why: "A dictionary lookup against the employee record.",
  },
  {
    stage: "guard",
    latency: "<1 ms",
    cost: "free",
    why: "Two regexes. No model, no index.",
  },
  {
    stage: "retrieve",
    latency: "341 ms",
    cost: "free",
    why: "The embedding model runs locally, so this costs time and no money.",
  },
  {
    stage: "answer",
    latency: "~1 s",
    cost: "$0.000286",
    why: "The one model call. Input tokens dominate: prompt plus three clauses.",
  },
];

function Hero({
  icon: Icon,
  title,
  body,
  muted,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  muted?: boolean;
}) {
  return (
    <div
      className="rounded-xl border p-4 text-center"
      style={{
        borderColor: "var(--app-border)",
        background: muted
          ? "var(--app-surface-muted)"
          : "var(--app-surface)",
      }}
    >
      <span
        className="inline-grid h-8 w-8 place-items-center rounded-lg"
        style={{
          background: "var(--app-accent-soft)",
          color: "var(--app-accent)",
        }}
      >
        <Icon size={15} />
      </span>

      <h3 className="mt-1.5 text-[14px] font-medium">
        {title}
      </h3>

      <p
        className="mt-0.5 text-[12.5px] leading-relaxed"
        style={{ color: "var(--app-ink-muted)" }}
      >
        {body}
      </p>
    </div>
  );
}

function Arrow() {
  return (
    <div
      className="flex justify-center py-1.5"
      style={{ color: "var(--app-ink-faint)" }}
      aria-hidden
    >
      <ArrowDown size={15} />
    </div>
  );
}

function Panel({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-2xl border p-4"
      style={{
        borderColor: "var(--app-border)",
        background: "var(--app-canvas)",
      }}
    >
      {children}
    </div>
  );
}
