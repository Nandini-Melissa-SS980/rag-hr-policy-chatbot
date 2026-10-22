import { useQuery } from "@tanstack/react-query";
import {
  Boxes,
  Coins,
  Cpu,
  Eye,
  FileStack,
  Network,
  Package,
  Scissors,
  Terminal,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/services/api";
import type { PackageInfo, SystemInfo } from "@/types/api";

/**
 * What this system is made of.
 *
 * Every value is fetched from /api/system, which reads the
 * modules that actually govern the behaviour - the threshold
 * off the retriever's own signature, the provider off config,
 * the chunk count off the live index. A hardcoded spec sheet
 * would drift the first time someone changed a default.
 */
export function SystemPage() {
  const query = useQuery({
    queryKey: ["system"],
    queryFn: api.system,
    retry: false,
  });

  if (query.isLoading) {
    return (
      <Shell>
        <p style={{ color: "var(--app-ink-muted)" }}>
          Reading the running configuration…
        </p>
      </Shell>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Shell>
        <p style={{ color: "var(--app-ink-muted)" }}>
          Could not reach the backend. Is uvicorn running
          on port 8000?
        </p>
      </Shell>
    );
  }

  const info: SystemInfo = query.data;

  return (
    <Shell>
      <h1 className="text-[22px] font-semibold tracking-tight">
        System
      </h1>

      <p
        className="mt-1.5 text-[13.5px] leading-relaxed"
        style={{ color: "var(--app-ink-muted)" }}
      >
        {info.app.description} Every value below is read
        from the running configuration, not written down
        here &mdash; so it cannot drift from what the app
        actually does.
      </p>

      <Section icon={Terminal} title="Runtime">
        <Row label="Python" value={info.runtime.python} mono />
        <Row
          label="Platform"
          value={info.runtime.platform}
          mono
          small
        />
      </Section>

      <Section icon={Package} title="Backend packages">
        <PackageTable packages={info.stack.backend} />
      </Section>

      <Section icon={Package} title="Frontend packages">
        <PackageTable packages={info.stack.frontend} />
        <Note>{info.stack.note}</Note>
      </Section>

      <Section icon={Cpu} title="Model">
        <Row label="Provider" value={info.model.provider} mono />
        <Row label="Model" value={info.model.model} mono />
        <Row label="Endpoint" value={info.model.endpoint} mono small />
        <Row
          label="OpenAI key"
          value={info.model.openai_key}
          tone={
            info.model.openai_key === "configured"
              ? "good"
              : "faint"
          }
        />
        <Row
          label="Gemini key"
          value={info.model.gemini_key}
          tone={
            info.model.gemini_key === "configured"
              ? "good"
              : "faint"
          }
        />
        <Note>{info.model.note}</Note>
      </Section>

      <Section icon={FileStack} title="Prompt">
        <Row
          label="Current version"
          value={info.prompt.current_version}
          mono
        />
        <Row
          label="Available"
          value={info.prompt.available.join(", ")}
          mono
        />
        <Note>{info.prompt.note}</Note>
      </Section>

      <Section icon={Boxes} title="Retrieval">
        <Row
          label="Embedding model"
          value={info.retrieval.embedding_model}
          mono
          small
        />
        <Row
          label="Reranker"
          value={info.retrieval.rerank_model}
          mono
          small
        />
        <Row
          label="Vector store"
          value={info.retrieval.vector_store}
        />
        <Row label="Distance" value={info.retrieval.distance} mono />
        <Row
          label="Chunks indexed"
          value={String(info.retrieval.chunks_indexed)}
          mono
        />
        <Row
          label="top_k"
          value={String(info.retrieval.top_k)}
          mono
        />
        <Row
          label="Abstain below"
          value={String(info.retrieval.abstain_below)}
          mono
        />
        <Row
          label="Policies"
          value={info.retrieval.policies_indexed.join(" · ")}
          mono
          small
        />
      </Section>

      <Section icon={Scissors} title="Chunking strategies">
        {info.chunking.map((strategy) => (
          <Card
            key={strategy.name}
            title={strategy.name}
            body={strategy.detail}
          />
        ))}
      </Section>

      <Section icon={Wrench} title="Agent">
        <Row label="Loop" value={info.agent.loop} />
        <Row
          label="Budgets"
          value={info.agent.budgets.join(" · ")}
          mono
          small
        />
        <Note>{info.agent.budget_note}</Note>

        <div className="mt-2 space-y-1.5">
          {info.agent.tools.map((tool) => (
            <Card
              key={tool.name}
              title={tool.name}
              body={`Reads ${tool.reads}.`}
            />
          ))}
        </div>

        <Note>{info.agent.tool_note}</Note>
      </Section>

      <Section icon={Network} title="MCP">
        {info.mcp.exposed.map((server) => (
          <Card
            key={server.server}
            title={server.server}
            body={
              server.tools.join(", ") +
              (server.scoped_by
                ? ` — scoped by ${server.scoped_by}`
                : "")
            }
          />
        ))}
        <Note>{info.mcp.consumed}</Note>
        <Note>{info.mcp.isolation}</Note>
      </Section>

      <Section icon={Eye} title="Observability">
        <Row label="Log" value={info.observability.log} mono small />
        <Row
          label="Exporter"
          value={info.observability.exporter}
          small
        />
        <div className="mt-1.5 space-y-1">
          {info.observability.per_request.map((field) => (
            <div
              key={field}
              className="text-[12.5px]"
              style={{ color: "var(--app-ink-muted)" }}
            >
              · {field}
            </div>
          ))}
        </div>
        <Note>{info.observability.redaction}</Note>
      </Section>

      <Section icon={Coins} title="Cost">
        <Row
          label="Input"
          value={`$${info.cost.input_per_1m_usd} / 1M tokens`}
          mono
        />
        <Row
          label="Output"
          value={`$${info.cost.output_per_1m_usd} / 1M tokens`}
          mono
        />
        <Note>{info.cost.note}</Note>
      </Section>
    </Shell>
  );
}

function Shell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[760px] px-4 py-8">
        {children}
      </div>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: LucideIcon;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-6">
      <h2 className="mb-2.5 flex items-center gap-1.5 text-[14px] font-medium">
        <span
          className="grid h-6 w-6 place-items-center rounded-md"
          style={{
            background: "var(--app-accent-soft)",
            color: "var(--app-accent)",
          }}
        >
          <Icon size={13} />
        </span>
        {title}
      </h2>

      <div
        className="rounded-xl border p-3.5"
        style={{
          borderColor: "var(--app-border)",
          background: "var(--app-surface)",
        }}
      >
        {children}
      </div>
    </section>
  );
}

function Row({
  label,
  value,
  mono,
  small,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  small?: boolean;
  tone?: "good" | "faint";
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-0.5">
      <span
        className="w-[128px] shrink-0 text-[12.5px]"
        style={{ color: "var(--app-ink-faint)" }}
      >
        {label}
      </span>
      <span
        className={[
          small ? "text-[11.5px]" : "text-[13px]",
          mono ? "font-mono" : "",
          "min-w-0 break-all",
        ].join(" ")}
        style={{
          color:
            tone === "good"
              ? "#059669"
              : tone === "faint"
                ? "var(--app-ink-faint)"
                : "var(--app-ink)",
        }}
      >
        {value}
      </span>
    </div>
  );
}

function PackageTable({
  packages,
}: {
  packages: PackageInfo[];
}) {
  return (
    <div className="space-y-0.5">
      {packages.map((pkg) => (
        <div
          key={pkg.name}
          className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-0.5"
        >
          <span
            className="w-[168px] shrink-0 font-mono text-[12px]"
            style={{ color: "var(--app-ink)" }}
          >
            {pkg.name}
          </span>
          <span
            className="tabular w-[82px] shrink-0 font-mono text-[11.5px]"
            style={{
              color:
                pkg.version === "not installed"
                  ? "#dc2626"
                  : "var(--app-accent)",
            }}
          >
            {pkg.version}
          </span>
          <span
            className="min-w-0 text-[12.5px]"
            style={{ color: "var(--app-ink-muted)" }}
          >
            {pkg.purpose}
          </span>
        </div>
      ))}
    </div>
  );
}

function Card({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div
      className="mt-1.5 rounded-lg border p-2.5"
      style={{
        borderColor: "var(--app-border)",
        background: "var(--app-surface-muted)",
      }}
    >
      <div className="font-mono text-[12px] font-medium">
        {title}
      </div>
      <div
        className="mt-0.5 text-[12.5px] leading-relaxed"
        style={{ color: "var(--app-ink-muted)" }}
      >
        {body}
      </div>
    </div>
  );
}

function Note({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <p
      className="mt-2 text-[12px] leading-relaxed"
      style={{ color: "var(--app-ink-faint)" }}
    >
      {children}
    </p>
  );
}
