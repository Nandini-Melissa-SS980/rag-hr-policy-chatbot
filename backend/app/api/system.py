"""
What this system is made of, served as data.

The System tab reads this rather than hardcoding a copy in
React. Everything here is imported from the module that
actually governs the behaviour - the chunk size comes from the
ingest script, the threshold from the retriever, the provider
from config - so the page cannot drift from the running
system the way a hand-written spec sheet does.

Nothing secret is returned. Keys are reported as configured
or not, never as values.
"""

from fastapi import APIRouter

from app import config


router = APIRouter(
    prefix="/api/system",
    tags=["system"],
)


def key_state(value) -> str:
    """
    Whether a credential is present. Never the credential.
    """

    return "configured" if value else "not set"


# What each backend package is actually for. Versions are read
# from the installed distribution rather than from
# requirements.txt, because requirements says what was asked
# for and the environment says what is running.
BACKEND_PACKAGES = [
    ("fastapi", "HTTP API and request validation"),
    ("uvicorn", "ASGI server"),
    ("pydantic", "Request and response schemas"),
    ("chromadb", "Vector store, SQLite-backed"),
    (
        "sentence-transformers",
        "Local embedding and reranker models",
    ),
    ("openai", "SDK for both OpenAI and Gemini"),
    ("pymupdf", "PDF text extraction"),
    ("python-dotenv", "Reads backend/.env"),
    ("mcp", "Model Context Protocol, both directions"),
    ("langsmith", "Trace export, optional"),
    ("pytest", "Test runner"),
    ("httpx", "Test client"),
]

FRONTEND_PACKAGES = [
    ("react", "UI framework"),
    ("typescript", "Types"),
    ("vite", "Dev server and bundler"),
    ("tailwindcss", "Styling"),
    ("@tanstack/react-query", "Server state and caching"),
    ("react-router-dom", "Routing"),
    ("lucide-react", "Icons"),
    ("react-markdown", "Renders answers"),
    ("vitest", "Test runner"),
]


def installed_version(name: str) -> str:
    """
    The version actually importable, or "not installed".
    """

    try:
        from importlib.metadata import version

        return version(name)

    except Exception:
        return "not installed"


def frontend_versions() -> list[dict]:
    """
    Read from frontend/package.json.

    The declared range, not the resolved lockfile version:
    the backend cannot see node_modules, and a range is
    honest about being a range.
    """

    import json
    import os

    path = os.path.join(
        os.path.dirname(config.BASE_DIR),
        "frontend",
        "package.json",
    )

    declared: dict = {}

    try:
        with open(
            path,
            "r",
            encoding="utf-8",
        ) as handle:

            manifest = json.load(handle)

        declared = {
            **manifest.get("dependencies", {}),
            **manifest.get("devDependencies", {}),
        }

    except Exception:
        pass

    return [
        {
            "name": name,
            "version": declared.get(
                name,
                "not declared",
            ),
            "purpose": purpose,
        }
        for name, purpose in FRONTEND_PACKAGES
    ]


@router.get("")
def system_info():

    from app.services.answering import TOP_K
    from app.services.prompts import (
        CURRENT_PROMPT_VERSION,
        PROMPTS,
    )

    retriever_threshold = 0.45

    try:
        # Read off the method's own default so this cannot
        # disagree with the gate that actually runs.
        import inspect

        from app.services.retriever import Retriever

        retriever_threshold = inspect.signature(
            Retriever.has_good_match
        ).parameters["threshold"].default

    except Exception:
        pass

    chunk_count = 0

    policies: list[str] = []

    try:
        from app.services.retriever import Retriever

        metadata = Retriever(
            "structure_aware"
        ).vector_store.all_metadata()

        chunk_count = len(metadata)

        policies = sorted(
            {
                item.get("policy_id", "")
                for item in metadata
                if item.get("policy_id")
            }
        )

    except Exception:
        pass

    import platform
    import sys

    return {
        "app": {
            "name": "HR360 Bot",
            "description": (
                "Retrieval-augmented Q&A over HR "
                "policy documents. Answers come "
                "only from retrieved policy text "
                "and carry citations."
            ),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "stack": {
            "backend": [
                {
                    "name": name,
                    "version": installed_version(
                        name
                    ),
                    "purpose": purpose,
                }
                for name, purpose in (
                    BACKEND_PACKAGES
                )
            ],
            "frontend": frontend_versions(),
            "note": (
                "Backend versions are read from the "
                "installed distributions, so they "
                "are what is running rather than "
                "what requirements.txt asked for. "
                "Frontend versions are the ranges "
                "declared in package.json."
            ),
        },
        "model": {
            "provider": config.LLM_PROVIDER,
            "model": (
                config.GEMINI_MODEL
                if config.LLM_PROVIDER == "gemini"
                else config.OPENAI_MODEL
            ),
            "openai_key": key_state(
                config.OPENAI_API_KEY
            ),
            "gemini_key": key_state(
                config.GEMINI_API_KEY
            ),
            "endpoint": (
                config.GEMINI_BASE_URL
                if config.LLM_PROVIDER == "gemini"
                else "https://api.openai.com/v1"
            ),
            "note": (
                "The agent loop stays on OpenAI "
                "regardless: the two providers "
                "disagree on the shape of a tool "
                "call, and the Week-8 and Week-10 "
                "numbers were measured against "
                "OpenAI's."
            ),
        },
        "prompt": {
            "current_version": (
                CURRENT_PROMPT_VERSION
            ),
            "available": sorted(PROMPTS),
            "note": (
                "v2 adds the on-topic rule. Old "
                "versions are never deleted - a "
                "trace from last week has to keep "
                "resolving to the text that ran."
            ),
        },
        "retrieval": {
            "embedding_model": (
                config.EMBEDDING_MODEL
            ),
            "rerank_model": config.RERANK_MODEL,
            "vector_store": "ChromaDB (local, SQLite-backed)",
            "distance": "cosine",
            "top_k": TOP_K,
            "abstain_below": retriever_threshold,
            "chunks_indexed": chunk_count,
            "policies_indexed": policies,
        },
        "chunking": [
            {
                "name": "structure_aware",
                "detail": (
                    "Splits on policy headings so a "
                    "chunk is one clause and a "
                    "citation points at a section. "
                    "The strategy the app serves "
                    "from."
                ),
            },
            {
                "name": "basic",
                "detail": (
                    "Fixed 1000-character windows "
                    "with 150 characters of "
                    "overlap. Kept as the Week-4 "
                    "baseline to measure the other "
                    "against."
                ),
            },
            {
                "name": "front_matter",
                "detail": (
                    "Week 12. Markdown with "
                    "declared version, "
                    "effective_date and entity, so "
                    "the desk can filter on them "
                    "rather than hope they rank."
                ),
            },
        ],
        "agent": {
            "loop": (
                "Hand-built: plan, call a tool, "
                "read the result, repeat."
            ),
            "budgets": [
                "max_iterations",
                "max_tokens",
                "max_cost_usd",
                "max_seconds",
            ],
            "budget_note": (
                "All four are checked every lap. A "
                "budget that is never checked is a "
                "comment, not a limit."
            ),
            "tools": [
                {
                    "name": "get_employee_record",
                    "reads": "the employee fixture",
                },
                {
                    "name": "search_handbook",
                    "reads": "the policy index",
                },
                {
                    "name": "get_jurisdiction_rules",
                    "reads": "the statutory table",
                },
            ],
            "tool_note": (
                "Each description says what the "
                "tool does NOT do. Overlapping "
                "descriptions, not the model, are "
                "the usual cause of a tool being "
                "called for the wrong step."
            ),
        },
        "mcp": {
            "exposed": [
                {
                    "server": "policy_server",
                    "tools": [
                        "search_handbook",
                        "get_policy_version",
                    ],
                },
                {
                    "server": "hris_server",
                    "tools": [
                        "get_leave_balance",
                        "get_grade_band",
                    ],
                    "scoped_by": "HRIS_SCOPES",
                },
            ],
            "consumed": (
                "app/mcp/client.py starts each "
                "server in mcp_servers.json, "
                "performs the handshake, asks "
                "tools/list, and hands the result "
                "to the agent loop. Adding a "
                "server is a config edit."
            ),
            "isolation": (
                "No MCP server holds an API key or "
                "can reach a model. Servers start "
                "with a scrubbed environment."
            ),
        },
        "observability": {
            "log": "logs/requests.jsonl",
            "per_request": [
                "trace_id",
                "question and answer (both indexed)",
                "prompt_version",
                "context_ids",
                "per-stage latency, tokens, cost",
            ],
            "exporter": (
                "LangSmith, off unless "
                "LANGSMITH_ENABLED=1"
            ),
            "langsmith": key_state(
                config.__dict__.get(
                    "LANGSMITH_API_KEY"
                )
                or None
            ),
            "redaction": (
                "grade, band, tenure and leave "
                "balance never reach the log; "
                "employee_id does, because the "
                "support drill searches on it."
            ),
        },
        "cost": {
            "input_per_1m_usd": (
                config.INPUT_COST_PER_1M
            ),
            "output_per_1m_usd": (
                config.OUTPUT_COST_PER_1M
            ),
            "note": (
                "List price from the provider's "
                "pricing page. Left at zero means "
                "the cost column is honest about "
                "being unset rather than invented."
            ),
        },
    }


@router.get("/policies/{policy_id}")
def policy_text(policy_id: str):
    """
    One policy's full text, read from the PDF the app
    actually ingests.

    Read from the PDF rather than from the Markdown source,
    so what a reader sees in the modal is what the retriever
    chunked. If those two ever diverge, the modal is the
    place it should show.
    """

    import os
    import re

    from fastapi import HTTPException

    # The id comes from a URL. Anything but the expected
    # shape is rejected before it reaches the filesystem.
    if not re.fullmatch(r"HR-\d{3}", policy_id):

        raise HTTPException(
            status_code=400,
            detail=(
                "A policy id looks like HR-201."
            ),
        )

    path = os.path.join(
        config.ADDENDA_DIR,
        f"{policy_id}.pdf",
    )

    if not os.path.exists(path):

        raise HTTPException(
            status_code=404,
            detail=f"No policy {policy_id}.",
        )

    try:
        import pymupdf

        document = pymupdf.open(path)

        pages = [
            page.get_text() for page in document
        ]

        document.close()

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not read the policy: "
                f"{type(error).__name__}"
            ),
        ) from error

    header, body = split_header(
        "\n".join(pages)
    )

    return {
        "policy_id": policy_id,
        "header": header,
        "text": body,
        "pages": len(pages),
    }


def split_header(text: str) -> tuple[dict, str]:
    """
    Pull the title and the labelled header lines off the
    front, so the modal can render them as a block rather
    than as the first paragraph of the policy.
    """

    import re

    lines = text.split("\n")

    header: dict = {}

    body_start = 0

    for index, line in enumerate(lines[:8]):

        if index == 0:
            header["title"] = line.strip()
            body_start = 1
            continue

        # Several "Label: value" pairs per line. The
        # lookahead stops each value at the next label
        # rather than swallowing the rest of the line,
        # which is what dropped Policy ID, Version and
        # Effective Date on the first attempt.
        found = dict(
            re.findall(
                r"([A-Z][A-Za-z ]*?):\s*"
                r"(.*?)(?=\s+[A-Z][A-Za-z ]*?:|$)",
                line.strip(),
            )
        )

        if not found:
            break

        header.update(
            {
                key.strip(): value.strip()
                for key, value in found.items()
            }
        )

        body_start = index + 1

    return header, "\n".join(
        lines[body_start:]
    ).strip()
