/**
 * Conversation history, in the browser.
 *
 * The backend has no persistence - /api/chat is stateless -
 * so history lives in localStorage rather than being faked
 * against an endpoint that does not exist. Every read and
 * write is guarded: storage throws in private windows and
 * returns nothing when site data is cleared, and the app has
 * to render correctly in both cases.
 */

import { useCallback, useEffect, useState } from "react";
import type { ChatTurn, Conversation } from "@/types/api";
import { titleFrom, uid } from "@/lib/utils";

const KEY = "hr360.conversations.v1";

const MAX_STORED = 50;

function read(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(conversations: Conversation[]) {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify(conversations.slice(0, MAX_STORED)),
    );
  } catch {
    // Quota or a blocked store. History is a convenience, so
    // losing it must never break the chat.
  }
}

export function useConversations() {
  const [conversations, setConversations] = useState<
    Conversation[]
  >(() => read());

  const [activeId, setActiveId] = useState<string | null>(
    () => read()[0]?.id ?? null,
  );

  useEffect(() => {
    write(conversations);
  }, [conversations]);

  const active =
    conversations.find((item) => item.id === activeId) ?? null;

  const startNew = useCallback(() => {
    setActiveId(null);
  }, []);

  const select = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const remove = useCallback(
    (id: string) => {
      setConversations((current) =>
        current.filter((item) => item.id !== id),
      );

      setActiveId((current) => (current === id ? null : current));
    },
    [],
  );

  const clearAll = useCallback(() => {
    setConversations([]);
    setActiveId(null);
  }, []);

  /** Appends a turn, opening a conversation if none is live. */
  const appendTurn = useCallback(
    (turn: ChatTurn, conversationId?: string | null) => {
      const target = conversationId ?? activeId;

      if (target) {
        setConversations((current) =>
          current.map((item) =>
            item.id === target
              ? {
                  ...item,
                  turns: [...item.turns, turn],
                  updatedAt: Date.now(),
                }
              : item,
          ),
        );

        return target;
      }

      const created: Conversation = {
        id: uid(),
        title: titleFrom(turn.content),
        turns: [turn],
        updatedAt: Date.now(),
      };

      setConversations((current) => [created, ...current]);
      setActiveId(created.id);

      return created.id;
    },
    [activeId],
  );

  /** Replaces one turn in place, for a pending -> settled swap. */
  const updateTurn = useCallback(
    (
      conversationId: string,
      turnId: string,
      patch: Partial<ChatTurn>,
    ) => {
      setConversations((current) =>
        current.map((item) =>
          item.id === conversationId
            ? {
                ...item,
                turns: item.turns.map((turn) =>
                  turn.id === turnId
                    ? { ...turn, ...patch }
                    : turn,
                ),
                updatedAt: Date.now(),
              }
            : item,
        ),
      );
    },
    [],
  );

  return {
    conversations,
    active,
    activeId,
    startNew,
    select,
    remove,
    clearAll,
    appendTurn,
    updateTurn,
  };
}
