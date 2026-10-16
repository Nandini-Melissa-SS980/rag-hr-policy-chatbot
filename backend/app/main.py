from fastapi import FastAPI

from app.api.chat import router


app = FastAPI(
    title="HR Policy RAG Chatbot",
    description=(
        "A Retrieval-Augmented Generation "
        "application for HR policy documents."
    ),
    version="1.0.0",
)


app.include_router(router)


@app.get("/")
def root():

    return {
        "message": "HR Policy RAG Chatbot",
        "docs": "/docs",
    }