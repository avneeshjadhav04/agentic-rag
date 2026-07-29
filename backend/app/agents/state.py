"""State for the multi-agent RAG workflow (subagents pattern).

The main agent (supervisor) is a ``create_agent`` instance with three
tools — ``research``, ``draft_answer``, ``finalize_answer`` — backed by
research and writer subagents.  A deterministic ``quality_check`` node
runs after the main agent produces its final answer.

``WorkflowState`` extends LangChain's ``AgentState`` (which provides
``messages`` with the ``add_messages`` reducer and ``structured_response``)
with the custom fields the RAG pipeline needs.
"""
from typing import Annotated, Optional

from langchain.agents import AgentState


class WorkflowState(AgentState):
    """Shared state for the subagents-pattern RAG workflow.

    Inherited from ``AgentState``:
        messages: Annotated[list, add_messages]  — conversation history
        structured_response: Optional[Any]       — result of response_format

    Custom fields:
        question:         the original user question (for grading)
        documents:        graded, deduped docs gathered by the research subagent
        trace:            SSE trace events for live UI streaming
        generation:       the main agent's final answer (set by finalize_answer)
        quality_passed:   quality_check verdict
        steps:            quality_check attempt counter
        quality_feedback: latest quality check feedback (for retries)
        max_loops:        max quality check retries (default 3)
        web_search_enabled: whether web_fetch is available to the researcher
    """
    question: str
    documents: list[dict]
    trace: list[dict]
    generation: Optional[str]
    quality_passed: bool
    steps: int
    quality_feedback: Optional[str]
    max_loops: int
    web_search_enabled: bool