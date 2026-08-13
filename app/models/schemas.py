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


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


class SearchResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    metadata: dict