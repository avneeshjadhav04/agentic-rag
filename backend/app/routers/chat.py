"""Chat endpoints for the Agentic RAG backend."""
from typing import AsyncGenerator

from fastapi import APIRouter, Form, Request
from fastapi.responses import StreamingResponse

from app.agents.graph import build_agentic_rag_graph
from app.agents.state import AgentState
from app.models.factory import get_chat_llm, get_embeddings
from app.vectorstore.chroma_store import ChromaStore

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _build_graph(
    chat_base_url: str,
    chat_model: str,
    chat_api_key: str,
    embed_base_url: str,
    embed_model: str,
    embed_api_key: str,
    temperature: float = 0.7,
):
    llm = get_chat_llm(chat_base_url, chat_model, chat_api_key, temperature=temperature)
    embeddings = get_embeddings(embed_base_url, embed_model, embed_api_key)
    vector_store = ChromaStore(embeddings=embeddings)
    return build_agentic_rag_graph(llm, embeddings, vector_store)


@router.post("")
def chat(
    request: Request,
    question: str = Form(...),
    chat_provider: str = Form(default="nvidia-nim"),
    chat_base_url: str = Form(...),
    chat_model: str = Form(...),
    chat_api_key: str = Form(default=""),
    embed_provider: str = Form(default="nvidia-nim"),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
    web_search_enabled: bool = Form(default=False),
    temperature: float = Form(default=0.7),
):
    graph = _build_graph(
        chat_base_url, chat_model, chat_api_key,
        embed_base_url, embed_model, embed_api_key,
        temperature=temperature,
    )
    state: AgentState = {
        "question": question,
        "messages": [],
        "documents": [],
        "web_search_urls": [],
        "generation": None,
        "trace": [],
        "steps": 0,
        "web_search_enabled": web_search_enabled,
        "max_loops": 3,
    }
    final_state = graph.invoke(state)
    return {
        "answer": final_state.get("generation", ""),
        "trace": final_state.get("trace", []),
    }


@router.post("/stream")
async def chat_stream(
    request: Request,
    question: str = Form(...),
    chat_provider: str = Form(default="nvidia-nim"),
    chat_base_url: str = Form(...),
    chat_model: str = Form(...),
    chat_api_key: str = Form(default=""),
    embed_provider: str = Form(default="nvidia-nim"),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
    web_search_enabled: bool = Form(default=False),
    temperature: float = Form(default=0.7),
):
    async def event_generator() -> AsyncGenerator[str, None]:
        graph = _build_graph(
            chat_base_url, chat_model, chat_api_key,
            embed_base_url, embed_model, embed_api_key,
            temperature=temperature,
        )
        state: AgentState = {
            "question": question,
            "messages": [],
            "documents": [],
            "web_search_urls": [],
            "generation": None,
            "trace": [],
            "steps": 0,
            "web_search_enabled": web_search_enabled,
            "max_loops": 3,
        }
        final_state = graph.invoke(state)
        answer = final_state.get("generation", "")
        trace = final_state.get("trace", [])

        # Stream the final answer word-by-word to mimic real-time generation.
        words = answer.split(" ")
        for i, word in enumerate(words):
            payload = word if i == 0 else " " + word
            yield f"data: {payload}\n\n"
        # Final event carries the trace.
        import json
        yield f"event: done\ndata: {json.dumps({'trace': trace})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
