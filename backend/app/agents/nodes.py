"""LangGraph agent nodes for the Agentic RAG workflow."""
import json
import re
import threading
import uuid
from collections import Counter, defaultdict
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
        question = state.get("refined_question") or state["question"]
        docs = vector_store.similarity_search(question, k=k)
        state["documents"] = [
            {"content": doc.page_content, "metadata": doc.metadata}
            for doc in docs
        ]
        source_counts = Counter(
            (doc.metadata.get("source_id", "unknown"), doc.metadata.get("source", "unknown"))
            for doc in docs
        )
        sources_summary = [
            {"source_id": sid, "name": name, "chunks": count}
            for (sid, name), count in source_counts.items()
        ]
        _add_trace(
            state,
            "retrieve",
            {"question": question, "count": len(docs), "sources": sources_summary},
        )
        return state

    return retrieve


def grade_documents_node_factory(llm: ChatOpenAI):
    def grade_documents(state: AgentState) -> AgentState:
        question = state["question"]
        doc_sources = [
            (doc.get("metadata", {}).get("source_id", "unknown"), doc.get("metadata", {}).get("source", "unknown"))
            for doc in state["documents"]
        ]
        graded: list[tuple[dict, int]] = []
        grades = []
        for i, doc in enumerate(state["documents"]):
            content = doc["content"]
            prompt = (
                "You are a relevance grader. Given a user question and a document chunk, "
                "respond with JSON: "
                "{\"relevant\": true/false, \"score\": <0-10>, \"reason\": \"...\"}\n\n"
                f"Question: {question}\n\n"
                f"Document chunk:\n{content}\n\n"
                "JSON:"
            )
            result = _llm_json_invoke(llm, prompt, {"relevant": True, "score": 5})
            is_relevant = bool(result.get("relevant"))
            score = int(result.get("score", 5))
            grades.append({"index": i, "relevant": is_relevant, "score": score, "reason": result.get("reason", "")})
            if is_relevant:
                graded.append((doc, score))
        graded.sort(key=lambda x: x[1], reverse=True)
        state["documents"] = [d for d, _ in graded]
        grouped: dict[str, list[dict]] = defaultdict(list)
        for g in grades:
            sid, name = doc_sources[g["index"]]
            grouped[sid].append({**g, "source_id": sid, "source": name})
        grades_by_source = [
            {"source_id": sid, "source": chunks[0]["source"], "chunks": chunks}
            for sid, chunks in grouped.items()
        ]
        _add_trace(state, "grade_documents", {"grades_by_source": grades_by_source, "relevant_count": len(graded)})
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
    fetched: list[dict] = []
    urls = state.get("web_search_urls", [])
    for url in urls:
        text = fetch_url(url)
        if text:
            fetched.append({"content": text, "metadata": {"source": url, "source_id": str(uuid.uuid4())}})
    if fetched:
        state["documents"].extend(fetched)
    state["web_fetched_count"] = len(fetched)
    _add_trace(
        state,
        "fetch_urls",
        {"urls": urls, "successful_fetches": len(fetched)},
    )
    return state


def grade_urls_node_factory(llm: ChatOpenAI):
    def grade_urls(state: AgentState) -> AgentState:
        question = state["question"]
        docs = state["documents"]
        web_count = state.get("web_fetched_count", 0)
        if web_count == 0:
            _add_trace(state, "grade_urls", {"grades_by_source": [], "relevant_count": 0})
            return state
        web_docs = docs[-web_count:]
        doc_sources = [
            (doc.get("metadata", {}).get("source_id", "unknown"), doc.get("metadata", {}).get("source", "unknown"))
            for doc in web_docs
        ]
        graded: list[tuple[dict, int]] = []
        grades = []
        for i, doc in enumerate(web_docs):
            content = doc["content"]
            prompt = (
                "You are a relevance grader. Given a user question and a document chunk, "
                "respond with JSON: "
                "{\"relevant\": true/false, \"score\": <0-10>, \"reason\": \"...\"}\n\n"
                f"Question: {question}\n\n"
                f"Document chunk:\n{content}\n\n"
                "JSON:"
            )
            result = _llm_json_invoke(llm, prompt, {"relevant": True, "score": 5})
            is_relevant = bool(result.get("relevant"))
            score = int(result.get("score", 5))
            grades.append({"index": i, "relevant": is_relevant, "score": score, "reason": result.get("reason", "")})
            if is_relevant:
                graded.append((doc, score))
        graded.sort(key=lambda x: x[1], reverse=True)
        relevant_docs = [d for d, _ in graded]
        state["documents"] = docs[:-web_count] + relevant_docs
        grouped: dict[str, list[dict]] = defaultdict(list)
        for g in grades:
            sid, name = doc_sources[g["index"]]
            grouped[sid].append({**g, "source_id": sid, "source": name})
        grades_by_source = [
            {"source_id": sid, "source": chunks[0]["source"], "chunks": chunks}
            for sid, chunks in grouped.items()
        ]
        _add_trace(state, "grade_urls", {"grades_by_source": grades_by_source, "relevant_count": len(graded)})
        return state

    return grade_urls


def generate_node_factory(llm: ChatOpenAI):
    def generate(state: AgentState) -> AgentState:
        question = state["question"]
        docs = state["documents"]
        if docs:
            context_parts = []
            for i, doc in enumerate(docs):
                source = doc.get("metadata", {}).get("source", f"doc {i+1}")
                context_parts.append(f"Source: {source}\n{doc['content']}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant context found."
        llm_messages = [
            SystemMessage(content=(
                "You are a helpful assistant. Use only the provided context to answer the "
                "user's question. If the context does not contain enough information, say so. "
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
        source_counts = Counter(
            (doc.get("metadata", {}).get("source_id", "unknown"), doc.get("metadata", {}).get("source", "unknown"))
            for doc in docs
        )
        sources_used = [
            {"source_id": sid, "name": name, "chunks": count}
            for (sid, name), count in source_counts.items()
        ]
        _add_trace(state, "generate", {"has_context": bool(docs), "length": len(generation), "sources_used": sources_used})
        return state

    return generate


def quality_check_node_factory(llm: ChatOpenAI):
    def quality_check(state: AgentState) -> AgentState:
        docs = state["documents"]
        if not docs:
            state["steps"] += 1
            state["quality_passed"] = True
            _add_trace(
                state,
                "quality_check",
                {
                    "grounded": True,
                    "answers_question": True,
                    "feedback": "No context available \u2014 answer correctly states it lacks information.",
                    "attempt": state["steps"],
                },
            )
            return state
        question = state["question"]
        generation = state.get("generation", "")
        docs = state["documents"]
        context = "\n\n---\n\n".join(d["content"] for d in docs) if docs else ""
        prompt = (
            "You are a quality checker. Given a question, an answer, and supporting context, "
            "respond with JSON: {\"grounded\": true/false, \"answers_question\": true/false, \"feedback\": \"...\"}\n\n"
            f"Question: {question}\n\n"
            f"Answer: {generation}\n\n"
            f"Context:\n{context}\n\n"
            "JSON:"
        )
        result = _llm_json_invoke(llm, prompt, {"grounded": True, "answers_question": True})
        grounded = bool(result.get("grounded"))
        answers_question = bool(result.get("answers_question"))
        feedback = result.get("feedback", "")
        state["steps"] += 1
        state["quality_passed"] = grounded and answers_question
        if not state["quality_passed"] and state["steps"] < state.get("max_loops", 3):
            state["refined_question"] = (
                f"The previous answer had issues: {feedback}\n\n"
                f"Original question: {question}\n\n"
                f"Please search again with this refined understanding."
            )
        _add_trace(
            state,
            "quality_check",
            {
                "grounded": grounded,
                "answers_question": answers_question,
                "feedback": feedback,
                "attempt": state["steps"],
            },
        )
        return state

    return quality_check


def route_after_quality(state: AgentState) -> str:
    if state["quality_passed"]:
        return "end"
    if state["steps"] >= state.get("max_loops", 3):
        return "end"
    return "retrieve"
