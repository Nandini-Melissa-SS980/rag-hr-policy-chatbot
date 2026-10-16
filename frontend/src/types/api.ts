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

export interface ChatResponse {
  answer: string;
  sources: Source[];
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
