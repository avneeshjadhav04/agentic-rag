"""Tools for the research sub-agent in the subagents-pattern architecture.

The research subagent is a ``create_agent`` instance with ``vector_search``
and (optionally) ``web_fetch`` as its tools.  These are **real ``@tool``
functions** — they execute directly inside the subagent's ReAct loop, grade
results via ``_grade_doc``, and return the formatted result text.

Documents are NOT updated via ``Command`` here — that would go to the
subagent's state and get lost.  Instead, the ``call_research`` wrapper in
``nodes.py`` extracts documents from the subagent's final state and merges
them into the outer ``WorkflowState``.

Trace events are pushed to the live SSE buffer via ``add_trace`` from
``.trace``.
"""
import uuid
from collections import Counter
from typing import Annotated

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.search.webfetch import fetch_url
from app.vectorstore.chroma_store import ChromaStore, PARENT_CHAR_CAP, WINDOW_RADIUS

from .state import WorkflowState
from .trace import add_trace


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class GradeResult(BaseModel):
    relevant: bool
    score: int
    reason: str


# ---------------------------------------------------------------------------
# Underlying execution helpers
# ---------------------------------------------------------------------------

def _build_window(children: list, target_start: int, radius: int = 2) -> str:
    if not children:
        return ""
    target_idx = 0
    for i, d in enumerate(children):
        if d.metadata.get("start_index", 0) == target_start:
            target_idx = i
            break
    lo = max(0, target_idx - radius)
    hi = min(len(children), target_idx + radius + 1)
    return "\n".join(d.page_content for d in children[lo:hi])


def _vector_search(
    vector_store: ChromaStore,
    k: int,
    query: str,
    llm: ChatOpenAI,
    question: str,
) -> tuple[str, list[dict]]:
    """Search Chroma, expand to parent docs, grade for relevance. Returns (formatted_text, graded_docs)."""
    child_docs = vector_store.similarity_search(query, k=k)
    parents = vector_store.get_parents(
        list({d.metadata.get("source_id") for d in child_docs if d.metadata.get("source_id")})
    )

    expanded: list[dict] = []
    seen_parent_ids: set[str] = set()
    for doc in child_docs:
        sid = doc.metadata.get("source_id")
        parent = parents.get(sid) if sid else None
        if parent and len(parent.page_content) <= PARENT_CHAR_CAP:
            if sid in seen_parent_ids:
                continue
            expanded.append({"content": parent.page_content, "metadata": parent.metadata})
            seen_parent_ids.add(sid)
        else:
            if parent is None:
                expanded.append({"content": doc.page_content, "metadata": doc.metadata})
            else:
                children = vector_store.get_children_by_source(sid)
                window = _build_window(children, doc.metadata.get("start_index", 0), WINDOW_RADIUS)
                expanded.append({"content": window or doc.page_content, "metadata": doc.metadata})

    if not expanded:
        return "No documents found in the local knowledge base for this query.", []

    graded: list[dict] = []
    for doc in expanded:
        relevant, score, reason = _grade_doc(llm, question, doc["content"])
        if relevant:
            graded.append(doc)

    if not graded:
        return "Found documents in the local knowledge base but none were relevant to the question.", []

    return _format_docs_for_llm(graded), graded


def _web_fetch(url: str, query: str, llm: ChatOpenAI) -> tuple[str, list[dict]]:
    """Fetch URL content, grade for relevance. Returns (formatted_text, graded_docs)."""
    text = fetch_url(url)
    if not text:
        return f"Failed to fetch content from {url}.", []

    doc = {"content": text, "metadata": {"source": url, "source_id": str(uuid.uuid4())}}
    relevant, score, reason = _grade_doc(llm, query, text)
    if not relevant:
        return f"Fetched {url} but the content was not relevant to the question (score: {score}/10).", []

    return _format_docs_for_llm([doc]), [doc]


def _grade_doc(llm: ChatOpenAI, question: str, content: str) -> tuple[bool, int, str]:
    """Grade a single document for relevance to the question via structured output."""
    structured_llm = llm.with_structured_output(GradeResult, method="function_calling")
    prompt = (
        "You are a relevance grader. Given a user question and a document, "
        "grade whether the document is relevant to the question.\n\n"
        f"Question: {question}\n\n"
        f"Document:\n{content}"
    )
    try:
        result = structured_llm.invoke(prompt)
        return result.relevant, result.score, result.reason
    except Exception:
        return True, 5, ""


def _format_docs_for_llm(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs):
        source = doc.get("metadata", {}).get("source", f"doc {i + 1}")
        parts.append(f"Source: {source}\n{doc['content']}")
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# @tool functions — execute directly inside the research subagent's ReAct loop.
# Each returns plain text (the formatted result) and pushes a trace event to
# the live SSE buffer.  Documents are NOT updated via Command here — the
# call_research wrapper in nodes.py handles that.
# ---------------------------------------------------------------------------

def build_research_tools(
    vector_store: ChromaStore,
    k: int,
    llm: ChatOpenAI,
    allow_web_fetch: bool,
) -> list:
    """Build the tool list for the research subagent.

    Returns real @tool-decorated functions that execute the search/fetch
    logic directly and return the formatted result text.
    """

    @tool
    def vector_search(
        query: str,
        runtime: ToolRuntime[None, WorkflowState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> str:
        """Search the local document knowledge base for relevant information.
        Use this to find information from uploaded documents. You can call it
        multiple times with different queries to explore different aspects of the question.
        """
        stop_event = runtime.state.get("stop_event")
        if stop_event and stop_event.is_set():
            return "[Stopped]"

        result_text, docs = _vector_search(vector_store, k, query, llm, query)

        source_counts = Counter(
            (doc.get("metadata", {}).get("source_id", "unknown"),
             doc.get("metadata", {}).get("source", "unknown"))
            for doc in docs
        )
        sources_summary = [
            {"source_id": sid, "source_name": name, "chunks": count}
            for (sid, name), count in source_counts.items()
        ]

        add_trace(runtime.state, "tool_result", {
            "tool": "vector_search",
            "query": query,
            "new_docs": len(docs),
            "total_docs": len(docs),
            "sources": sources_summary,
        })

        return result_text

    tools = [vector_search]

    if allow_web_fetch:
        @tool
        def web_fetch(
            url: str,
            runtime: ToolRuntime[None, WorkflowState],
            tool_call_id: Annotated[str, InjectedToolCallId],
        ) -> str:
            """Fetch content from a specific URL. Use this only when the local
            knowledge base doesn't contain enough information and you know a
            specific URL that likely has the answer. The URL must be real.
            """
            stop_event = runtime.state.get("stop_event")
            if stop_event and stop_event.is_set():
                return "[Stopped]"

            result_text, docs = _web_fetch(url, url, llm)

            add_trace(runtime.state, "tool_result", {
                "tool": "web_fetch",
                "url": url,
                "new_docs": len(docs),
                "total_docs": len(docs),
            })

            return result_text

        tools.append(web_fetch)

    return tools