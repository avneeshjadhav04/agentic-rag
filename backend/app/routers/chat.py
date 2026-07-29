"""Chat endpoints for the Agentic RAG backend."""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Form, Request
from fastapi.responses import StreamingResponse

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import build_agentic_rag_graph
from app.agents.state import AgentState
from app.models.factory import get_generation_llm, get_embeddings
from app.sse import SSE_HEADERS
from app.vectorstore.chroma_store import ChromaStore

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _build_graph(
    generation_base_url: str,
    generation_model: str,
    generation_api_key: str,
    embed_base_url: str,
    embed_model: str,
    embed_api_key: str,
    temperature: float = 0.7,
    web_search_enabled: bool = False,
):
    llm = get_generation_llm(generation_base_url, generation_model, generation_api_key, temperature=temperature)
    embeddings = get_embeddings(embed_base_url, embed_model, embed_api_key)
    vector_store = ChromaStore(embeddings=embeddings)
    return build_agentic_rag_graph(llm, embeddings, vector_store, web_search_enabled=web_search_enabled)


@router.post("/stream")
async def chat_stream(
    request: Request,
    question: str = Form(...),
    messages: str = Form(default="[]"),
    generation_provider: str = Form(default="nvidia-nim"),
    generation_base_url: str = Form(...),
    generation_model: str = Form(...),
    generation_api_key: str = Form(default=""),
    embed_provider: str = Form(default="nvidia-nim"),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
    web_search_enabled: bool = Form(default=False),
    temperature: float = Form(default=0.7),
):
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            graph = _build_graph(
                generation_base_url, generation_model, generation_api_key,
                embed_base_url, embed_model, embed_api_key,
                temperature=temperature,
                web_search_enabled=web_search_enabled,
            )
            from app.agents.nodes import set_trace_buffer, clear_trace_buffer

            trace_buffer: list[dict] = []
            history_messages = json.loads(messages)
            base_messages = []
            for msg in history_messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    base_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    base_messages.append(AIMessage(content=content))
            state: AgentState = {
                "question": question,
                "messages": base_messages,
                "documents": [],
                "generation": None,
                "trace": [],
                "steps": 0,
                "web_search_enabled": web_search_enabled,
                "max_loops": 3,
                "quality_passed": False,
                "next_agent": None,
                "pending_tool": None,
                "pending_args": None,
                "tool_call_count": 0,
                "tool_call_id": None,
                "researcher_summary": None,
                "writer_summary": None,
                "quality_feedback": None,
            }

            def run_graph():
                set_trace_buffer(trace_buffer)
                try:
                    return graph.invoke(state, config={"recursion_limit": 25})
                finally:
                    clear_trace_buffer()

            task = asyncio.create_task(asyncio.to_thread(run_graph))

            while not task.done():
                while trace_buffer:
                    yield f"event: trace\ndata: {json.dumps(trace_buffer.pop(0))}\n\n"
                await asyncio.sleep(0.05)

            while trace_buffer:
                yield f"event: trace\ndata: {json.dumps(trace_buffer.pop(0))}\n\n"

            final_state = task.result()
            answer = final_state.get("generation", "")
            words = answer.split(" ")
            for i, word in enumerate(words):
                payload = word if i == 0 else " " + word
                yield f"data: {json.dumps(payload)}\n\n"
            yield f"event: done\ndata: {json.dumps({'trace': final_state.get('trace', [])})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=SSE_HEADERS)
