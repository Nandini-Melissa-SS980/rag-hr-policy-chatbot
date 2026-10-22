/**
 * The one place that talks to FastAPI.
 *
 * Every call goes through `request`, so error handling is
 * uniform and the 429 the backend currently returns on
 * generation surfaces as a typed ApiError the UI can explain
 * rather than a raw stack trace.
 */

import type {
  ChatRequest,
  ChatResponse,
  SearchResult,
  StatsResponse,
  PolicyText,
  SystemInfo,
} from "@/types/api";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;

  /** True when the backend is up but the model is unfunded. */
  isQuota: boolean;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.isQuota =
      status === 429 ||
      /quota|credit|rate limit/i.test(message);
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "content-type": "application/json" },
      ...init,
    });
  } catch {
    // fetch only rejects on a network-level failure, which
    // here almost always means uvicorn is not running.
    throw new ApiError(
      0,
      "Cannot reach the backend. Is uvicorn running on port 8000?",
    );
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;

    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      // A non-JSON error body is fine; the status line stands.
    }

    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  stats: () => request<StatsResponse>("/stats"),

  /** What the running system is made of. */
  system: () => request<SystemInfo>("/system"),

  /** One policy's full text, read from the PDF. */
  policyText: (policyId: string) =>
    request<PolicyText>(
      `/system/policies/${encodeURIComponent(policyId)}`,
    ),

  /** Retrieval only. Needs no model, so it works at 429. */
  search: (body: ChatRequest) =>
    request<SearchResult[]>("/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** Retrieval plus generation. Needs a funded key. */
  chat: (body: ChatRequest) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
