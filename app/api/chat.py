from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    SearchResult,
)
from app.services.generator import (
    Generator,
)
from app.services.retriever import (
    Retriever,
)


router = APIRouter(
    prefix="/api",
    tags=["RAG"],
)


retriever = Retriever()
generator = Generator()


@router.get("/health")
def health():
    return {
        "status": "ok"
    }


@router.get("/stats")
def stats():

    return {
        "message": (
            "Vector store is available."
        ),
        "count": (
            retriever.vector_store.count()
        ),
    }


@router.post(
    "/search",
    response_model=list[SearchResult],
)
def search(request: ChatRequest):

    results = retriever.retrieve(
        question=request.question,
        top_k=5,
        region=request.region,
    )

    return results


@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
):

    results = retriever.retrieve(
        question=request.question,
        top_k=5,
        region=request.region,
    )

    if not retriever.has_good_match(
        results
    ):
        return ChatResponse(
            answer=(
                "I couldn't find information "
                "about this in the provided "
                "HR policy documents."
            ),
            sources=[],
        )

    generated = generator.generate(
        question=request.question,
        results=results,
    )

    source_map = {
        result["metadata"].get(
            "chunk_id"
        ): result["metadata"]
        for result in results
    }

    sources = []

    for source in generated.get(
        "sources",
        [],
    ):

        chunk_id = source.get(
            "chunk_id"
        )

        metadata = source_map.get(
            chunk_id
        )

        if not metadata:
            continue

        sources.append(
            {
                "chunk_id": chunk_id,
                "source_file": metadata.get(
                    "source_file",
                    "",
                ),
                "policy_id": metadata.get(
                    "policy_id",
                    "",
                ),
                "section": metadata.get(
                    "section",
                    "",
                ),
                "region": metadata.get(
                    "region",
                    "",
                ),
                "effective_date": metadata.get(
                    "effective_date",
                    "",
                ),
            }
        )

    return ChatResponse(
        answer=generated.get(
            "answer",
            "No answer was generated.",
        ),
        sources=sources,
    )