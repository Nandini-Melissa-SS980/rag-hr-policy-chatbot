from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        description="Question about the HR policies",
    )

    region: str | None = Field(
        default=None,
        description="Optional region filter",
    )


class Source(BaseModel):
    chunk_id: str
    source_file: str
    policy_id: str
    section: str
    region: str
    effective_date: str


class StageMetrics(BaseModel):
    """
    One stage of one request. Retrieval costs latency and no
    money; generation costs both. Reporting them separately is
    the whole point - a single total hides which half to fix.
    """

    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class RequestMetrics(BaseModel):
    """
    What one question cost, shown next to its answer.

    Already recorded on every trace by app/observability.py;
    this carries it to the UI so it is visible per question
    rather than only greppable in logs/requests.jsonl.
    """

    trace_id: str
    model: str = ""
    prompt_version: str = ""
    duration_ms: float = 0.0
    total_tokens: int = 0
    cost_usd: float = 0.0
    top_score: float = 0.0
    retrieved: int = 0
    stages: dict[str, StageMetrics] = {}


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    metrics: RequestMetrics | None = None


class SearchResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    metadata: dict