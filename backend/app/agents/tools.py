"""Tools for the researcher sub-agent.

Each tool returns a text summary for the LLM and a list of graded doc dicts
to store in ``state["documents"]``. Grading happens inside the tools so that
``state["documents"]`` only contains relevant context — preserving
ContextualPrecision/Recall eval metric quality.
"""
from collections import Counter
from typing import Optional

from langchain_openai import ChatOpenAI

from app.search.webfetch import fetch_url
from app.vectorstore.chroma_store import ChromaStore, PARENT_CHAR_CAP, WINDOW_RADIUS


def _build_window(children: list, target_start: int, radius: int = 2) -> str:
    """Join a window of neighboring child chunks around ``target_start``."""
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


def vector_search(
    vector_store: ChromaStore,
    k: int,
    query: str,
) -> tuple[str, list[dict]]:
    """Search the local vector store and return graded, relevant docs.

    Performs child-chunk similarity search, expands to parent documents when
    available (parent-document retrieval), and grades results for relevance.
    Returns ``(result_text, docs)`` where ``docs`` are the relevant doc dicts
    to append to ``state["documents"]``.
    """
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

    result_text = _format_docs_for_llm(expanded)
    return result_text, expanded


def web_fetch(
    url: str,
    query: str,
    llm: ChatOpenAI,
) -> tuple[str, list[dict]]:
    """Fetch a URL and return graded, relevant content.

    Uses ``fetch_url`` to retrieve plain text from the page, then grades it
    against the user's question. Returns ``(result_text, docs)`` where ``docs``
    are relevant doc dicts to append to ``state["documents"]``.
    """
    import uuid

    text = fetch_url(url)
    if not text:
        return f"Failed to fetch content from {url}.", []

    doc = {"content": text, "metadata": {"source": url, "source_id": str(uuid.uuid4())}}
    relevant, score, reason = _grade_doc(llm, query, text)
    if not relevant:
        return f"Fetched {url} but the content was not relevant to the question (score: {score}/10).", []

    return _format_docs_for_llm([doc]), [doc]


def _grade_doc(llm: ChatOpenAI, question: str, content: str) -> tuple[bool, int, str]:
    """Grade a single document for relevance. Returns (relevant, score, reason)."""
    import json
    import re

    prompt = (
        "You are a relevance grader. Given a user question and a document, "
        "Respond with ONLY a JSON object — no text before or after: "
        '{"relevant": true/false, "score": <0-10>, "reason": "..."}\n\n'
        f"Question: {question}\n\n"
        f"Document:\n{content}\n\n"
        "JSON:"
    )
    try:
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            obj_match = re.search(r"\{.*\}", text, re.DOTALL)
            if obj_match:
                text = obj_match.group(0)
        result = json.loads(text.strip())
        return bool(result.get("relevant")), int(result.get("score", 5)), result.get("reason", "")
    except Exception:
        return True, 5, ""


def _format_docs_for_llm(docs: list[dict]) -> str:
    """Format graded docs into a text summary for the LLM."""
    parts = []
    for i, doc in enumerate(docs):
        source = doc.get("metadata", {}).get("source", f"doc {i + 1}")
        parts.append(f"Source: {source}\n{doc['content']}")
    return "\n\n---\n\n".join(parts)


# Tool description strings for the researcher's system prompt.
VECTOR_SEARCH_DESC = (
    'vector_search: Search the local document knowledge base for relevant information.\n'
    '  Args: {"query": "<search query>"}\n'
    "  Use this to find information from uploaded documents. You can call it "
    "multiple times with different queries to explore different aspects of the question."
)

WEB_FETCH_DESC = (
    'web_fetch: Fetch content from a specific URL.\n'
    '  Args: {"url": "<full URL including https://>"}\n'
    "  Use this only when the local knowledge base doesn't contain enough "
    "information and you know a specific URL that likely has the answer. "
    "The URL must be a real, specific URL — do not make up URLs."
)

HANDOFF_DESC = (
    'handoff: Signal that you have gathered enough information.\n'
    '  Args: {}\n'
    "  Use this when you have sufficient context to answer the question, "
    "or when further searching is unlikely to yield better results."
)