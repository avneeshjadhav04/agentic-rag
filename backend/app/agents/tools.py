"""Tools for the researcher sub-agent.

Provides ``build_research_tools()`` which returns ``@tool``-decorated
functions with Pydantic arg schemas for use with ``llm.bind_tools()``.
The underlying execution functions (_vector_search, _web_fetch) are
called directly by the research_tools graph node — the @tool wrappers
exist only to generate the OpenAI function schema for the LLM.
"""
import uuid

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.search.webfetch import fetch_url
from app.vectorstore.chroma_store import ChromaStore, PARENT_CHAR_CAP, WINDOW_RADIUS


# ---------------------------------------------------------------------------
# Pydantic schemas — for bind_tools and with_structured_output
# ---------------------------------------------------------------------------

class VectorSearchInput(BaseModel):
    query: str = Field(description="The search query")


class WebFetchInput(BaseModel):
    url: str = Field(description="Full URL including https://")


class HandoffInput(BaseModel):
    pass


class GradeResult(BaseModel):
    relevant: bool
    score: int
    reason: str


# ---------------------------------------------------------------------------
# Underlying execution functions (called by research_tools node)
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


def _vector_search(vector_store: ChromaStore, k: int, query: str) -> tuple[str, list[dict]]:
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
    return _format_docs_for_llm(expanded), expanded


def _web_fetch(url: str, query: str, llm: ChatOpenAI) -> tuple[str, list[dict]]:
    text = fetch_url(url)
    if not text:
        return f"Failed to fetch content from {url}.", []

    doc = {"content": text, "metadata": {"source": url, "source_id": str(uuid.uuid4())}}
    relevant, score, reason = _grade_doc(llm, query, text)
    if not relevant:
        return f"Fetched {url} but the content was not relevant to the question (score: {score}/10).", []

    return _format_docs_for_llm([doc]), [doc]


def _grade_doc(llm: ChatOpenAI, question: str, content: str) -> tuple[bool, int, str]:
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
# build_research_tools — returns @tool-decorated functions for bind_tools.
# The @tool functions are schema-only; research_tools calls _vector_search /
# _web_fetch directly with runtime context (vector_store, k, question, llm).
# ---------------------------------------------------------------------------

def build_research_tools(
    vector_store: ChromaStore,
    k: int,
    llm: ChatOpenAI,
    allow_web_fetch: bool,
) -> list:
    @tool(args_schema=VectorSearchInput)
    def vector_search(query: str) -> str:
        """Search the local document knowledge base for relevant information.
        Use this to find information from uploaded documents. You can call it
        multiple times with different queries to explore different aspects of the question.
        """
        result_text, _ = _vector_search(vector_store, k, query)
        return result_text

    @tool(args_schema=HandoffInput)
    def handoff() -> str:
        """Signal that you have gathered enough information. Call this when
        you have sufficient context to answer the question, or when further
        searching is unlikely to yield better results.
        """
        return "Handoff complete."

    tools = [vector_search, handoff]

    if allow_web_fetch:
        @tool(args_schema=WebFetchInput)
        def web_fetch(url: str) -> str:
            """Fetch content from a specific URL. Use this only when the local
            knowledge base doesn't contain enough information and you know a
            specific URL that likely has the answer. The URL must be real.
            """
            return f"Fetch {url}"

        tools.append(web_fetch)

    return tools