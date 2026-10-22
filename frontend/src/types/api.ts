/**
 * Mirrors app/models/schemas.py.
 *
 * These are the shapes the FastAPI backend actually returns.
 * Keep them in step with the Pydantic models - a field
 * invented here is a field the UI will render as undefined.
 */

export interface ChatRequest {
  question: string;
  region?: string | null;
}

/** One cited passage, as /api/chat returns it. */
export interface Source {
  chunk_id: string;
  source_file: string;
  policy_id: string;
  section: string;
  region: string;
  effective_date: string;
}

/** One stage of one request, as the trace recorded it. */
export interface StageMetrics {
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

/**
 * What one question cost.
 *
 * A projection of the trace the backend already wrote, not a
 * second measurement - so what the UI shows and what
 * logs/requests.jsonl holds cannot disagree.
 */
export interface RequestMetrics {
  trace_id: string;
  model: string;
  prompt_version: string;
  duration_ms: number;
  total_tokens: number;
  cost_usd: number;
  top_score: number;
  retrieved: number;
  stages: Record<string, StageMetrics>;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  metrics?: RequestMetrics | null;
}

/** One retrieved chunk, as /api/search returns it. */
export interface SearchResult {
  chunk_id: string;
  text: string;
  score: number;
  metadata: {
    policy_id?: string;
    section?: string;
    source_file?: string;
    region?: string;
    effective_date?: string;
    page_number?: number;
    chunking_strategy?: string;
  };
}

export interface StatsResponse {
  message: string;
  count: number;
}

/** A turn in the transcript. */
export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  /** Populated in retrieval-only mode, and on demand. */
  retrieved?: SearchResult[];
  /** Per-question score, latency, tokens and cost. */
  metrics?: RequestMetrics | null;
  /** Set when the request failed, so the UI can explain. */
  error?: string;
  createdAt: number;
}

export interface Conversation {
  id: string;
  title: string;
  turns: ChatTurn[];
  updatedAt: number;
}

export interface PackageInfo {
  name: string;
  version: string;
  purpose: string;
}

/** Served by /api/system. Mirrors app/api/system.py. */
export interface SystemInfo {
  app: { name: string; description: string };
  runtime: { python: string; platform: string };
  stack: {
    backend: PackageInfo[];
    frontend: PackageInfo[];
    note: string;
  };
  model: {
    provider: string;
    model: string;
    openai_key: string;
    gemini_key: string;
    endpoint: string;
    note: string;
  };
  prompt: {
    current_version: string;
    available: string[];
    note: string;
  };
  retrieval: {
    embedding_model: string;
    rerank_model: string;
    vector_store: string;
    distance: string;
    top_k: number;
    abstain_below: number;
    chunks_indexed: number;
    policies_indexed: string[];
  };
  chunking: { name: string; detail: string }[];
  agent: {
    loop: string;
    budgets: string[];
    budget_note: string;
    tools: { name: string; reads: string }[];
    tool_note: string;
  };
  mcp: {
    exposed: {
      server: string;
      tools: string[];
      scoped_by?: string;
    }[];
    consumed: string;
    isolation: string;
  };
  observability: {
    log: string;
    per_request: string[];
    exporter: string;
    langsmith: string;
    redaction: string;
  };
  cost: {
    input_per_1m_usd: number;
    output_per_1m_usd: number;
    note: string;
  };
}

/** Served by /api/system/policies/{id}. */
export interface PolicyText {
  policy_id: string;
  header: Record<string, string>;
  text: string;
  pages: number;
}
