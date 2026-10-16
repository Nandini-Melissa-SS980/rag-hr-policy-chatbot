import { describe, expect, it, vi, afterEach } from "vitest";
import { ApiError, api } from "@/services/api";

function mockFetch(
  status: number,
  body: unknown,
  ok = status < 400,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      statusText: String(status),
      json: async () => body,
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApiError", () => {
  it("flags a 429 as a quota problem", () => {
    expect(new ApiError(429, "slow down").isQuota).toBe(true);
  });

  it("flags a credit message as a quota problem", () => {
    expect(
      new ApiError(500, "You have no credits remaining")
        .isQuota,
    ).toBe(true);
  });

  it("does not flag an ordinary failure", () => {
    expect(new ApiError(500, "boom").isQuota).toBe(false);
  });
});

describe("api", () => {
  it("returns search results", async () => {
    mockFetch(200, [
      {
        chunk_id: "HR-202-2.1-x",
        text: "Full-time employees receive twenty-five days",
        score: 0.87,
        metadata: { policy_id: "HR-202", section: "2.1" },
      },
    ]);

    const results = await api.search({
      question: "leave?",
    });

    expect(results).toHaveLength(1);
    expect(results[0].metadata.policy_id).toBe("HR-202");
  });

  it("raises a typed error when generation is unfunded", async () => {
    mockFetch(429, { detail: "no credits remaining" }, false);

    await expect(
      api.chat({ question: "leave?" }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 429,
      isQuota: true,
    });
  });

  it("explains an unreachable backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("refused")),
    );

    await expect(
      api.health(),
    ).rejects.toThrow(/uvicorn/i);
  });
});
