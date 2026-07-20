"""LangGraph agent nodes for the Agentic RAG workflow."""
import json
import re
import threading
from typing import Optional

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.search.webfetch import fetch_url
from app.vectorstore.chroma_store import ChromaStore

from .state import AgentState

_trace_buffers: dict[int, list[dict]] = {}
_trace_buffers_lock = threading.Lock()


def set_trace_buffer(buf: list[dict]) -> None:
    with _trace_buffers_lock:
        _trace_buffers[threading.get_ident()] = buf


def clear_trace_buffer() -> None:
    with _trace_buffers_lock:
        _trace_buffers.pop(threading.get_ident(), None)


def _add_trace(state: AgentState, step: str, detail: dict) -> None:
    entry = {"step": step, **detail}
    state["trace"].append(entry)
    with _trace_buffers_lock:
        buf = _trace_buffers.get(threading.get_ident())
    if buf is not None:
        buf.append(entry)


def _llm_json_invoke(llm: ChatOpenAI, prompt: str, fallback: dict) -> dict:
    try:
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        # Extract JSON if wrapped in markdown fences.
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        return json.loads(text.strip())
    except Exception:
        return fallback


def retrieve_node_factory(vector_store: ChromaStore, k: int = 4):
    def retrieve(state: AgentState) -> AgentState:
        question = state["question"]
        docs = vector_store.similarity_search(question, k=k)
        state["documents"] = [doc.page_content for doc in docs]
        _add_trace(
            state,
            "retrieve",
            {"question": question, "count": len(docs), "sources": [getattr(d, "metadata", {}).get("source", "") for d in docs]},
        )
        return state

    return retrieve


def grade_documents_node_factory(llm: ChatOpenAI):
    def grade_documents(state: AgentState) -> AgentState:
        question = state["question"]
        relevant_docs = []
        grades = []
        for i, doc in enumerate(state["documents"]):
            prompt = (
                "You are a relevance grader. Given a user question and a document chunk, "
                "respond with JSON: {\"relevant\": true/false, \"reason\": \"...\"}\n\n"
                f"Question: {question}\n\n"
                f"Document chunk:\n{doc}\n\n"
                "JSON:"
            )
            result = _llm_json_invoke(llm, prompt, {"relevant": True})
            is_relevant = bool(result.get("relevant"))
            grades.append({"index": i, "relevant": is_relevant, "reason": result.get("reason", "")})
            if is_relevant:
                relevant_docs.append(doc)
        state["documents"] = relevant_docs
        _add_trace(state, "grade_documents", {"grades": grades, "relevant_count": len(relevant_docs)})
        return state

    return grade_documents


def route_after_grading(state: AgentState) -> str:
    if state["documents"]:
        return "generate"
    if state["web_search_enabled"]:
        return "propose_urls"
    return "generate"


def propose_urls_node_factory(llm: ChatOpenAI):
    def propose_urls(state: AgentState) -> AgentState:
        question = state["question"]
        prompt = (
            "You are a research assistant. The user asked a question and no relevant "
            "documents were found. Propose up to 3 authoritative URLs that likely contain "
            "the answer. Respond with JSON: {\"urls\": [\"...\"]}\n\n"
            f"Question: {question}\n\n"
            "JSON:"
        )
        result = _llm_json_invoke(llm, prompt, {"urls": []})
        urls = [u for u in result.get("urls", []) if isinstance(u, str)]
        urls = urls[:3]
        state["web_search_urls"] = urls
        _add_trace(state, "propose_urls", {"proposed_urls": urls})
        return state

    return propose_urls


def fetch_urls_node(state: AgentState) -> AgentState:
    fetched: list[str] = []
    urls = state.get("web_search_urls", [])
    for url in urls:
        text = fetch_url(url)
        if text:
            fetched.append(text)
    if fetched:
        state["documents"].extend(fetched)
    _add_trace(
        state,
        "fetch_urls",
        {"urls": urls, "successful_fetches": len(fetched)},
    )
    return state


def generate_node_factory(llm: ChatOpenAI):
    def generate(state: AgentState) -> AgentState:
        question = state["question"]
        docs = state["documents"]
        context = "\n\n---\n\n".join(docs) if docs else "No relevant context found."
        llm_messages = [
            SystemMessage(content=(
                "You are a helpful assistant. Use only the provided context to answer the "
                "user's question. If the context does not contain enough information, say so. "
                "Cite sources using [doc N] or [web N] when possible.\n\n"
                "Use markdown formatting only. Do not use HTML tags. For line breaks, "
                "end the line with two spaces or use a blank line between paragraphs.\n\n"
                f"Context:\n{context}"
            )),
            *state["messages"],
            HumanMessage(content=question),
        ]
        response = llm.invoke(llm_messages)
        generation = response.content if hasattr(response, "content") else str(response)
        generation = re.sub(r"<br\s*/?>", "\n\n", generation, flags=re.IGNORECASE)
        state["generation"] = generation
        _add_trace(state, "generate", {"has_context": bool(docs), "length": len(generation)})
        return state

    return generate


def quality_check_node_factory(llm: ChatOpenAI):
    def quality_check(state: AgentState) -> AgentState:
        question = state["question"]
        generation = state.get("generation", "")
        docs = state["documents"]
        context = "\n\n---\n\n".join(docs) if docs else ""
        prompt = (
            "You are a quality checker. Given a question, an answer, and supporting context, "
            "respond with JSON: {\"grounded\": true/false, \"answers_question\": true/false, \"feedback\": \"...\"}\n\n"
            f"Question: {question}\n\n"
            f"Answer: {generation}\n\n"
            f"Context:\n{context}\n\n"
            "JSON:"
        )
        result = _llm_json_invoke(llm, prompt, {"grounded": True, "answers_question": True})
        _add_trace(
            state,
            "quality_check",
            {
                "grounded": bool(result.get("grounded")),
                "answers_question": bool(result.get("answers_question")),
                "feedback": result.get("feedback", ""),
            },
        )
        return state

    return quality_check


def route_after_quality(state: AgentState) -> str:
    if state["steps"] >= state.get("max_loops", 3):
        return "end"
    # We run quality check once and then end to keep graph simple.
    return "end"
