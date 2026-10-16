import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "@/App";

beforeEach(() => {
  localStorage.clear();

  // The shell queries /api/stats on mount. The chunk count is
  // not what these tests are about, so it is stubbed rather
  // than requiring a live backend.
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        message: "Vector store is available.",
        count: 65,
      }),
    }),
  );
});

describe("New chat", () => {
  it("returns to the chat page from Policies", async () => {
    // The bug this guards: New chat cleared the active
    // conversation but never navigated, so pressing it on
    // /policies changed invisible state and looked dead.
    render(<App />);

    await userEvent.click(
      screen.getByRole("link", { name: /policies/i }),
    );

    expect(
      await screen.findByText(/indexed policies/i),
    ).toBeInTheDocument();

    // Two New chat buttons exist, one per surface; both must
    // navigate, so each is exercised.
    const buttons = screen.getAllByRole("button", {
      name: /new chat/i,
    });

    expect(buttons.length).toBeGreaterThan(0);

    await userEvent.click(buttons[0]);

    await waitFor(() => {
      expect(
        screen.queryByText(/indexed policies/i),
      ).toBeNull();
    });

    expect(
      screen.getByPlaceholderText(/ask about an hr policy/i),
    ).toBeInTheDocument();
  });

  it("offers the header New chat button too", async () => {
    render(<App />);

    await userEvent.click(
      screen.getByRole("link", { name: /policies/i }),
    );

    const buttons = screen.getAllByRole("button", {
      name: /new chat/i,
    });

    await userEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(
        screen.queryByText(/indexed policies/i),
      ).toBeNull();
    });
  });
});
