from fastapi import APIRouter, HTTPException
from openai import OpenAIError, RateLimitError

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    SearchResult,
)
from app.services.answering import (
    answer_question,
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
    """
    Every request is traced. `answer_question` writes
    one row to logs/requests.jsonl with per-stage
    latency, tokens, cost, the prompt version and the
    retrieved context ids - which is what makes a
    complaint about a past answer findable.
    """

    try:

        generated, trace = answer_question(
            request.question,
            retriever,
            generator,
            top_k=5,
            region=request.region,
        )

    except RateLimitError as error:

        # Surfaced as 429 with a readable detail rather
        # than letting it become an opaque 500. A client
        # cannot tell "the model is unfunded" from "the
        # server is broken" without this, and the two
        # need completely different responses: one is a
        # billing problem, the other is a page.
        #
        # The trace is already written - answer_question
        # records the retrieval span and the error before
        # re-raising - so a failed request is still
        # findable in the log.
        raise HTTPException(
            status_code=429,
            detail=(
                "The language model is unavailable: "
                f"{error}"
            ),
        ) from error

    except OpenAIError as error:

        raise HTTPException(
            status_code=502,
            detail=(
                "The language model could not be "
                f"reached: {type(error).__name__}"
            ),
        ) from error

    if trace["abstained"] or not generated.get(
        "answer"
    ):

        return ChatResponse(
            answer=generated.get(
                "answer",
                (
                    "I couldn't find information "
                    "about this in the provided "
                    "HR policy documents."
                ),
            ),
            sources=[],
        )

    # Built from the context the trace recorded, not
    # from a second retrieval call. Re-running the
    # search would cost a second embed and could
    # return something other than what was logged,
    # which would make the trace a description of a
    # request that did not happen.
    source_map = {
        item["chunk_id"]: item
        for item in trace["labels"].get(
            "context",
            [],
        )
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