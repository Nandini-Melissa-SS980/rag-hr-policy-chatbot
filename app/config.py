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