"""State for the multi-agent RAG workflow (subagents pattern).

The main agent (supervisor) is a ``create_agent`` instance with tools
— ``research``, ``draft_answer`` — backed by research and writer
subagents.  A deterministic ``quality_check`` node runs after the main
agent produces its final answer.

``WorkflowState`` extends LangChain's ``AgentState`` (which provides
``messages`` with the ``add_messages`` reducer and ``structured_response``)
with the custom fields the RAG pipeline needs.
"""
import hashlib
import json
import threading
from typing import Annotated, Optional

from langchain.agents import AgentState


def _dedup_docs(left: list[dict], right: list[dict]) -> list[dict]:
    """Reducer for documents: concatenate and deduplicate by content hash."""
    seen: set[str] = set()
    result: list[dict] = []
    for doc in left + right:
        content = doc.get("content", "")
        h = hashlib.md5(content.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            result.append(doc)
    return result


class WorkflowState(AgentState):
    """Shared state for the subagents-pattern RAG workflow.

    Inherited from ``AgentState``:
        messages: Annotated[list, add_messages]  — conversation history
        structured_response: Optional[Any]       — result of response_format

    Custom fields:
        question:         the original user question (for grading)
        documents:        graded, deduped docs gathered by the research subagent
        trace:            SSE trace events for live UI streaming
        generation:       the main agent's final answer (set by prepare_generation)
        quality_passed:   quality_check verdict
        steps:            quality_check attempt counter
        quality_feedback: latest quality check feedback (for retries)
        max_loops:        max quality check retries (default 3)
        web_search_enabled: whether web_fetch is available to the researcher
        stop_event:       threading.Event set when the client disconnects
    """
    question: str
    documents: Annotated[list[dict], _dedup_docs]
    trace: list[dict]
    generation: Optional[str]
    quality_passed: bool
    steps: int
    quality_feedback: Optional[str]
    max_loops: int
    web_search_enabled: bool
    stop_event: Optional[threading.Event]