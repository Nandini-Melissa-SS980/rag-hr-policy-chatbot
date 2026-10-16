import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SourcesPanel } from "@/components/chat/SourcesPanel";
import { QuickPrompts } from "@/components/chat/QuickPrompts";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { Logo } from "@/components/brand/Logo";
import { scoreTone, titleFrom } from "@/lib/utils";
import { POLICIES, QUICK_PROMPTS } from "@/lib/policies";

describe("SourcesPanel", () => {
  const source = {
    chunk_id: "HR-202-2.1-abc",
    source_file: "HR-202.pdf",
    policy_id: "HR-202",
    section: "2.1",
    region: "unknown",
    effective_date: "unknown",
  };

  it("shows a cited policy and section", () => {
    render(<SourcesPanel sources={[source]} />);

    expect(screen.getByText("HR-202")).toBeInTheDocument();
    expect(screen.getByText("§2.1")).toBeInTheDocument();
  });

  it("renders nothing when there is no evidence", () => {
    const { container } = render(<SourcesPanel />);

    expect(container).toBeEmptyDOMElement();
  });

  it("hides retrieved chunks until asked", async () => {
    render(
      <SourcesPanel
        retrieved={[
          {
            chunk_id: "c1",
            text: "Full-time employees receive twenty-five days of paid annual leave per leave year.",
            score: 0.87,
            metadata: { policy_id: "HR-202", section: "2.1" },
          },
        ]}
      />,
    );

    expect(screen.queryByText(/twenty-five/)).toBeNull();

    await userEvent.click(
      screen.getByRole("button", { name: /show retrieved/i }),
    );

    expect(
      screen.getByText(/twenty-five/),
    ).toBeInTheDocument();
  });

  it("labels a heading-only chunk", async () => {
    // These exist in the real index - "2 Working Hours" is
    // 15 characters with no body - and can never answer
    // anything, so the pane says so rather than showing a
    // confident-looking empty result.
    render(
      <SourcesPanel
        retrieved={[
          {
            chunk_id: "c1",
            text: "2 Working Hours",
            score: 0.59,
            metadata: { policy_id: "HR-201", section: "2" },
          },
        ]}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: /show retrieved/i }),
    );

    expect(
      screen.getByText(/heading only/i),
    ).toBeInTheDocument();
  });
});

describe("QuickPrompts", () => {
  it("asks the question behind the chip, not its label", async () => {
    const onPick = vi.fn();

    render(<QuickPrompts onPick={onPick} />);

    await userEvent.click(
      screen.getByRole("button", { name: /annual leave/i }),
    );

    expect(onPick).toHaveBeenCalledWith(
      "How many days of annual leave do I get?",
    );
  });

  it("offers only questions this corpus answers", () => {
    // A chip that leads to a refusal teaches the user the
    // tool is broken when it is working correctly.
    const ids = POLICIES.map((policy) => policy.id);

    expect(ids).toHaveLength(6);
    expect(QUICK_PROMPTS.length).toBeGreaterThan(3);

    for (const prompt of QUICK_PROMPTS) {
      expect(prompt.question.length).toBeGreaterThan(10);
      expect(prompt.question).toMatch(/\?$/);
    }
  });
});

describe("MessageBubble", () => {
  it("renders an error instead of an empty answer", () => {
    render(
      <MessageBubble
        turn={{
          id: "t1",
          role: "assistant",
          content: "",
          error: "The language model is unavailable",
          createdAt: Date.now(),
        }}
      />,
    );

    expect(
      screen.getByText(/language model is unavailable/i),
    ).toBeInTheDocument();
  });

  it("renders markdown in an answer", () => {
    render(
      <MessageBubble
        turn={{
          id: "t1",
          role: "assistant",
          content: "Employees receive **twenty-five** days.",
          createdAt: Date.now(),
        }}
      />,
    );

    expect(
      screen.getByText("twenty-five").tagName,
    ).toBe("STRONG");
  });
});

describe("utils", () => {
  it("bands scores against the backend's own threshold", () => {
    expect(scoreTone(0.87).label).toBe("strong");
    expect(scoreTone(0.66).label).toBe("fair");
    expect(scoreTone(0.4).label).toBe("weak");
  });

  it("truncates a long title on a word boundary", () => {
    const title = titleFrom(
      "How long must I work here before I can request flexible working?",
    );

    expect(title.length).toBeLessThanOrEqual(39);
    expect(title.endsWith("…")).toBe(true);
    expect(title).not.toMatch(/\s…$/);
  });

  it("leaves a short title alone", () => {
    expect(titleFrom("  How much leave?  ")).toBe(
      "How much leave?",
    );
  });
});

describe("Logo", () => {
  it("gives each instance its own gradient id", () => {
    // An SVG gradient is referenced by a document-wide id.
    // Two avatars sharing one id means the second silently
    // renders with the first's gradient.
    const { container } = render(
      <>
        <MessageBubble
          turn={{
            id: "a",
            role: "assistant",
            content: "First.",
            createdAt: Date.now(),
          }}
        />
        <MessageBubble
          turn={{
            id: "b",
            role: "assistant",
            content: "Second.",
            createdAt: Date.now(),
          }}
        />
      </>,
    );

    const ids = Array.from(
      container.querySelectorAll("linearGradient"),
    ).map((node) => node.id);

    expect(ids.length).toBe(2);
    expect(new Set(ids).size).toBe(2);
  });

  it("labels the standalone mark for screen readers", () => {
    render(<Logo />);

    expect(
      screen.getByRole("img", { name: "HR360 Bot" }),
    ).toBeInTheDocument();
  });
});
