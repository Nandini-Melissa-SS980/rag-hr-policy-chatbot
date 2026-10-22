import os

from dotenv import load_dotenv

load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5-mini",
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "BAAI/bge-small-en-v1.5",
)

RERANK_MODEL = os.getenv(
    "RERANK_MODEL",
    "BAAI/bge-reranker-base",
)


# Token prices for the Week 7 agent-vs-workflow
# race, in USD per million tokens. Left at zero on
# purpose: set them from the provider's pricing page
# so the cost column is real rather than invented.
INPUT_COST_PER_1M = float(
    os.getenv(
        "INPUT_COST_PER_1M",
        "0.0",
    )
)

OUTPUT_COST_PER_1M = float(
    os.getenv(
        "OUTPUT_COST_PER_1M",
        "0.0",
    )
)

CHROMA_PATH = os.getenv(
    "CHROMA_PATH",
    "./vectorstore",
)

COLLECTION_NAME = os.getenv(
    "COLLECTION_NAME",
    "hr_policy_chunks",
)

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DOCUMENTS_DIR = os.path.join(
    BASE_DIR,
    "documents",
)

ADDENDA_DIR = os.path.join(
    DOCUMENTS_DIR,
    "addenda",
)

# Week 12. The versioned corpus: the same policy in more than
# one edition, the entity annexes that override the handbook,
# and the grade-band matrix. Markdown with front matter rather
# than PDF, because version, effective_date and entity have to
# be declared fields the retriever can filter on - a date
# mentioned inside a paragraph is a string that might rank
# well, not a constraint.
VERSIONED_DIR = os.path.join(
    DOCUMENTS_DIR,
    "versioned",
)

ANNEXES_DIR = os.path.join(
    DOCUMENTS_DIR,
    "annexes",
)

MATRICES_DIR = os.path.join(
    DOCUMENTS_DIR,
    "matrices",
)

# The collection the Week-12 desk reads. Kept separate from
# the Week-4 collections so the retrieval numbers in
# results.md stay reproducible against the index they were
# measured on.
DESK_COLLECTION = os.getenv(
    "DESK_COLLECTION",
    "hr_policy_desk",
)


# ---------------------------------------------------
# Provider selection.
#
# The generator and the judge go through
# app/services/llm.py and honour this. The Week-7 agent
# loop does not: it does tool calling, the two providers
# disagree on the shape of a tool call, and the Week-8
# and Week-10 numbers were measured against OpenAI's.
# ---------------------------------------------------
LLM_PROVIDER = os.getenv(
    "LLM_PROVIDER",
    "openai",
).strip().lower()

# Free tier, no card: https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.0-flash",
)

# Gemini's OpenAI-compatible endpoint, so the same SDK
# serves both providers and there is no second
# dependency to install.
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)
