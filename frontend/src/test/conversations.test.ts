import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useConversations } from "@/stores/conversations";
import type { ChatTurn } from "@/types/api";

function turn(
  role: ChatTurn["role"],
  content: string,
): ChatTurn {
  return {
    id: `${role}-${content}-${Math.random()}`,
    role,
    content,
    createdAt: Date.now(),
  };
}

beforeEach(() => {
  localStorage.clear();
});

describe("useConversations", () => {
  it("opens a conversation on the first turn", () => {
    const { result } = renderHook(() =>
      useConversations(),
    );

    expect(result.current.conversations).toHaveLength(0);

    act(() => {
      result.current.appendTurn(
        turn("user", "How much leave do I get?"),
      );
    });

    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.active?.title).toBe(
      "How much leave do I get?",
    );
  });

  it("keeps both turns of one exchange together", () => {
    // The bug this guards: appendTurn reads activeId from a
    // closure, so a second call in the same tick would open
    // a SECOND conversation unless the caller threads the id
    // returned by the first. ChatPage threads it.
    const { result } = renderHook(() =>
      useConversations(),
    );

    let id = "";

    act(() => {
      id = result.current.appendTurn(
        turn("user", "How much leave?"),
      );
    });

    act(() => {
      result.current.appendTurn(
        turn("assistant", "Twenty-five days."),
        id,
      );
    });

    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.conversations[0].turns).toHaveLength(
      2,
    );
  });

  it("settles a pending turn in place", () => {
    const { result } = renderHook(() =>
      useConversations(),
    );

    const pending = turn("assistant", "");

    let id = "";

    act(() => {
      id = result.current.appendTurn(
        turn("user", "How much leave?"),
      );
    });

    act(() => {
      result.current.appendTurn(pending, id);
    });

    act(() => {
      result.current.updateTurn(id, pending.id, {
        content: "Twenty-five days.",
      });
    });

    const turns = result.current.conversations[0].turns;

    expect(turns).toHaveLength(2);
    expect(turns[1].content).toBe("Twenty-five days.");
  });

  it("starts a fresh conversation after New chat", () => {
    const { result } = renderHook(() =>
      useConversations(),
    );

    act(() => {
      result.current.appendTurn(turn("user", "First"));
    });

    act(() => {
      result.current.startNew();
    });

    act(() => {
      result.current.appendTurn(turn("user", "Second"));
    });

    expect(result.current.conversations).toHaveLength(2);
  });

  it("survives storage being unavailable", () => {
    // Private windows and cleared site data both make this
    // throw. History is a convenience, so losing it must
    // never break the chat.
    const getItem = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new Error("blocked");
      });

    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("blocked");
      });

    const { result } = renderHook(() =>
      useConversations(),
    );

    expect(() => {
      act(() => {
        result.current.appendTurn(
          turn("user", "How much leave?"),
        );
      });
    }).not.toThrow();

    expect(result.current.conversations).toHaveLength(1);

    getItem.mockRestore();
    setItem.mockRestore();
  });

  it("removes a conversation and clears the selection", () => {
    const { result } = renderHook(() =>
      useConversations(),
    );

    let id = "";

    act(() => {
      id = result.current.appendTurn(
        turn("user", "How much leave?"),
      );
    });

    act(() => {
      result.current.remove(id);
    });

    expect(result.current.conversations).toHaveLength(0);
    expect(result.current.activeId).toBeNull();
  });
});
